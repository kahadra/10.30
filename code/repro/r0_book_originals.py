"""R0: run the book's Ch.4 example scripts as published, in the book's pinned environment and in the current one.

Only one change is allowed, and it is written out as a diff: the paid model name
    ChatOpenAI(model_name="gpt-4o", ...)  ->  ChatOpenAI(model_name="qwen2.5:7b", ...)
served by Ollama's OpenAI-compatible endpoint (OPENAI_API_BASE / OPENAI_BASE_URL). The ChatOpenAI class and every
other byte stay as in the repo. The MCP client uses no LLM and runs with no change at all; as the book says, the
weather server (the repo's MCP_weather_server.py) is started first on port 8000.

Environments:
  book     .venv-book  Python 3.11 + third_party/book-repo/requirements.txt (langchain 0.1.20, langchain-openai 0.1.4, langgraph 0.0.28)
  current  .venv      Python 3.14 + requirements.lock.txt

Usage:  .venv/Scripts/python.exe repro/r0_book_originals.py
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
RUNS = ROOT / "repro/book_runs"
OLLAMA_V1 = "http://127.0.0.1:11434/v1"
MODEL_LINE = ('model_name="gpt-4o"', 'model_name="qwen2.5:7b"')
ENVS = {"book": ROOT / ".venv-book/Scripts/python.exe", "current": ROOT / ".venv/Scripts/python.exe"}
EXAMPLES = [  # (key, book page, repo path, needs model swap)
    ("calculator", "p.74-75", "src/frameworks/langchain/calculator_tool_use.py", True),
    ("wikipedia", "p.76", "src/frameworks/langchain/wikipedia_tool_use.py", True),
    ("stock_price", "p.77-78", "src/frameworks/langchain/stock_price_tool_use.py", True),
    ("mcp_client", "p.82-83", "src/frameworks/langgraph_agents/langgraph_mcp_client.py", False),
]
TIMEOUT_S = 180


def prepare(key: str, rel: str, swap: bool) -> tuple[Path, str]:
    src = (REPO / rel).read_text(encoding="utf-8")
    out = src.replace(*MODEL_LINE) if swap else src
    if swap:
        assert src.count(MODEL_LINE[0]) == 1, f"{rel}: expected exactly one model line"
    RUNS.mkdir(parents=True, exist_ok=True)
    target = RUNS / f"book_{key}.py"  # prefixed: a file named wikipedia.py would shadow the wikipedia package
    target.write_text(out, encoding="utf-8")
    diff = "".join(difflib.unified_diff(src.splitlines(True), out.splitlines(True), f"book-repo/{rel}", f"repro/book_runs/book_{key}.py"))
    (RUNS / f"book_{key}.diff").write_text(diff or "(no change)\n", encoding="utf-8")
    return target, diff


def port_open(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
        return True
    except OSError:
        return False


def run(py: Path, script: Path) -> dict:
    env = {**os.environ, "OPENAI_API_KEY": "ollama-local", "OPENAI_API_BASE": OLLAMA_V1, "OPENAI_BASE_URL": OLLAMA_V1,
           "PYTHONIOENCODING": "utf-8"}
    t0 = time.perf_counter()
    try:
        p = subprocess.run([str(py), str(script)], cwd=REPO, env=env, capture_output=True, timeout=TIMEOUT_S,
                           encoding="utf-8", errors="replace")
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        code, out, err = "timeout", (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
    last_err = [l for l in err.strip().splitlines() if l.strip()][-1:] if err.strip() else []
    return {"exit": code, "seconds": round(time.perf_counter() - t0, 1), "stdout_tail": out.strip()[-1200:],
            "error_last_line": last_err[0][:300] if last_err else None, "stderr_tail": err.strip()[-1500:]}


def main():
    weather = None
    if not port_open(8000):  # the book: "Assumes a separate MCP server is already running on port 8000"
        weather = subprocess.Popen([str(ENVS["current"]), "src/common/mcp/MCP_weather_server.py"], cwd=REPO,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if port_open(8000):
                break
            time.sleep(0.2)
    try:
        results = []
        for key, page, rel, swap in EXAMPLES:
            script, diff = prepare(key, rel, swap)
            row = {"example": key, "book_page": page, "repo_file": rel, "change": "model name only" if swap else "none",
                   "diff_file": f"repro/book_runs/book_{key}.diff", "runs": {}}
            for env_name, py in ENVS.items():
                row["runs"][env_name] = run(py, script)
                r = row["runs"][env_name]
                print(f"{key:<12} {env_name:<8} exit={r['exit']!s:<8} {r['seconds']:>6}s  {r['error_last_line'] or r['stdout_tail'][-90:]!r}")
            results.append(row)
    finally:
        if weather:
            weather.terminate()
    meta = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "llm": "qwen2.5:7b via Ollama OpenAI-compatible API",
            "model_substitution": f"{MODEL_LINE[0]} -> {MODEL_LINE[1]} (gpt-4o is a paid API model)",
            "weather_server": "book-repo src/common/mcp/MCP_weather_server.py on :8000 (current env; book env lacks fastapi/uvicorn)",
            "envs": {k: subprocess.run([str(v), "-c", "import sys;print(sys.version.split()[0])"], capture_output=True, text=True).stdout.strip()
                     for k, v in ENVS.items()}}
    out = ROOT / "results/r0_book_originals.json"
    out.write_text(json.dumps({"meta": meta, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
