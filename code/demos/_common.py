"""Shared helpers for the Ch.4 demos: .env loading, LLM construction, result writing.

The LLM is chosen in ch4-tool-use/.env:
  LLM_PROVIDER=ollama  (default; local and free)  or  openai
  LLM_MODEL=<model id>, e.g. qwen2.5:7b for Ollama or gpt-4o-mini for OpenAI
  OPENAI_API_KEY=...   only for openai
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
load_dotenv(ROOT / ".env")

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "ollama").strip().lower()


def model_name() -> str:
    return os.environ.get("LLM_MODEL", "").strip()


def llm_available() -> bool:
    if not model_name():
        return False
    if provider() == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    try:
        import requests

        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).json()
        return any(m["name"] in (model_name(), f"{model_name()}:latest") for m in tags.get("models", []))
    except Exception:  # noqa: BLE001 - server not running
        return False


def make_llm(**kw):
    if not llm_available():
        raise SystemExit(f"LLM not ready (provider={provider()!r}, model={model_name()!r}). "
                         "Check ch4-tool-use/.env and run repro/check_llm.py")
    if provider() == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name(), temperature=0, **kw)
    from langchain_ollama import ChatOllama

    return ChatOllama(model=model_name(), temperature=0, base_url=OLLAMA_URL,
                      num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "8192")), **kw)


def llm_label() -> str:
    return f"{provider()}:{model_name()}"


def meta(**extra) -> dict:
    return {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0], **extra}


def save(name: str, data: dict) -> Path:
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / name
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"-> {out.relative_to(ROOT)}")
    return out
