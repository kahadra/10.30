"""D2: API-based tools -- the book's Wikipedia and stock-price examples, then a hardened API tool.

Part A (offline) calls the book's tools directly:
  A1  WikipediaQueryRun({"query": "Buzz Aldrin"}) against the real Wikipedia API (p.76).
  A2  the book's get_stock_price("AAPL") (p.77): api.example.com is a placeholder, so we record
      what an agent loop actually receives -- an exception (loop crashes) or, with
      handle_tool_error=True, a ToolMessage the model can read.
Part B (offline) runs a hardened quote tool against local mock providers (real HTTP on 127.0.0.1)
  with injected faults: timeout, exponential backoff on 5xx/timeout, a fallback provider and a
  cached value -- the "reliability ... graceful failure ... multiple providers" advice of p.78.
Part C (--llm) runs the book's Wikipedia agent loop and the hardened tool inside a model loop.

Usage:  python demos/d2_api_tools.py            # A + B, no API key needed
        python demos/d2_api_tools.py --llm      # A + B + C
"""
import argparse
import json
import re
import threading
import time
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool, tool

from _common import llm_available, make_llm, meta, llm_label, save

warnings.filterwarnings("ignore", category=DeprecationWarning)


# ---------- Part A: the book's tools, verbatim --------------------------------------------------
@tool
def get_stock_price(ticker: str) -> float:
    """Get the stock price for the stock exchange ticker for the company."""
    api_url = f"https://api.example.com/stocks/{ticker}"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        return data["price"]
    else:
        raise ValueError(f"Failed to fetch stock price for {ticker}")


def wikipedia_tool():
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    return WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=300))


def part_a() -> dict:
    out = {}
    wiki = wikipedia_tool()
    t0 = time.perf_counter()
    try:
        text = wiki.invoke({"query": "Buzz Aldrin"})
        out["A1_wikipedia"] = {"tool_name": wiki.name, "args_schema": wiki.args, "chars": len(text), "content": text}
    except Exception as e:  # noqa: BLE001 - e.g. Wikimedia 429 rate limit surfaces as JSONDecodeError
        out["A1_wikipedia"] = {"tool_name": wiki.name, "raised": f"{type(e).__name__}: {str(e)[:200]}"}
    out["A1_wikipedia"]["latency_s"] = round(time.perf_counter() - t0, 2)
    # Raw status of the same API right now, to explain any failure above (Wikimedia requires a User-Agent).
    r = requests.get("https://en.wikipedia.org/w/api.php", timeout=10,
                     params={"action": "query", "list": "search", "srsearch": "Buzz Aldrin", "format": "json"})
    out["A1_wikipedia"]["raw_api_without_user_agent"] = {"status": r.status_code, "body": r.text[:120]}

    call = {"name": "get_stock_price", "args": {"ticker": "AAPL"}, "id": "call_1", "type": "tool_call"}
    t0 = time.perf_counter()
    try:
        msg = get_stock_price.invoke(call)
        raw = {"raised": False, "content": msg.content}
    except Exception as e:  # noqa: BLE001 - this is the point of the experiment
        raw = {"raised": True, "error_type": type(e).__name__, "error": str(e)[:300]}
    raw["latency_s"] = round(time.perf_counter() - t0, 2)

    get_stock_price.handle_tool_error = True
    try:
        msg = get_stock_price.invoke(call)
        handled = {"raised": False, "message_type": type(msg).__name__, "status": getattr(msg, "status", None),
                   "content": str(msg.content)[:300]}
    except Exception as e:  # noqa: BLE001 - handle_tool_error only catches ToolException/ValueError-like errors
        handled = {"raised": True, "error_type": type(e).__name__, "error": str(e)[:300]}
    finally:
        get_stock_price.handle_tool_error = False
    out["A2_book_stock_tool"] = {"url": "https://api.example.com/stocks/AAPL", "timeout_set": False,
                                 "default": raw, "handle_tool_error=True": handled}
    return out


# ---------- Part B: mock providers + hardened tool ----------------------------------------------
class MockProviders:
    """Two quote providers on 127.0.0.1. `mode[name]` is one of ok | flaky | down | slow."""

    def __init__(self):
        self.mode = {"primary": "ok", "backup": "ok"}
        self.hits = {"primary": 0, "backup": 0}
        owner = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                m = re.fullmatch(r"/(primary|backup)/quote/([A-Z.]+)", self.path)
                if not m:
                    return self._send(404, {"error": "not found"})
                name, ticker = m.groups()
                owner.hits[name] += 1
                mode = owner.mode[name]
                if mode == "down" or (mode == "flaky" and owner.hits[name] <= 2):
                    return self._send(503, {"error": "service unavailable"})
                if mode == "slow":
                    time.sleep(2.0)
                price = {"primary": 231.40, "backup": 231.35}[name]
                self._send(200, {"ticker": ticker, "price": price})

            def _send(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except OSError:
                    pass  # client already timed out

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reset(self, primary: str, backup: str):
        self.mode = {"primary": primary, "backup": backup}
        self.hits = {"primary": 0, "backup": 0}


TICKER = re.compile(r"^[A-Z.]{1,10}$")
CACHE = {"AAPL": {"price": 229.87, "as_of": "2026-10-23T20:00:00Z"}}


def make_quote_tool(base: str, log: list, timeout_s=0.5, retries=3, base_delay_s=0.1):
    """Hardened get_stock_price: validated input, timeout, backoff, fallback chain, structured errors."""

    def get_stock_price(ticker: str) -> str:
        """Get the latest stock price in USD for an exchange ticker symbol such as AAPL or MSFT.
        Returns JSON with price and source; source 'cache' means the value may be stale."""
        ticker = ticker.strip().upper()
        if not TICKER.match(ticker):
            return json.dumps({"error": "invalid_ticker", "detail": "Use an exchange ticker like AAPL.", "retryable": False})
        for provider in ("primary", "backup"):
            for attempt in range(1, retries + 1):
                t0 = time.perf_counter()
                try:
                    r = requests.get(f"{base}/{provider}/quote/{ticker}", timeout=timeout_s)
                    outcome = r.status_code
                    if r.status_code == 200:
                        log.append({"provider": provider, "attempt": attempt, "outcome": 200,
                                    "ms": round((time.perf_counter() - t0) * 1000)})
                        return json.dumps({"ticker": ticker, "price": r.json()["price"], "source": provider})
                    retryable = r.status_code >= 500 or r.status_code == 429
                except requests.Timeout:
                    outcome, retryable = "timeout", True
                except requests.ConnectionError:
                    outcome, retryable = "connection_error", True
                log.append({"provider": provider, "attempt": attempt, "outcome": outcome,
                            "ms": round((time.perf_counter() - t0) * 1000)})
                if not retryable:
                    break
                if attempt < retries:
                    time.sleep(base_delay_s * 2 ** (attempt - 1))  # 0.1, 0.2, 0.4 ...
        if ticker in CACHE:
            log.append({"provider": "cache", "attempt": 1, "outcome": "hit"})
            return json.dumps({"ticker": ticker, **CACHE[ticker], "source": "cache"})
        return json.dumps({"error": "all_providers_failed", "retryable": True,
                           "detail": "Quote services are unavailable; tell the user and do not guess a price."})

    return StructuredTool.from_function(get_stock_price)


SCENARIOS = [  # (name, primary mode, backup mode)
    ("primary ok", "ok", "ok"),
    ("primary flaky (503 x2)", "flaky", "ok"),
    ("primary down -> backup", "down", "ok"),
    ("primary slow (timeout) -> backup", "slow", "ok"),
    ("both down -> cache", "down", "down"),
]


def part_b(mock: MockProviders) -> list:
    rows = []
    for name, p, b in SCENARIOS:
        mock.reset(p, b)
        log = []
        t = make_quote_tool(mock.base, log)
        t0 = time.perf_counter()
        result = json.loads(t.invoke({"ticker": "AAPL"}))
        rows.append({"scenario": name, "result": result, "attempts": log,
                     "n_requests": sum(1 for x in log if x["provider"] != "cache"),
                     "elapsed_s": round(time.perf_counter() - t0, 2)})
    log = []
    rows.append({"scenario": "invalid input", "result": json.loads(make_quote_tool(mock.base, log).invoke({"ticker": "Apple Inc"})),
                 "attempts": log, "n_requests": 0})
    return rows


# ---------- Part C: inside a model loop ---------------------------------------------------------
def agent_loop(llm, tools, query: str) -> dict:
    by_name = {t.name: t for t in tools}
    bound = llm.bind_tools(tools)
    messages = [HumanMessage(query)]
    ai = bound.invoke(messages)
    messages.append(ai)
    calls = []
    for tc in ai.tool_calls:
        try:
            tm: ToolMessage = by_name[tc["name"]].invoke(tc)
        except Exception as e:  # noqa: BLE001 - the book's loop has no handler; record where it would crash
            calls.append({"tool": tc["name"], "args": tc["args"], "raised": f"{type(e).__name__}: {str(e)[:200]}"})
            return {"query": query, "tool_calls": calls, "final": None, "loop_crashed": True}
        calls.append({"tool": tc["name"], "args": tc["args"], "result": str(tm.content)[:400]})
        messages.append(tm)
    final = bound.invoke(messages)
    return {"query": query, "tool_calls": calls, "final": final.content, "loop_crashed": False}


def part_c(mock: MockProviders) -> dict:
    llm = make_llm()
    out = {"C1_book_wikipedia_loop": agent_loop(llm, [wikipedia_tool()], "What was the most impressive thing about Buzz Aldrin?")}
    for key, (p, b) in {"C2_hardened_backup": ("down", "ok"), "C3_hardened_cache": ("down", "down")}.items():
        mock.reset(p, b)
        log = []
        r = agent_loop(llm, [make_quote_tool(mock.base, log)], "What is the stock price of Apple?")
        out[key] = {**r, "provider_log": log}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run Part C (needs the LLM set in .env)")
    a = ap.parse_args()
    mock = MockProviders()
    res = {"meta": meta(model=llm_label() if a.llm else None), "part_a": part_a(), "part_b": part_b(mock)}
    if a.llm:
        res["part_c"] = part_c(mock) if llm_available() else "skipped: LLM not ready (see repro/check_llm.py)"
    for r in res["part_b"]:
        print(f'{r["scenario"]:<34} requests={r["n_requests"]}  -> {r["result"]}')
    print("A2 default:", res["part_a"]["A2_book_stock_tool"]["default"])
    save("d2_api_tools.json", res)


if __name__ == "__main__":
    main()
