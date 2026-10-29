"""R3: Does the book's "MCP" math server speak the MCP protocol?

Runs the official MCP Python client against
  (a) the book repo's src/common/mcp/MCP_math_server.py, and
  (b) a minimal FastMCP server exposing the same arithmetic (control),
and records whether initialize -> tools/list -> tools/call succeeds.
No LLM / API key is needed.
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
BOOK_SERVER = ROOT / "third_party/book-repo/src/common/mcp/MCP_math_server.py"
CONTROL_SERVER = ROOT / "demos/mcp_math_server.py"
TIMEOUT_S = 10


async def probe(server: Path) -> dict:
    params = StdioServerParameters(command=sys.executable, args=["-I", str(server)])
    record = {"server": str(server.relative_to(ROOT)), "steps": []}
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await asyncio.wait_for(session.initialize(), TIMEOUT_S)
                record["steps"].append({"step": "initialize", "ok": True,
                                        "server_info": init.serverInfo.model_dump()})
                tools = await asyncio.wait_for(session.list_tools(), TIMEOUT_S)
                names = [t.name for t in tools.tools]
                record["steps"].append({"step": "tools/list", "ok": True, "tools": names})
                res = await asyncio.wait_for(
                    session.call_tool(names[0], {"expression": "(3 + 5) * 12"}), TIMEOUT_S)
                record["steps"].append({"step": "tools/call", "ok": not res.isError,
                                        "content": [c.model_dump() for c in res.content]})
    except BaseException as e:  # noqa: BLE001 - record any failure, incl. TimeoutError / ExceptionGroup
        record["steps"].append({"step": "failed", "ok": False,
                                "error_type": type(e).__name__, "error": repr(e)[:400]})
    record["handshake_ok"] = bool(record["steps"]) and record["steps"][0].get("step") == "initialize"
    return record


async def main():
    servers = [CONTROL_SERVER] if "--control-only" in sys.argv else [BOOK_SERVER, CONTROL_SERVER]
    results = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "timeout_s": TIMEOUT_S,
        "probes": [await probe(s) for s in servers],
    }
    if "--control-only" in sys.argv:
        OUT = ROOT / "results/r3_control_only.json"
    else:
        OUT = ROOT / "results/r3_book_mcp_handshake.json"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
