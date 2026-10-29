"""D5: tool-use configuration (p.87-88) -- tool_choice modes, then validate -> retry -> fall back -> log.

Part A (LLM) measures what each tool_choice mode actually does with the configured model, two ways:
  native    pass tool_choice to bind_tools (auto | required | none | pin "multiply")
  enforced  implement the mode in client code: none = do not bind tools; required = re-prompt until a tool
            is called (max 2); pinned = bind only that tool + required.
  langchain-ollama documents that tool_choice "is currently ignored as it is not supported by Ollama",
  so with a local model the native column shows what you get when the guarantee silently disappears.
Part B runs the book's corrective flow as a guarded executor. Offline, the model turns are scripted
  (labelled as such) so every branch fires deterministically; with --llm a real model sees the error
  ToolMessages and must repair its own call.
  B1 invalid args -> schema error back to model -> repaired     B2 unknown tool name -> repaired
  B3 transient tool failure x2 -> exponential backoff -> ok      B4 persistent failure -> fallback impl
  B5 skipped tool (answer guessed) -> forced tool call
  B6 final answer states a number no tool produced -> one corrective turn -> replaced by verified results
  every event -> results/d5_events.jsonl

Usage:  python demos/d5_tool_choice.py [--llm]
"""
import argparse
import json
import re
import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import ValidationError

from _common import RESULTS, llm_available, llm_label, make_llm, meta, provider, save


@tool
def multiply(x: float, y: float) -> float:
    """Multiply 'x' times 'y'."""
    return x * y


@tool
def exponentiate(x: float, y: float) -> float:
    """Raise 'x' to the 'y'."""
    return x**y


@tool
def add(x: float, y: float) -> float:
    """Add 'x' and 'y'."""
    return x + y


TOOLS = [multiply, exponentiate, add]  # the book's calculator tools (p.74)

# ---------- Part A: tool_choice ------------------------------------------------------------------
MATH = ["What is 393 * 12.25?", "Add 11 and 49.", "What is 2 to the power of 10?", "Multiply 17 by 23."]
OTHER = ["Say hello in French.", "What is the capital of France?", "Write a haiku about trains.", "Who wrote Hamlet?"]
MODES = ["auto", "required", "none", "pinned:multiply"]
NATIVE = {"auto": "auto", "required": "required", "none": "none", "pinned:multiply": "multiply"}
NUDGE = "You must answer by calling one of the provided tools."


def first_turn(llm, query: str, mode: str, enforced: bool) -> dict:
    msgs = [HumanMessage(query)]
    reprompts = 0
    if not enforced:
        ai = llm.bind_tools(TOOLS, tool_choice=NATIVE[mode]).invoke(msgs)
    elif mode == "none":
        ai = llm.invoke(msgs)
    elif mode == "auto":
        ai = llm.bind_tools(TOOLS).invoke(msgs)
    else:
        bound = llm.bind_tools([multiply] if mode.startswith("pinned") else TOOLS)
        ai = bound.invoke(msgs)
        while not ai.tool_calls and reprompts < 2:
            reprompts += 1
            msgs += [ai, HumanMessage(NUDGE)]
            ai = bound.invoke(msgs)
    return {"query": query, "mode": mode, "enforced": enforced, "reprompts": reprompts,
            "calls": [{"name": c["name"], "args": c["args"]} for c in ai.tool_calls]}


def part_a(llm) -> dict:
    rows = []
    for enforced in (False, True):
        for mode in MODES:
            for q in MATH + OTHER:
                try:
                    rows.append(first_turn(llm, q, mode, enforced))
                except Exception as e:  # noqa: BLE001 - e.g. a provider rejecting a tool_choice value
                    rows.append({"query": q, "mode": mode, "enforced": enforced, "error": f"{type(e).__name__}: {e}"[:200]})
    summary = []
    for enforced in (False, True):
        for mode in MODES:
            rs = [r for r in rows if r["mode"] == mode and r["enforced"] == enforced]
            ok = [r for r in rs if "error" not in r]
            rate = lambda qs: round(sum(bool(r["calls"]) for r in ok if r["query"] in qs) / max(1, sum(r["query"] in qs for r in ok)), 2)
            calls = [c for r in ok for c in r["calls"]]
            summary.append({"how": "enforced" if enforced else "native", "mode": mode, "errors": len(rs) - len(ok),
                            "tool_rate_math": rate(MATH), "tool_rate_other": rate(OTHER),
                            "share_multiply": round(sum(c["name"] == "multiply" for c in calls) / len(calls), 2) if calls else None,
                            "reprompts": sum(r.get("reprompts", 0) for r in ok)})
    return {"summary": summary, "rows": rows}


# ---------- Part B: guarded executor -------------------------------------------------------------
class TransientError(Exception):
    pass


class GuardedExecutor:
    """Validate first, retry with backoff on transient errors, fall back, and log every step."""

    def __init__(self, tools, log: list, retries=3, base_delay_s=0.05, faults=None, fallbacks=None):
        self.tools = {t.name: t for t in tools}
        self.log, self.retries, self.base_delay_s = log, retries, base_delay_s
        self.faults = faults or {}        # tool name -> number of transient failures still to inject, or "always"
        self.fallbacks = fallbacks or {}  # tool name -> backup implementation

    def _event(self, kind, call, **kw):
        self.log.append({"t": round(time.time(), 3), "event": kind, "tool": call["name"], "args": call["args"], **kw})

    def _invoke(self, t, args):
        f = self.faults.get(t.name)
        if f == "always" or (isinstance(f, int) and f > 0):
            if isinstance(f, int):
                self.faults[t.name] = f - 1
            raise TransientError("upstream timeout (injected)")
        return t.invoke(args)

    def run(self, call) -> ToolMessage:
        reply = lambda content, status="success": ToolMessage(str(content), tool_call_id=call["id"], name=call["name"], status=status)
        t = self.tools.get(call["name"])
        if t is None:
            self._event("unknown_tool", call)
            return reply(f"error: no tool named {call['name']!r}. Available: {sorted(self.tools)}", "error")
        try:
            args = t.args_schema.model_validate(call["args"]).model_dump()
        except ValidationError as e:
            errs = [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()]
            self._event("invalid_args", call, errors=errs)
            return reply(f"error: invalid arguments {errs}. Call {call['name']} again with corrected arguments.", "error")
        for attempt in range(1, self.retries + 1):
            try:
                out = self._invoke(t, args)
                self._event("ok", call, attempt=attempt, result=out)
                return reply(out)
            except TransientError as e:
                delay = self.base_delay_s * 2 ** (attempt - 1)
                self._event("retry", call, attempt=attempt, error=str(e), backoff_s=delay)
                time.sleep(delay)
        if call["name"] in self.fallbacks:
            out = self.fallbacks[call["name"]](**args)
            self._event("fallback", call, result=out)
            return reply(f"{out} (computed by fallback implementation)")
        self._event("safe_default", call)
        return reply("error: tool unavailable after retries; tell the user instead of guessing.", "error")


def needs_tool(query: str) -> bool:
    return any(ch.isdigit() for ch in query)


def guarded_loop(model, query: str, ex: GuardedExecutor, max_rounds=4) -> dict:
    """Model turn -> execute calls -> feed results (incl. errors) back, until a final answer."""
    msgs, turns, first_final, challenged = [HumanMessage(query)], [], None, False
    for _ in range(max_rounds + 1):
        ai = model.invoke(msgs)
        msgs.append(ai)
        turns.append({"content": ai.content, "calls": [{"name": c["name"], "args": c["args"]} for c in ai.tool_calls]})
        if not ai.tool_calls:
            if needs_tool(query) and not any(t["calls"] for t in turns):
                ex.log.append({"t": round(time.time(), 3), "event": "skipped_tool", "tool": None, "args": None})
                msgs.append(HumanMessage(NUDGE))
                continue
            first_final = first_final or ai.content
            problems = grounding_problems(query, ai.content, ex.log)
            if problems and not challenged:  # one corrective turn, then replace
                challenged = True
                ex.log.append({"t": round(time.time(), 3), "event": "ungrounded_final", "tool": None, "args": None, **problems})
                msgs.append(HumanMessage(f"Your answer is not supported by the tool results: {problems}. Call the failed tool "
                                         "again with valid arguments, or say that the value is unavailable. Do not invent numbers."))
                continue
            if problems:
                ex.log.append({"t": round(time.time(), 3), "event": "replaced_final", "tool": None, "args": None, **problems})
                verified = "; ".join(dict.fromkeys(f'{e["tool"]}({e["args"]}) = {e["result"]}' for e in ex.log if e["event"] in ("ok", "fallback")))
                return {"query": query, "turns": turns, "final_raw": first_final,
                        "final": f"Some results could not be computed reliably. Verified results: {verified or 'none'}."}
            break
        for c in ai.tool_calls:
            msgs.append(ex.run(c))
    final = msgs[-1].content if isinstance(msgs[-1], AIMessage) else None
    return {"query": query, "turns": turns, "final_raw": first_final, "final": final}


NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _nums(text: str) -> set:
    out = set()
    for m in NUM_RE.findall(text or ""):
        try:
            out.add(round(float(m.replace(",", "").rstrip(".")), 2))
        except ValueError:
            pass
    return out


def grounding_problems(query: str, answer: str, log: list) -> dict:
    """Book p.87: after every response, check the right tools ran and succeeded. Here: (1) a tool whose last
    call failed was never re-run successfully, (2) the answer states numbers found in neither query nor results."""
    status = {}
    for e in log:
        if e["event"] in ("ok", "fallback"):
            status[e["tool"]] = "ok"
        elif e["event"] in ("invalid_args", "safe_default"):
            status[e["tool"]] = "failed"
    unresolved = sorted(t for t, s in status.items() if s == "failed")
    allowed = _nums(query) | {round(float(e["result"]), 2) for e in log
                              if e["event"] in ("ok", "fallback") and isinstance(e.get("result"), (int, float))}
    unsupported = sorted(n for n in _nums(answer) - allowed)
    return {k: v for k, v in (("unresolved_tools", unresolved), ("unsupported_numbers", unsupported)) if v}


class Scripted:
    """Stands in for the model offline: returns the given AIMessages in order (clearly not a real model)."""

    def __init__(self, *turns):
        self.turns = list(turns)

    def invoke(self, _msgs):
        return self.turns.pop(0)


def tc(name, args, i):
    return {"name": name, "args": args, "id": f"call_{i}", "type": "tool_call"}


Q = "What is 393 * 12.25? Also, what is 11 + 49?"


def scripted_cases():
    final = AIMessage("393 times 12.25 is 4814.25, and 11 + 49 is 60.")
    return {
        "B1 invalid args": (Scripted(AIMessage("", tool_calls=[tc("multiply", {"x": "three hundred ninety-three", "y": 12.25}, 1),
                                                               tc("add", {"x": 11, "y": 49}, 2)]),
                                     AIMessage("", tool_calls=[tc("multiply", {"x": 393, "y": 12.25}, 3)]), final), {}),
        "B2 unknown tool": (Scripted(AIMessage("", tool_calls=[tc("multiplication", {"a": 393, "b": 12.25}, 1),
                                                               tc("add", {"x": 11, "y": 49}, 2)]),
                                     AIMessage("", tool_calls=[tc("multiply", {"x": 393, "y": 12.25}, 3)]), final), {}),
        "B3 transient x2": (Scripted(AIMessage("", tool_calls=[tc("multiply", {"x": 393, "y": 12.25}, 1), tc("add", {"x": 11, "y": 49}, 2)]),
                                     final), {"faults": {"multiply": 2}}),
        "B4 persistent -> fallback": (Scripted(AIMessage("", tool_calls=[tc("multiply", {"x": 393, "y": 12.25}, 1),
                                                                         tc("add", {"x": 11, "y": 49}, 2)]), final),
                                      {"faults": {"multiply": "always"}, "fallbacks": {"multiply": lambda x, y: x * y}}),
        "B6 ungrounded final": (Scripted(AIMessage("", tool_calls=[tc("multiply", {"x": 393, "y": 12.25}, 1),
                                                                   tc("add", {"x": 11, "y": 49}, 2)]),
                                        AIMessage("393 times 12.25 is 60.0, and 11 + 49 is 60."),
                                        AIMessage("393 times 12.25 is about 4800, and 11 + 49 is 60.")),
                                {"faults": {"multiply": "always"}}),
        "B5 skipped tool": (Scripted(AIMessage("393 * 12.25 is about 4800, and 11 + 49 is 60."),
                                     AIMessage("", tool_calls=[tc("multiply", {"x": 393, "y": 12.25}, 1), tc("add", {"x": 11, "y": 49}, 2)]),
                                     final), {}),
    }


def part_b_offline(events: list) -> list:
    out = []
    for name, (model, kw) in scripted_cases().items():
        log = []
        r = guarded_loop(model, Q, GuardedExecutor(TOOLS, log, **kw))
        events += [{"case": name, "model": "scripted", **e} for e in log]
        out.append({"case": name, "model": "scripted", "events": [e["event"] for e in log], "final_raw": r["final_raw"], "final": r["final"]})
    return out


def part_b_llm(llm, events: list) -> list:
    """Real model: inject faults at the tool layer, or corrupt the model's first call, and watch it recover."""
    out = []
    bound = llm.bind_tools(TOOLS)

    class CorruptFirst:  # replaces the first call's args with an invalid value; later turns are the model's own
        def __init__(self):
            self.done = False

        def invoke(self, msgs):
            ai = bound.invoke(msgs)
            if ai.tool_calls and not self.done:
                self.done = True
                c = dict(ai.tool_calls[0], args={**ai.tool_calls[0]["args"], "x": "three hundred ninety-three"})
                ai = AIMessage(ai.content, tool_calls=[c] + ai.tool_calls[1:])
            return ai

    cases = {"B1 invalid args (corrupted)": (CorruptFirst(), {}),
             "B3 transient x2": (bound, {"faults": {"multiply": 2}}),
             "B4 persistent -> fallback": (bound, {"faults": {"multiply": "always"}, "fallbacks": {"multiply": lambda x, y: x * y}}),
             "B4' persistent, no fallback": (bound, {"faults": {"multiply": "always"}})}
    for name, (model, kw) in cases.items():
        log = []
        r = guarded_loop(model, Q, GuardedExecutor(TOOLS, log, **kw))
        events += [{"case": name, "model": llm_label(), **e} for e in log]
        out.append({"case": name, "model": llm_label(), "events": [e["event"] for e in log], "turns": r["turns"], "final_raw": r["final_raw"], "final": r["final"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    a = ap.parse_args()
    events = []
    res = {"meta": meta(model=llm_label() if a.llm else None, provider=provider() if a.llm else None),
           "part_b_scripted": part_b_offline(events)}
    for r in res["part_b_scripted"]:
        print(f'{r["case"]:<28} {" -> ".join(r["events"])}')
    if a.llm:
        if llm_available():
            llm = make_llm()
            res["part_a"] = part_a(llm)
            for s in res["part_a"]["summary"]:
                print(s)
            res["part_b_llm"] = part_b_llm(llm, events)
            for r in res["part_b_llm"]:
                print(f'{r["case"]:<28} {" -> ".join(r["events"])}  | {str(r["final"])[:80]}')
        else:
            res["part_a"] = "skipped: LLM not ready (see repro/check_llm.py)"
    save("d5_tool_choice.json", res)
    RESULTS.joinpath("d5_events.jsonl").write_text("\n".join(json.dumps(e, default=str) for e in events) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
