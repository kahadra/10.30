"""D3: MCP -- the book's two-server example (stdio math + streamable-HTTP weather), made to run.

Part A (offline) runs the book's agent loop (p.82-83) as written against spec-compliant servers,
  and scores the book's keyword router ("+-*/()" -> math, "weather" -> weather) on a labelled query set.
Part B (offline) uses MultiServerMCPClient to discover tools from both servers (tools/list) and call
  them (tools/call) -- the discovery step the book describes but its router bypasses.
Part C (--llm) lets the model route instead: bind the discovered MCP tools and score the first turn
  on the same query set, then run full loops on a few queries.

The book's own servers are not MCP (see repro/r3_book_mcp_handshake.py), so both servers here are
FastMCP equivalents with the same behaviour: demos/mcp_math_server.py and demos/mcp_weather_server.py.

Usage:  python demos/d3_mcp.py [--llm]
"""
import argparse
import asyncio
import socket
import subprocess
import sys
import time

from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from _common import ROOT, llm_available, make_llm, meta, llm_label, save

PORT = 8000

# (query, ground truth: math | weather | none)
QUERIES = [
    ("What is (3 + 5) * 12?", "math"),
    ("Compute 2 ** 10 - 24.", "math"),
    ("What is twelve times eight?", "math"),
    ("What's 15% of 80?", "math"),
    ("Divide 144 by 12.", "math"),
    ("What's the weather in London?", "weather"),
    ("What's the weather in San Francisco (right now)?", "weather"),
    ("What's the weather like in Winston-Salem?", "weather"),
    ("Will I need a jacket in NYC today? How cold is it there?", "weather"),
    ("Current temperature in London?", "weather"),
    ("Who wrote Hamlet?", "none"),
    ("Tell me a joke about trains.", "none"),
]


def book_router(text: str) -> str:
    """The book's routing heuristic, verbatim logic (p.83)."""
    last_msg = text.lower()
    if any(token in last_msg for token in ["+", "-", "*", "/", "(", ")"]):
        return "math"
    elif "weather" in last_msg:
        return "weather"
    return "none"


def connections():
    return {
        "math": {"command": sys.executable, "args": ["-I", str(ROOT / "demos/mcp_math_server.py")], "transport": "stdio"},
        "weather": {"url": f"http://127.0.0.1:{PORT}/mcp", "transport": "streamable_http"},
    }


TOOL_OF = {"evaluate_arithmetic": "math", "get_current_weather": "weather"}


def start_weather_server() -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-I", str(ROOT / "demos/mcp_weather_server.py"), str(PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close()
            return proc
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit(f"weather server did not start on port {PORT}")


def score(pred: list[str]) -> dict:
    gold = [g for _, g in QUERIES]
    return {"accuracy": round(sum(p == g for p, g in zip(pred, gold)) / len(gold), 3),
            "errors": [{"query": q, "gold": g, "pred": p} for (q, g), p in zip(QUERIES, pred) if p != g]}


async def book_loop_as_written(tools) -> dict:
    """p.83: `next(t for t in MCP_TOOLS if t.name == tool_name)` then `tool_obj.arun(user_input)`."""
    query = "What is (3 + 5) * 12?"
    tool_name = book_router(query)
    rec = {"query": query, "routed_to": tool_name, "server_tool_names": [t.name for t in tools]}
    try:
        tool_obj = next(t for t in tools if t.name == tool_name)
        rec["result"] = await tool_obj.arun(query)
    except StopIteration:
        rec["failure"] = f"StopIteration: no tool named {tool_name!r} -- server/connection key != tool name"
    # Patched lookup by server, still passing the raw user text as the tool input:
    tool_obj = next(t for t in tools if TOOL_OF.get(t.name) == tool_name)
    try:
        rec["patched_lookup_raw_text"] = str(await tool_obj.arun(query))[:300]
    except Exception as e:  # noqa: BLE001
        rec["patched_lookup_raw_text"] = f"{type(e).__name__}: {str(e)[:300]}"
    return rec


async def run(use_llm: bool) -> dict:
    proc = start_weather_server()
    try:
        client = MultiServerMCPClient(connections())
        t0 = time.perf_counter()
        tools = await client.get_tools()
        discovery_s = round(time.perf_counter() - t0, 2)
        res = {
            "part_a": {"book_router": score([book_router(q) for q, _ in QUERIES]),
                       "book_loop_as_written": await book_loop_as_written(tools)},
            "part_b": {"discovery_s": discovery_s,
                       "tools": [{"name": t.name, "description": t.description, "args": t.args} for t in tools],
                       "calls": {
                           "evaluate_arithmetic": str(await next(t for t in tools if t.name == "evaluate_arithmetic")
                                                      .ainvoke({"expression": "(3 + 5) * 12"})),
                           "get_current_weather": str(await next(t for t in tools if t.name == "get_current_weather")
                                                      .ainvoke({"city": "London"})),
                       }},
        }
        if use_llm:
            res["part_c"] = await llm_part(tools) if llm_available() else "skipped: LLM not ready (see repro/check_llm.py)"
        return res
    finally:
        proc.terminate()


async def llm_part(tools) -> dict:
    llm = make_llm()
    bound = llm.bind_tools(tools)
    by_name = {t.name: t for t in tools}
    pred, rows = [], []
    for q, gold in QUERIES:
        ai = await bound.ainvoke([HumanMessage(q)])
        names = [c["name"] for c in ai.tool_calls]
        p = TOOL_OF.get(names[0], names[0]) if names else "none"
        pred.append(p)
        rows.append({"query": q, "gold": gold, "pred": p, "calls": [{"name": c["name"], "args": c["args"]} for c in ai.tool_calls]})
    loops = []
    for q in ("What is twelve times eight?", "What's the weather in San Francisco (right now)?"):
        msgs = [HumanMessage(q)]
        ai = await bound.ainvoke(msgs)
        msgs.append(ai)
        for c in ai.tool_calls:
            msgs.append(await by_name[c["name"]].ainvoke(c))
        loops.append({"query": q, "calls": [{"name": c["name"], "args": c["args"]} for c in ai.tool_calls],
                      "final": (await bound.ainvoke(msgs)).content})
    return {"llm_router": score(pred), "first_turn": rows, "full_loops": loops}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    a = ap.parse_args()
    res = asyncio.run(run(a.llm))
    out = {"meta": meta(model=llm_label() if a.llm else None, n_queries=len(QUERIES)), **res}
    print("book router accuracy:", res["part_a"]["book_router"]["accuracy"])
    for e in res["part_a"]["book_router"]["errors"]:
        print(f'  {e["gold"]:>7} -> {e["pred"]:<7} {e["query"]}')
    print("book loop:", res["part_a"]["book_loop_as_written"])
    print("discovered:", [t["name"] for t in res["part_b"]["tools"]], res["part_b"]["calls"])
    if isinstance(res.get("part_c"), dict):
        print("llm router accuracy:", res["part_c"]["llm_router"]["accuracy"])
    save("d3_mcp.json", out)


if __name__ == "__main__":
    main()
