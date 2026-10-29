"""Hypothesis tests for the Ch.4 examples whose purpose was not (fully) achieved.

Each test states its hypothesis and prediction before running, and records a verdict computed from the data.
LLM: qwen2.5:7b through Ollama's OpenAI-compatible API with the book's ChatOpenAI class (as in r0/r0b).

  w_ua      Wikipedia original failure (HTTP 429)
            H: the library's shared default User-Agent is throttled; the code itself is fine.
            Predict: alternating identical requests -> default UA mostly 429, identifying UA mostly 200.
  w_query   Wikipedia minimal-fix wrong answer
            H: the model's query ("Buzz Aldrin most impressive thing") pulls an unrelated top-1 page.
            Predict: the same tool with the bare entity name returns the right page; the model's query does not.
  w_loop    Wikipedia purpose (retrieve, then answer from the page) over 6 people x 4 conditions
            H1: the book's one-shot loop cannot recover a bad query -> a multi-step loop raises success.
            H2: top_k_results=1 is brittle -> top_k=3 raises success.
  tc        tool_choice ignored
            H: the langchain-ollama wrapper drops tool_choice; Ollama's OpenAI-compatible API honours it.
            Predict: via ChatOpenAI -> /v1, "none" gives 0% tool calls and "required" 100%.
            (Refuted if /v1 behaves like the wrapper: then the server/model ignores it.)
  err       model states a result after the tool reported an error
            H: a generic error ToolMessage is not enough; an explicit instruction (system rule) reduces fabrication.
            Predict: fabrication rate falls with the system rule.
  ver       the book's code fails in the book's pinned environment (langchain 0.1.20)
            H: the code was written against langchain-core >= 0.2 (ToolCall invocation), newer than the pins.
            Predict: the unmodified calculator (model name only) runs under langchain-core 0.2.x.

Usage:  .venv/Scripts/python.exe repro/hypotheses.py [w_ua w_query w_loop tc err ver]
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OLLAMA_V1 = "http://127.0.0.1:11434/v1"
MODEL = "qwen2.5:7b"
UA = "ch4-tool-use-course-demo/1.0 (graduate course reproduction; local, low volume)"
os.environ.setdefault("OPENAI_API_KEY", "ollama-local")


def llm(**kw):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=MODEL, temperature=0, base_url=OLLAMA_V1, api_key="ollama-local", **kw)


def save(name, data):
    data = {"meta": {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "llm": f"{MODEL} via Ollama /v1"}, **data}
    (RES / f"h_{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"-> results/h_{name}.json")


# ---------- Wikipedia ---------------------------------------------------------------------------
def w_ua(n=6, gap=2.0):
    import requests
    import wikipedia.wikipedia as w

    params = {"action": "query", "prop": "extracts|revisions", "explaintext": "", "rvprop": "ids", "titles": "Buzz Aldrin", "format": "json"}
    rows = []
    for i in range(n):
        for name, ua in (("default", w.USER_AGENT), ("identifying", UA)):
            r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers={"User-Agent": ua}, timeout=10)
            rows.append({"i": i, "ua": name, "status": r.status_code, "retry_after": r.headers.get("retry-after")})
            time.sleep(gap)
    rate = {u: sum(r["status"] == 200 for r in rows if r["ua"] == u) / n for u in ("default", "identifying")}
    # Decision rule = the prediction stated above ("default mostly 429, identifying mostly 200"). The first run used a stricter
    # threshold (default ok-rate <= 0.2) that did not match the stated prediction; corrected here and noted in the result.
    verdict = "supported" if rate["identifying"] >= 0.8 and rate["default"] < 0.5 else ("refuted" if rate["default"] >= 0.8 else "inconclusive")
    print("ok-rate", rate, verdict)
    save("w_ua", {"hypothesis": "shared default UA is throttled", "ok_rate": rate, "verdict": verdict, "rows": rows})


def _patient_wiki_requests():
    """Test harness only (not a variable under test): honour HTTP 429 Retry-After so transient throttling does not
    masquerade as an agent failure. Each wait is logged in WIKI_WAITS."""
    import requests
    import wikipedia.wikipedia as w

    if getattr(w, "_patched", False):
        return

    def _wiki_request(params):
        params["format"] = "json"
        params.setdefault("action", "query")
        for attempt in range(4):
            r = requests.get(w.API_URL, params=params, headers={"User-Agent": w.USER_AGENT}, timeout=15)
            if r.status_code != 429:
                return r.json()
            wait = min(int(r.headers.get("retry-after", "5")), 60)
            WIKI_WAITS.append(wait)
            time.sleep(wait)
        return r.json()

    w._wiki_request, w._patched = _wiki_request, True


WIKI_WAITS = []


def wiki_tool(top_k):
    import wikipedia
    _patient_wiki_requests()
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    wikipedia.set_user_agent(UA)
    return WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=top_k, doc_content_chars_max=300 * top_k))


def pages(text):
    return re.findall(r"^Page: (.+)$", text or "", re.M)


def w_query():
    tool = wiki_tool(1)
    out = {}
    for q in ("Buzz Aldrin most impressive thing", "Buzz Aldrin"):
        out[q] = pages(tool.invoke({"query": q}))
        time.sleep(1.5)
    verdict = "supported" if out["Buzz Aldrin"] == ["Buzz Aldrin"] and out["Buzz Aldrin most impressive thing"] != ["Buzz Aldrin"] else "refuted"
    print(out, verdict)
    save("w_query", {"hypothesis": "the model's query pulls an unrelated top-1 page", "pages": out, "verdict": verdict, "retry_after_waits_s": WIKI_WAITS})


PEOPLE = {  # person -> facts that a grounded answer about their most notable achievement should mention (any one)
    "Buzz Aldrin": ["apollo 11", "moon"],
    "Marie Curie": ["nobel", "radioactiv", "polonium", "radium"],
    "Alan Turing": ["enigma", "turing machine", "computer science", "codebreak"],
    "Ada Lovelace": ["analytical engine", "program", "algorithm"],
    "Yuri Gagarin": ["first human", "first person", "vostok", "outer space"],
    "Katherine Johnson": ["nasa", "trajector", "orbital", "calculation"],
}


def agent(tool, question, max_rounds):
    from langchain_core.messages import HumanMessage

    bound = llm().bind_tools([tool])
    msgs, trace = [HumanMessage(question)], []
    for _ in range(max_rounds):
        ai = bound.invoke(msgs)
        msgs.append(ai)
        if not ai.tool_calls:
            return ai.content, trace
        for tc in ai.tool_calls:
            try:
                tm = tool.invoke(tc)
                got = pages(tm.content)
            except Exception as e:  # noqa: BLE001 - record API failures (e.g. 429) as outcomes
                from langchain_core.messages import ToolMessage
                tm, got = ToolMessage(f"error: {type(e).__name__}", tool_call_id=tc["id"]), [f"ERROR {type(e).__name__}"]
            trace.append({"query": tc["args"].get("query"), "pages": got})
            msgs.append(tm)
            time.sleep(1.0)
    return bound.invoke(msgs).content, trace  # book loop: answer after one round of tool calls


def w_loop():
    conds = [("book: 1 round, top_k=1", 1, 1), ("multi-step (<=3), top_k=1", 3, 1), ("1 round, top_k=3", 1, 3), ("multi-step (<=3), top_k=3", 3, 3)]
    rows = []
    for name, rounds, k in conds:
        tool = wiki_tool(k)
        for person, facts in PEOPLE.items():
            q = f"What was the most impressive thing about {person}?"
            final, trace = agent(tool, q, rounds)
            retrieved = any(person in p for t in trace for p in t["pages"])
            grounded = retrieved and any(f in (final or "").lower() for f in facts)
            rows.append({"condition": name, "person": person, "trace": trace, "final": final, "retrieved_right_page": retrieved, "success": grounded})
            print(f"{name:<28} {person:<18} retrieved={retrieved!s:<5} success={grounded!s:<5} {[t['query'] for t in trace]}")
    summary = {c: {"success": sum(r["success"] for r in rows if r["condition"] == c) / len(PEOPLE),
                   "retrieved": sum(r["retrieved_right_page"] for r in rows if r["condition"] == c) / len(PEOPLE)} for c, _, _ in conds}
    s = {c: v["success"] for c, v in summary.items()}
    v1 = "supported" if s["multi-step (<=3), top_k=1"] > s["book: 1 round, top_k=1"] else "not supported"
    v2 = "supported" if s["1 round, top_k=3"] > s["book: 1 round, top_k=1"] else "not supported"
    print(summary, {"H1 multi-step": v1, "H2 top_k": v2})
    save("w_loop", {"success_criterion": "the right page was retrieved AND the answer mentions one of its key facts",
                    "summary": summary, "verdicts": {"H1_multi_step": v1, "H2_top_k3": v2}, "retry_after_waits_s": WIKI_WAITS, "rows": rows})


TITLE_DESC = ("Look up one Wikipedia article and return its summary. The input must be the title of the article, such as a person's "
              "full name (e.g. 'Buzz Aldrin') or a topic name - not a question and not extra words like 'most impressive'.")


def w_desc():
    """H-W4: the tool description drives query formation. Predict: a title-only description makes the model query the entity
    name, so the book's one-round loop retrieves the right page and success rises (vs. the original description)."""
    conds = [("original description, 1 round", None, 1), ("title-only description, 1 round", TITLE_DESC, 1),
             ("title-only description, multi-step (<=3)", TITLE_DESC, 3)]
    rows = []
    for name, desc, rounds in conds:
        tool = wiki_tool(1)
        if desc:
            tool.description = desc
        for person, facts in PEOPLE.items():
            final, trace = agent(tool, f"What was the most impressive thing about {person}?", rounds)
            retrieved = any(person in p for t in trace for p in t["pages"])
            mentions = any(f in (final or "").lower() for f in facts)
            rows.append({"condition": name, "person": person, "trace": trace, "final": final,
                         "retrieved_right_page": retrieved, "mentions_key_fact": mentions, "success": retrieved and mentions})
            print(f"{name:<44} {person:<18} retrieved={retrieved!s:<5} success={retrieved and mentions!s:<5} {[t['query'] for t in trace]}", flush=True)
    summary = {c: {k: sum(r[k] for r in rows if r["condition"] == c) / len(PEOPLE) for k in ("success", "retrieved_right_page", "mentions_key_fact")}
               for c, _, _ in conds}
    verdict = "supported" if summary["title-only description, 1 round"]["success"] > summary["original description, 1 round"]["success"] else "not supported"
    print(summary, verdict)
    save("w_desc", {"hypothesis": "the tool description drives query formation", "title_only_description": TITLE_DESC,
                    "summary": summary, "verdict": verdict, "retry_after_waits_s": WIKI_WAITS, "rows": rows})


# ---------- tool_choice -------------------------------------------------------------------------
def tc():
    from langchain_core.messages import HumanMessage
    from langchain_core.tools import tool

    @tool
    def multiply(x: float, y: float) -> float:
        """Multiply 'x' times 'y'."""
        return x * y

    @tool
    def add(x: float, y: float) -> float:
        """Add 'x' and 'y'."""
        return x + y

    math_q = ["What is 393 * 12.25?", "Add 11 and 49.", "Multiply 17 by 23.", "What is 7.5 plus 2.25?"]
    other_q = ["Say hello in French.", "What is the capital of France?", "Write a haiku about trains.", "Who wrote Hamlet?"]
    rows, summary = [], {}
    for mode in ("auto", "none", "required", "multiply"):
        bound = llm().bind_tools([multiply, add], tool_choice=mode)
        for q in math_q + other_q:
            try:
                ai = bound.invoke([HumanMessage(q)])
                calls = [c["name"] for c in ai.tool_calls]
                err = None
            except Exception as e:  # noqa: BLE001 - the server may reject a tool_choice value
                calls, err = [], f"{type(e).__name__}: {str(e)[:160]}"
            rows.append({"mode": mode, "query": q, "calls": calls, "error": err})
        rs = [r for r in rows if r["mode"] == mode]
        summary[mode] = {"tool_rate_math": sum(bool(r["calls"]) for r in rs if r["query"] in math_q) / 4,
                         "tool_rate_other": sum(bool(r["calls"]) for r in rs if r["query"] in other_q) / 4,
                         "errors": sum(bool(r["error"]) for r in rs)}
        print(mode, summary[mode])
    honoured = summary["none"]["tool_rate_math"] == 0 and summary["required"]["tool_rate_other"] == 1
    verdict = "supported (the wrapper drops it; /v1 honours it)" if honoured else "refuted (ignored by the server/model too)"
    print(verdict)
    save("tc", {"hypothesis": "langchain-ollama drops tool_choice; Ollama's OpenAI-compatible API honours it",
                "summary": summary, "verdict": verdict, "rows": rows})


# ---------- error fabrication -------------------------------------------------------------------
PAIRS = [(393, 12.25), (17, 23), (48.5, 6), (1234, 5.5), (99, 101), (3.75, 64)]
RULE = ("If a tool returns an error, do not compute or estimate that value yourself. Say that the value is unavailable "
        "and report only the results the tools returned.")


def err():
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool

    @tool
    def multiply(x: float, y: float) -> float:
        """Multiply 'x' times 'y'."""
        return x * y

    @tool
    def add(x: float, y: float) -> float:
        """Add 'x' and 'y'."""
        return x + y

    ERR = "error: tool unavailable after retries; tell the user instead of guessing."
    bound = llm().bind_tools([multiply, add])
    rows = []
    for cond in ("error ToolMessage only", "error ToolMessage + system rule"):
        for a, b in PAIRS:
            q = f"What is {a} * {b}? Also, what is 11 + 49?"
            msgs = ([SystemMessage(RULE)] if "rule" in cond else []) + [HumanMessage(q)]
            ai = bound.invoke(msgs)
            msgs.append(ai)
            for c in ai.tool_calls:  # multiply always fails, add succeeds
                content = ERR if c["name"] == "multiply" else str(add.invoke(c["args"]))
                msgs.append(ToolMessage(content, tool_call_id=c["id"], name=c["name"], status="error" if c["name"] == "multiply" else "success"))
            final = bound.invoke(msgs).content if ai.tool_calls else ai.content
            nums = {round(float(x.replace(",", "")), 2) for x in re.findall(r"-?\d[\d,]*\.?\d*", final or "") if x.replace(",", "").replace(".", "").lstrip("-").isdigit()}
            allowed = {round(float(a), 2), round(float(b), 2), 11.0, 49.0, 60.0}
            fabricated = bool(nums - allowed)
            rows.append({"condition": cond, "query": q, "called": [c["name"] for c in ai.tool_calls], "final": final,
                         "unsupported_numbers": sorted(nums - allowed), "fabricated": fabricated})
            print(f"{cond:<34} {a}*{b:<6} fabricated={fabricated!s:<5} {sorted(nums - allowed)}")
    rate = {c: sum(r["fabricated"] for r in rows if r["condition"] == c) / len(PAIRS) for c in ("error ToolMessage only", "error ToolMessage + system rule")}
    verdict = "supported" if rate["error ToolMessage + system rule"] < rate["error ToolMessage only"] else "not supported"
    print(rate, verdict)
    save("err", {"hypothesis": "an explicit system rule reduces fabrication after a tool error", "fabrication_rate": rate,
                 "verdict": verdict, "rows": rows})


# ---------- version -----------------------------------------------------------------------------
def ver():
    uv = ROOT / ".venv/Scripts/uv.exe"
    env = ROOT / ".venv-book-core02"
    if not env.exists():
        subprocess.run([str(uv), "venv", "-q", "--python", "3.11", str(env)], check=True)
    if True:  # always (idempotent): a half-installed env must not produce a verdict
        subprocess.run([str(uv), "pip", "install", "-q", "--link-mode=copy", "--python", str(env / "Scripts/python.exe"),
                        "langchain==0.2.16", "langchain-openai==0.1.25"], check=True)
    py = env / "Scripts/python.exe"
    versions = subprocess.run([str(py), "-c", "import langchain_core,langchain;print(langchain.__version__, langchain_core.__version__)"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    script = ROOT / "repro/book_runs/book_calculator.py"  # original + model name only
    e = {**os.environ, "OPENAI_API_BASE": OLLAMA_V1, "OPENAI_BASE_URL": OLLAMA_V1, "OPENAI_API_KEY": "ollama-local", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([str(py), str(script)], cwd=ROOT / "third_party/book-repo", env=e, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    ok = p.returncode == 0 and "4814.25" in p.stdout
    verdict = "supported" if ok else "refuted"
    print(versions, p.returncode, verdict, p.stdout.strip()[-120:], (p.stderr.strip().splitlines() or [""])[-1][:200])
    save("ver", {"hypothesis": "book code targets langchain-core >= 0.2 (newer than its pins)", "env": f"Python 3.11, langchain/core {versions}",
                 "exit": p.returncode, "stdout_tail": p.stdout.strip()[-500:], "stderr_last": (p.stderr.strip().splitlines() or [""])[-1],
                 "verdict": verdict})


# ---------- MCP routing on the book's (minimally exposed) servers --------------------------------
MCP_EXPECT = {  # query -> expected tool and a check on the tool's output
    "What is (3 + 5) * 12?": ("math", 96), "Compute 2 ** 10 - 24.": ("math", 1000), "What is twelve times eight?": ("math", 96),
    "What's 15% of 80?": ("math", 12), "Divide 144 by 12.": ("math", 12),
    "What's the weather in London?": ("weather", "london"), "What's the weather in San Francisco (right now)?": ("weather", "san francisco"),
    "What's the weather like in Winston-Salem?": ("weather", "winston-salem"),
    "Will I need a jacket in NYC today? How cold is it there?": ("weather", "nyc"), "Current temperature in London?": ("weather", "london"),
    "Who wrote Hamlet?": ("none", None), "Tell me a joke about trains.": ("none", None),
}


def _mcp_ok(tool, expect, text):
    if tool != expect[0]:
        return False
    if tool == "none":
        return True
    if tool == "math":
        m = re.search(r"-?\d+(?:\.\d+)?", text or "")
        return bool(m) and abs(float(m.group()) - expect[1]) < 1e-6
    return expect[1] in (text or "").lower() or (expect[1] == "nyc" and "new york" in (text or "").lower())


def _mcp_eval(math_file: Path, weather_file: Path):
    """Route MCP_EXPECT queries with the book's keyword rule and with the model, over the given servers."""
    import asyncio
    import socket

    from langchain_core.messages import HumanMessage
    from langchain_mcp_adapters.client import MultiServerMCPClient

    def book_router(text):  # verbatim logic of the book's call_mcp_tools (p.83)
        last_msg = text.lower()
        if any(token in last_msg for token in ["+", "-", "*", "/", "(", ")"]):
            return "math"
        elif "weather" in last_msg:
            return "weather"
        return "none"

    def text_of(res):
        if isinstance(res, list):
            return " ".join(b.get("text", "") for b in res if isinstance(b, dict))
        return str(res)

    srv = subprocess.Popen([sys.executable, str(weather_file)], cwd=ROOT / "third_party/book-repo",
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", 8000), timeout=0.3).close()
                break
            except OSError:
                time.sleep(0.2)

        async def run():
            client = MultiServerMCPClient({"math": {"command": sys.executable, "args": [str(math_file)], "transport": "stdio"},
                                           "weather": {"url": "http://127.0.0.1:8000/mcp", "transport": "streamable_http"}})
            tools = {t.name: t for t in await client.get_tools()}
            import httpx  # fresh async client per event loop (langchain-openai caches one bound to the first loop)
            bound = llm(http_async_client=httpx.AsyncClient(timeout=180)).bind_tools(list(tools.values()))
            rows = []
            for q, expect in MCP_EXPECT.items():
                kw = book_router(q)
                kw_out = text_of(await tools[kw].ainvoke({"query": q})) if kw != "none" else ""
                ai = await bound.ainvoke([HumanMessage(q)])
                c = ai.tool_calls[0] if ai.tool_calls else None
                mr = c["name"] if c else "none"
                m_out = text_of(await tools[mr].ainvoke(c["args"])) if c and mr in tools else ""
                rows.append({"query": q, "expected": expect[0], "keyword_route": kw, "keyword_output": kw_out[:120],
                             "keyword_ok": _mcp_ok(kw, expect, kw_out), "model_route": mr, "model_args": c["args"] if c else None,
                             "model_output": m_out[:120], "model_ok": _mcp_ok(mr, expect, m_out)})
                print(f"{q[:44]:<46} kw={kw:<8}{rows[-1]['keyword_ok']!s:<6} model={mr:<8}{rows[-1]['model_ok']!s:<6} {c['args'] if c else ''}", flush=True)
            return rows

        rows = asyncio.run(run())
    finally:
        srv.terminate()
        time.sleep(1.5)  # free port 8000 for the next condition
    n = len(rows)
    summ = {"keyword_routing_acc": sum(r["keyword_route"] == r["expected"] for r in rows) / n, "keyword_end_to_end": sum(r["keyword_ok"] for r in rows) / n,
            "model_routing_acc": sum(r["model_route"] == r["expected"] for r in rows) / n, "model_end_to_end": sum(r["model_ok"] for r in rows) / n}
    return rows, summ


def mcp():
    """H-M1: the keyword router, not the book's servers, limits the MCP example. Predict: model routing over the same servers
    raises routing accuracy and end-to-end correctness."""
    mn = ROOT / "repro/book_min"
    rows, summ = _mcp_eval(mn / "book_mcp_math_server.py", mn / "book_mcp_weather_server.py")
    verdict = "supported" if summ["model_routing_acc"] > summ["keyword_routing_acc"] and summ["model_end_to_end"] > summ["keyword_end_to_end"] else "not supported"
    print(summ, verdict)
    save("mcp", {"hypothesis": "the keyword router, not the book's servers, limits the MCP example", "servers": "repro/book_min (book logic exposed via MCP SDK)",
                 "summary": summ, "verdict": verdict, "rows": rows})


WEATHER_DOC = '    """Answer a question like "what is the weather in nyc?" (dummy data)."""'
WEATHER_DOC_FULL = ('    """Answer a weather question. Pass the user\'s FULL question unchanged, e.g. "What is the weather in London?" '
                    '- the server only understands the phrase \'weather in <city>\'."""')
MATH_ANCHOR = '    cleaned = cleaned.replace("^", "**")'
CITY_ANCHOR = '            city = "unknown"\n'


def mcp_fix():
    """H-M2: the book's math server fails because its text cleaning leaves leading spaces (Python reports
    'unexpected indent'). Predict: adding .strip() makes keyword-routed symbolic queries succeed.
    H-M3: weather failures come from a mismatch between the server's parser ('weather in <city>') and the model's
    argument (a bare city). Predict: either (a) a description telling the model to pass the full question, or
    (b) a server that also accepts a bare city, raises model end-to-end correctness."""
    mn, hv = ROOT / "repro/book_min", ROOT / "repro/book_min_h"
    hv.mkdir(exist_ok=True)
    math_src = (mn / "book_mcp_math_server.py").read_text(encoding="utf-8")
    line = next(l for l in math_src.splitlines(True) if l.startswith(MATH_ANCHOR))
    (hv / "math_strip.py").write_text(math_src.replace(line, line + "    cleaned = cleaned.strip()  # H-M2\n", 1), encoding="utf-8")
    w_src = (mn / "book_mcp_weather_server.py").read_text(encoding="utf-8")
    assert w_src.count(WEATHER_DOC) == 1
    (hv / "weather_desc.py").write_text(w_src.replace(WEATHER_DOC, WEATHER_DOC_FULL), encoding="utf-8")
    k = w_src.index("def _answer")
    head, seg = w_src[:k], w_src[k:]
    assert seg.count(CITY_ANCHOR) == 1, "expected the except-branch default once in _answer"
    seg = seg.replace(CITY_ANCHOR, CITY_ANCHOR + '    else:  # H-M3b: also accept a bare city name\n'
                                                 '        city = lowered.strip().rstrip("?").strip() or "unknown"\n', 1)
    (hv / "weather_city.py").write_text(head + seg, encoding="utf-8")
    conds = {"book servers (L1)": (mn / "book_mcp_math_server.py", mn / "book_mcp_weather_server.py"),
             "math .strip() + weather description: pass full question": (hv / "math_strip.py", hv / "weather_desc.py"),
             "math .strip() + weather server accepts bare city": (hv / "math_strip.py", hv / "weather_city.py")}
    results = {}
    for name, (mf, wf) in conds.items():
        print("##", name, flush=True)
        rows, summ = _mcp_eval(mf, wf)
        results[name] = {"summary": summ, "rows": rows}
        print(summ, flush=True)
    base = results["book servers (L1)"]["summary"]
    kw_math = lambda c: sum(r["keyword_ok"] for r in results[c]["rows"] if r["expected"] == "math" and r["keyword_route"] == "math")
    a_name, b_name = list(conds)[1], list(conds)[2]
    v2 = "supported" if kw_math(a_name) > kw_math("book servers (L1)") else "not supported"
    va = "supported" if results[a_name]["summary"]["model_end_to_end"] > base["model_end_to_end"] else "not supported"
    vb = "supported" if results[b_name]["summary"]["model_end_to_end"] > base["model_end_to_end"] else "not supported"
    print({"H-M2": v2, "H-M3a": va, "H-M3b": vb})
    save("mcp_fix", {"hypotheses": {"H-M2": "leading spaces after cleaning break the math server", "H-M3a": "description: pass the full question",
                                    "H-M3b": "server accepts a bare city"}, "verdicts": {"H-M2": v2, "H-M3a": va, "H-M3b": vb},
                     "variant_dir": "repro/book_min_h", "results": results})


TESTS = {"w_ua": w_ua, "w_query": w_query, "w_loop": w_loop, "w_desc": w_desc, "tc": tc, "err": err, "ver": ver, "mcp": mcp, "mcp_fix": mcp_fix}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(TESTS):
        print(f"=== {name}")
        TESTS[name]()
