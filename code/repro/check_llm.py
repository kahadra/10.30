"""Check the LLM configured in ch4-tool-use/.env (never prints the API key): reachability, model, one tool call."""
import sys
from pathlib import Path

import requests
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos"))
from _common import OLLAMA_URL, llm_available, llm_label, make_llm, model_name, provider  # noqa: E402

print(f"provider={provider()}  model={model_name() or '<empty>'}")
if provider() == "ollama":
    try:
        names = [m["name"] for m in requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).json()["models"]]
        print(f"ollama server: OK at {OLLAMA_URL}; pulled models: {', '.join(names) or '<none>'}")
    except requests.RequestException:
        sys.exit(f"ollama server: NOT REACHABLE at {OLLAMA_URL} -- start the Ollama app (or `ollama serve`)")
if not llm_available():
    sys.exit("model: NOT READY -- set LLM_MODEL in .env" + (" and run `ollama pull <model>`" if provider() == "ollama" else
                                                            " and OPENAI_API_KEY"))


@tool
def add(x: float, y: float) -> float:
    """Add 'x' and 'y'."""
    return x + y


ai = make_llm().bind_tools([add]).invoke([HumanMessage("What is 11 + 49?")])
ok = any(c["name"] == "add" for c in ai.tool_calls)
print(f"tool call with {llm_label()}: {'OK' if ok else 'NO TOOL CALL'} {ai.tool_calls}")
