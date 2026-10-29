"""R0b: the smallest edits that let each book example run, applied as exact string replacements with a reason each.

Level 0 (repro/r0_book_originals.py) runs the repo files as published (model name swapped only).
Level 1 (this file) builds repro/book_min/*.py from the same originals, applies only the edits listed in FIXES,
writes a .diff per file, and runs them. The book's logic (tools, prompts, routing heuristic, server parsing) is kept;
the book's own advice (retries, fallbacks, validation) is NOT added here -- that is Level 2, the demos/ experiments.

Usage:  .venv/Scripts/python.exe repro/r0b_book_minimal.py
"""
import difflib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "third_party/book-repo"
OUT = ROOT / "repro/book_min"
OLLAMA_V1 = "http://127.0.0.1:11434/v1"
ENVS = {"book": ROOT / ".venv-book/Scripts/python.exe", "current": ROOT / ".venv/Scripts/python.exe"}
MODEL = ('model_name="gpt-4o"', 'model_name="qwen2.5:7b"', "gpt-4o is a paid API model; same ChatOpenAI class via Ollama's OpenAI-compatible API")
TOOLMSG_FIX = "langchain-core 0.1.x (the book's pinned version) cannot invoke a tool with a whole ToolCall dict; pass args and wrap the ToolMessage"
UA = "ch4-tool-use-course-demo/1.0 (graduate course reproduction; local, low volume)"

# file key -> (source, [(old, new, reason)], envs to run)
FIXES = {
    "calculator": ("src/frameworks/langchain/calculator_tool_use.py", [
        (*MODEL[:2], MODEL[2]),
        ("    tool_msg = selected_tool.invoke(tool_call)",
         '    tool_msg = ToolMessage(content=str(selected_tool.invoke(tool_call["args"])), tool_call_id=tool_call["id"], name=tool_call["name"])',
         TOOLMSG_FIX),
    ], ("book", "current")),
    "wikipedia": ("src/frameworks/langchain/wikipedia_tool_use.py", [
        (*MODEL[:2], MODEL[2]),
        ("from langchain_core.messages import HumanMessage",
         f'from langchain_core.messages import HumanMessage, ToolMessage\nimport wikipedia\nwikipedia.set_user_agent("{UA}")',
         "Wikimedia requires an identifying User-Agent (w.wiki/4wJS); the library's shared default UA is rate-limited (HTTP 429). "
         "ToolMessage import for the 0.1.x fix below"),
        ("    tool_msg = tool.invoke(tool_call)",
         '    tool_msg = ToolMessage(content=str(tool.invoke(tool_call["args"])), tool_call_id=tool_call["id"], name=tool_call["name"])',
         TOOLMSG_FIX),
    ], ("book", "current")),
    "stock_price": ("src/frameworks/langchain/stock_price_tool_use.py", [
        (*MODEL[:2], MODEL[2]),
        ('    api_url = f"https://api.example.com/stocks/{ticker}"\n    response = requests.get(api_url)',
         f'    api_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{{ticker}}"\n    response = requests.get(api_url, headers={{"User-Agent": "{UA}"}})',
         "api.example.com is a placeholder with no API behind it; Yahoo's unofficial chart endpoint needs no key but rejects the default UA (429)"),
        ('        return data["price"]', '        return data["chart"]["result"][0]["meta"]["regularMarketPrice"]', "response shape of that endpoint"),
        ("from langchain_core.messages import HumanMessage", "from langchain_core.messages import HumanMessage, ToolMessage", "for the 0.1.x fix below"),
        ("    tool_msg = get_stock_price.invoke(tool_call)",
         '    tool_msg = ToolMessage(content=str(get_stock_price.invoke(tool_call["args"])), tool_call_id=tool_call["id"], name=tool_call["name"])',
         TOOLMSG_FIX),
    ], ("book", "current")),
    "mcp_math_server": ("src/common/mcp/MCP_math_server.py", [
        ("    if isinstance(node, ast.Num):  # <number>\n        return node.n",
         "    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):  # <number>\n        return node.value",
         "ast.Num was removed in Python 3.12"),
        ("# ─── Main Loop ─", "# ─── MCP server (official SDK) — replaces the custom stdin envelope loop below ─\n"
         "from mcp.server.fastmcp import FastMCP\n\nmcp = FastMCP(\"math\")\n\n\n@mcp.tool(name=\"math\")\ndef math_tool(query: str) -> str:\n"
         "    \"\"\"Compute the arithmetic expression contained in the user's message, e.g. \"what's (3 + 5) * 12?\".\"\"\"\n"
         "    # same cleaning as the book's main()\n    cleaned = \"\".join(ch for ch in query if ch.isdigit() or ch in \"+-*/()^ .*\")\n"
         "    cleaned = cleaned.replace(\"^\", \"**\")\n    return str(compute_math(cleaned))\n\n\n# ─── Main Loop (book original, no longer used) ─",
         "The book's server reads a custom {context, payload} envelope, not MCP JSON-RPC; expose the same compute_math as an MCP tool "
         "named \"math\" so the client's name lookup works"),
        ('if __name__ == "__main__":\n    main()', 'if __name__ == "__main__":\n    mcp.run()  # stdio', "serve MCP instead of the envelope loop"),
    ], ()),
    "mcp_weather_server": ("src/common/mcp/MCP_weather_server.py", [
        ('app = FastAPI(title="Weather MCP Server")\n\n@app.post("/mcp", response_model=MCPResponse)\nasync def handle_mcp(request: MCPRequest):',
         'from mcp.server.fastmcp import FastMCP\n\nmcp = FastMCP("weather", port=8000)\n\n\n@mcp.tool(name="weather")\ndef weather_tool(query: str) -> str:\n'
         '    """Answer a question like "what is the weather in nyc?" (dummy data)."""\n    return _answer(query)\n\n\n'
         'app = FastAPI(title="Weather MCP Server")\n\n@app.post("/mcp", response_model=MCPResponse)\nasync def handle_mcp(request: MCPRequest):',
         "The book's server is a plain FastAPI POST endpoint with a custom envelope, not MCP; expose the same logic as an MCP tool named \"weather\""),
        ("    # Very naive parsing: look for a city name after \"weather in \"",
         "    return {\"context\": {\"conversation_id\": context.conversation_id, \"request_id\": context.request_id, \"tokens_used\": 0},\n"
         "            \"payload\": {\"choices\": [{\"text\": _answer(user_msg)}]}}\n\n\ndef _answer(user_msg: str) -> str:\n"
         "    # Very naive parsing: look for a city name after \"weather in \"",
         "move the book's parsing into a function both endpoints share (body unchanged)"),
        ('    # Build response context\n    response_context = {\n        "conversation_id": context.conversation_id,\n'
         '        "request_id": context.request_id,\n        "tokens_used": 0  # set to 0 or mock value; depends on your billing model\n    }\n\n'
         '    # Build response payload\n    response_payload = {\n        "choices": [\n            { "text": f"The current temperature in {city.title()} is {temp}." }\n'
         '        ]\n    }\n\n    return {\n        "context": response_context,\n        "payload": response_payload\n    }',
         '    return f"The current temperature in {city.title()} is {temp}."', "same sentence, returned as the tool result"),
        ('    uvicorn.run(app, host="0.0.0.0", port=8000)', '    mcp.run(transport="streamable-http")  # http://127.0.0.1:8000/mcp',
         "serve MCP streamable HTTP at the URL the book's client expects"),
    ], ()),
    "mcp_client": ("src/frameworks/langgraph_agents/langgraph_mcp_client.py", [
        ("import os\n", "import os\nimport sys\n", "for sys.executable below"),
        ("from langchain.schema import HumanMessage\nfrom langchain.tools import Tool",
         "from langchain_core.messages import HumanMessage\nfrom langchain_core.tools import BaseTool as Tool",
         "langchain.schema / langchain.tools no longer exist (langchain 1.x); same classes live in langchain_core"),
        ('            "command": "python3",\n            "args": ["src/common/mcp/MCP_weather_server.py"],',
         '            "command": sys.executable,\n            "args": ["../../repro/book_min/book_mcp_math_server.py"],',
         "the \"math\" entry launched the weather server file; python3 is not a command on Windows"),
        ("    mcp_result: str = await tool_obj.arun(user_input)", '    mcp_result: str = await tool_obj.arun({"query": user_input})',
         "MCP tools have a JSON schema; LangChain rejects a bare string as input"),
        ('    loop = asyncio.get_event_loop()\n    loop.run_until_complete(run_math_query())\n    loop.run_until_complete(run_weather_query())',
         "    asyncio.run(run_math_query())\n    asyncio.run(run_weather_query())",
         "asyncio.get_event_loop() without a running loop raises on Python 3.14"),
        ('    print("Math answer:", assistant_msg.content)', '    print("Math answer:", assistant_msg["content"])',
         "the graph node returns messages as {role, content} dicts, so the final message has no .content attribute"),
        ('    print("Weather answer:", assistant_msg.content)', '    print("Weather answer:", assistant_msg["content"])', "same as above"),
    ], ("current",)),
}

# Environment-only fixes (no code change): packages the examples import but the book's requirements.txt omits.
ENV_FIXES = {"book": ["wikipedia"]}  # langchain-mcp-adapters cannot be added: incompatible with langchain==0.1.20


def build(key: str) -> list:
    rel, edits, _ = FIXES[key]
    src = (REPO / rel).read_text(encoding="utf-8")
    out, applied = src, []
    for old, new, why in edits:
        n = out.count(old)
        assert n == 1, f"{key}: expected 1 match, found {n}: {old[:60]!r}"
        out = out.replace(old, new)
        applied.append(why)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"book_{key}.py").write_text(out, encoding="utf-8")
    diff = "".join(difflib.unified_diff(src.splitlines(True), out.splitlines(True), f"book-repo/{rel}", f"repro/book_min/book_{key}.py"))
    (OUT / f"book_{key}.diff").write_text(diff, encoding="utf-8")
    changed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
    return [{"reason": w} for w in applied] + [{"original_lines_changed": changed}]


def port_open(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
        return True
    except OSError:
        return False


def run(py: Path, script: Path, timeout=180) -> dict:
    env = {**os.environ, "OPENAI_API_KEY": "ollama-local", "OPENAI_API_BASE": OLLAMA_V1, "OPENAI_BASE_URL": OLLAMA_V1, "PYTHONIOENCODING": "utf-8"}
    t0 = time.perf_counter()
    try:
        p = subprocess.run([str(py), str(script)], cwd=REPO, env=env, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace")
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        code, out, err = "timeout", "", "timeout"
    last = [l for l in err.strip().splitlines() if l.strip()][-1:] if err.strip() else []
    return {"exit": code, "seconds": round(time.perf_counter() - t0, 1), "stdout_tail": out.strip()[-1200:],
            "error_last_line": last[0][:300] if last and code != 0 else None}


def main():
    uv = ROOT / ".venv/Scripts/uv.exe"
    for env_name, pkgs in ENV_FIXES.items():
        subprocess.run([str(uv), "pip", "install", "-q", "--python", str(ENVS[env_name]), *pkgs], check=True)
    results = {k: {"source": FIXES[k][0], "diff_file": f"repro/book_min/book_{k}.diff", "edits": build(k), "runs": {}} for k in FIXES}
    assert not port_open(8000), "port 8000 is busy; stop the other server first"
    weather = subprocess.Popen([str(ENVS["current"]), str(OUT / "book_mcp_weather_server.py")], cwd=REPO,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if port_open(8000):
                break
            time.sleep(0.2)
        for key, (_, _, envs) in FIXES.items():
            for env_name in envs:
                r = run(ENVS[env_name], OUT / f"book_{key}.py")
                results[key]["runs"][env_name] = r
                print(f"{key:<12} {env_name:<8} exit={r['exit']!s:<8} {r['error_last_line'] or r['stdout_tail'][-110:]!r}")
    finally:
        weather.terminate()
    meta = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "llm": "qwen2.5:7b via Ollama OpenAI-compatible API",
            "note": "servers are not run on their own; mcp_client launches the math server (stdio) and uses the weather server on :8000"}
    out = ROOT / "results/r0b_book_minimal.json"
    out.write_text(json.dumps({"meta": meta, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
