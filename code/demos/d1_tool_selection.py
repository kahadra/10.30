"""D1: tool-selection accuracy vs. number of tools and description quality.

Ch.4 (Local Tools) says names/descriptions/schemas decide which tool the model picks;
Ch.5 and Ch.8 say accuracy degrades as the toolset grows. This measures both with the
Ch.9 metrics: tool precision, tool recall, parameter accuracy (first model turn only;
tools are never executed).

Conditions: N in {6, 15, 30} tools  x  description in {good, poor}  x  REPEATS.
The 6 target tools are present in every condition; the rest are distractors, some of
them deliberately close to a target (forecast vs current weather, exchange rate vs
currency conversion, draft vs send email).

Usage:  set LLM_PROVIDER / LLM_MODEL in ch4-tool-use/.env, then
        python demos/d1_tool_selection.py [--repeats 3] [--dry-run]
"""
import argparse
import json
import time
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from _common import ROOT, llm_label, make_llm

OUT = ROOT / "results/d1_tool_selection.json"

NUM = {"type": "number"}
STR = {"type": "string"}
TEMP_UNIT = {"type": "string", "enum": ["celsius", "fahrenheit", "kelvin"]}

# name: (good_desc, poor_name, poor_desc, properties)
TARGETS = {
    "add_numbers": ("Return the sum a + b of two numbers.",
                    "process_numbers", "Processes numbers.", {"a": NUM, "b": NUM}),
    "convert_temperature": ("Convert a temperature value between celsius, fahrenheit and kelvin.",
                            "unit_helper", "Helps with units.",
                            {"value": NUM, "from_unit": TEMP_UNIT, "to_unit": TEMP_UNIT}),
    "get_current_weather": ("Get the weather right now (temperature, sky) for a city. Not for future days.",
                            "place_info", "Gets information about a place.", {"city": STR}),
    "get_local_time": ("Get the current local clock time in a city.",
                       "time_helper", "Time related helper.", {"city": STR}),
    "convert_currency": ("Convert an amount of money from one ISO currency code to another, e.g. 100 USD to KRW.",
                         "money_tool", "Money tool.", {"amount": NUM, "from_currency": STR, "to_currency": STR}),
    "send_email": ("Send an email now to a recipient address with a subject and body.",
                   "message_tool", "Handles messages.", {"to": STR, "subject": STR, "body": STR}),
}

DISTRACTORS_15 = {
    "multiply_numbers": ("Return the product a * b of two numbers.", "number_util", "Number utility.", {"a": NUM, "b": NUM}),
    "get_weather_forecast": ("Get the weather forecast for the next N days in a city. Not for current conditions.",
                             "place_lookup", "Looks up a place.", {"city": STR, "days": NUM}),
    "get_air_quality": ("Get the air quality index (AQI) for a city.", "city_data", "City data.", {"city": STR}),
    "convert_length": ("Convert a length between meters, feet, miles and kilometers.", "convert_helper", "Converts things.",
                       {"value": NUM, "from_unit": STR, "to_unit": STR}),
    "get_exchange_rate": ("Return only the exchange rate between two ISO currency codes; does not convert an amount.",
                          "finance_info", "Finance information.", {"from_currency": STR, "to_currency": STR}),
    "search_web": ("Search the web and return result snippets for a query.", "lookup", "Looks things up.", {"query": STR}),
    "send_sms": ("Send a text message (SMS) to a phone number.", "notify", "Notifies someone.", {"phone": STR, "text": STR}),
    "create_calendar_event": ("Create a calendar event with a title and ISO start time.", "schedule_tool", "Schedule tool.",
                              {"title": STR, "start": STR}),
    "translate_text": ("Translate text into a target language.", "text_tool", "Text tool.", {"text": STR, "target_language": STR}),
}

DISTRACTORS_30 = {
    "subtract_numbers": ("Return the difference a - b of two numbers.", "calc_a", "Calculation.", {"a": NUM, "b": NUM}),
    "compute_average": ("Return the arithmetic mean of a list of numbers.", "calc_b", "Calculation.",
                        {"numbers": {"type": "array", "items": NUM}}),
    "compute_percentage": ("Return what percent part is of whole.", "calc_c", "Calculation.", {"part": NUM, "whole": NUM}),
    "convert_weight": ("Convert a weight between kilograms and pounds.", "convert_b", "Converts values.",
                       {"value": NUM, "from_unit": STR, "to_unit": STR}),
    "convert_volume": ("Convert a volume between liters and gallons.", "convert_c", "Converts values.",
                       {"value": NUM, "from_unit": STR, "to_unit": STR}),
    "get_sunrise_time": ("Get today's sunrise and sunset times for a city.", "place_extra", "Place details.", {"city": STR}),
    "convert_timezone": ("Convert a given clock time from one city's time zone to another's.", "time_convert", "Time conversion.",
                         {"time": STR, "from_city": STR, "to_city": STR}),
    "list_calendar_events": ("List calendar events on a given ISO date.", "schedule_list", "Schedule listing.", {"date": STR}),
    "search_news": ("Search recent news articles for a query.", "lookup_b", "Looks things up.", {"query": STR}),
    "search_wikipedia": ("Search Wikipedia and return a page summary.", "lookup_c", "Looks things up.", {"query": STR}),
    "get_stock_price": ("Get the latest stock price for a ticker symbol.", "finance_b", "Finance information.", {"ticker": STR}),
    "send_slack_message": ("Post a message to a Slack channel.", "notify_b", "Notifies someone.", {"channel": STR, "text": STR}),
    "round_number": ("Round a number to a given number of decimal places.", "number_util_b", "Number utility.",
                     {"value": NUM, "digits": NUM}),
    "get_humidity": ("Get the current relative humidity for a city.", "place_extra_b", "Place details.", {"city": STR}),
    "draft_email": ("Save an email as a draft without sending it.", "message_draft", "Handles messages.",
                    {"to": STR, "subject": STR, "body": STR}),
}

# (query, expected tool, expected args) -- 4 per target tool
QUERIES = [
    ("What is 1287.5 plus 349?", "add_numbers", {"a": 1287.5, "b": 349}),
    ("Add 73 and 19 for me.", "add_numbers", {"a": 73, "b": 19}),
    ("I spent 45.2 dollars and then 18.8 more. Total spent?", "add_numbers", {"a": 45.2, "b": 18.8}),
    ("Sum of 0.125 and 3.5?", "add_numbers", {"a": 0.125, "b": 3.5}),
    ("Convert 98.6 Fahrenheit to Celsius.", "convert_temperature", {"value": 98.6, "from_unit": "fahrenheit", "to_unit": "celsius"}),
    ("How many kelvin is 25 degrees celsius?", "convert_temperature", {"value": 25, "from_unit": "celsius", "to_unit": "kelvin"}),
    ("The oven says 350 F. What is that in C?", "convert_temperature", {"value": 350, "from_unit": "fahrenheit", "to_unit": "celsius"}),
    ("Turn -40 celsius into fahrenheit.", "convert_temperature", {"value": -40, "from_unit": "celsius", "to_unit": "fahrenheit"}),
    ("What's the weather in Seoul right now?", "get_current_weather", {"city": "seoul"}),
    ("Is it raining in London at the moment?", "get_current_weather", {"city": "london"}),
    ("Current temperature in Busan?", "get_current_weather", {"city": "busan"}),
    ("How is the sky over Tokyo now?", "get_current_weather", {"city": "tokyo"}),
    ("What time is it in New York?", "get_local_time", {"city": "new york"}),
    ("Tell me the current local time in Paris.", "get_local_time", {"city": "paris"}),
    ("Is it already evening in Sydney? What's the time there?", "get_local_time", {"city": "sydney"}),
    ("Clock time in Berlin right now?", "get_local_time", {"city": "berlin"}),
    ("Convert 100 USD to KRW.", "convert_currency", {"amount": 100, "from_currency": "usd", "to_currency": "krw"}),
    ("How much is 2500 yen in euros?", "convert_currency", {"amount": 2500, "from_currency": "jpy", "to_currency": "eur"}),
    ("I have 50000 won, how many US dollars is that?", "convert_currency", {"amount": 50000, "from_currency": "krw", "to_currency": "usd"}),
    ("Change 75 GBP into USD.", "convert_currency", {"amount": 75, "from_currency": "gbp", "to_currency": "usd"}),
    ("Email kim@lab.ac.kr with subject 'Seminar' and say 'Slides are ready.'", "send_email",
     {"to": "kim@lab.ac.kr", "subject": "seminar", "body": "slides are ready."}),
    ("Send an email to prof@uni.edu, subject Meeting, body: Can we meet Friday?", "send_email",
     {"to": "prof@uni.edu", "subject": "meeting", "body": "can we meet friday?"}),
    ("Please email lee@corp.com titled 'Invoice' saying 'Invoice attached.'", "send_email",
     {"to": "lee@corp.com", "subject": "invoice", "body": "invoice attached."}),
    ("Shoot a mail to team@lab.org, subject 'Lunch', text 'Lunch at noon.'", "send_email",
     {"to": "team@lab.org", "subject": "lunch", "body": "lunch at noon."}),
]

CONDITIONS = [(n, q) for n in (6, 15, 30) for q in ("good", "poor")]


def catalog(n: int) -> dict:
    cat = dict(TARGETS)
    if n >= 15:
        cat |= DISTRACTORS_15
    if n >= 30:
        cat |= DISTRACTORS_30
    assert len(cat) == n, (n, len(cat))
    return cat


def build_tools(n: int, quality: str):
    """Return (tools, name_map) where name_map maps the exposed tool name back to its canonical name."""
    tools, name_map = [], {}
    for canon, (good_desc, poor_name, poor_desc, props) in catalog(n).items():
        name, desc = (canon, good_desc) if quality == "good" else (poor_name, poor_desc)
        schema = {"type": "object", "properties": props, "required": list(props)}
        tools.append(StructuredTool.from_function(func=lambda **_: None, name=name, description=desc, args_schema=schema))
        name_map[name] = canon
    return tools, name_map


def _norm(v):
    return round(float(v), 4) if isinstance(v, (int, float)) else str(v).strip().lower()


def args_match(expected: dict, got: dict) -> bool:
    return all(k in got and _norm(got[k]) == _norm(v) for k, v in expected.items())


def run(repeats: int, dry_run: bool) -> dict:
    llm = make_llm() if not dry_run else None
    rows = []
    for n, quality in CONDITIONS:
        tools, name_map = build_tools(n, quality)
        bound = llm.bind_tools(tools) if llm else None
        for rep in range(repeats):
            for query, exp_tool, exp_args in QUERIES:
                if dry_run:
                    rows.append({"n": n, "quality": quality, "rep": rep, "query": query})
                    continue
                t0 = time.perf_counter()
                msg = bound.invoke([HumanMessage(query)])
                latency = time.perf_counter() - t0
                calls = [{"tool": name_map.get(c["name"], c["name"]), "args": c["args"]} for c in msg.tool_calls]
                hit = [c for c in calls if c["tool"] == exp_tool]
                rows.append({
                    "n": n, "quality": quality, "rep": rep, "query": query, "expected": exp_tool,
                    "calls": calls, "recall_hit": bool(hit),
                    "n_correct_calls": len(hit), "n_calls": len(calls),
                    "args_ok": bool(hit) and args_match(exp_args, hit[0]["args"]),
                    "input_tokens": (msg.usage_metadata or {}).get("input_tokens"),
                    "latency_s": round(latency, 3),
                })
    return {"rows": rows, "summary": summarize(rows) if not dry_run else None}


def summarize(rows):
    out = []
    for n, quality in CONDITIONS:
        rs = [r for r in rows if r["n"] == n and r["quality"] == quality]
        calls = sum(r["n_calls"] for r in rs)
        hits = [r for r in rs if r["recall_hit"]]
        toks = [r["input_tokens"] for r in rs if r["input_tokens"]]
        out.append({
            "n_tools": n, "description": quality, "trials": len(rs),
            "tool_recall": round(len(hits) / len(rs), 3),
            "tool_precision": round(sum(r["n_correct_calls"] for r in rs) / calls, 3) if calls else None,
            "parameter_accuracy": round(sum(r["args_ok"] for r in hits) / len(hits), 3) if hits else None,
            "no_tool_call_rate": round(sum(r["n_calls"] == 0 for r in rs) / len(rs), 3),
            "mean_input_tokens": round(sum(toks) / len(toks)) if toks else None,
            "mean_latency_s": round(sum(r["latency_s"] for r in rs) / len(rs), 3),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true", help="build all conditions without calling the model")
    a = ap.parse_args()
    for n, q in CONDITIONS:
        build_tools(n, q)  # validates catalog sizes
    res = run(a.repeats, a.dry_run)
    if a.dry_run:
        print(f"dry run ok: {len(CONDITIONS)} conditions x {a.repeats} repeats x {len(QUERIES)} queries "
              f"= {len(res['rows'])} model calls")
        return
    meta = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": llm_label(),
            "temperature": 0, "repeats": a.repeats, "n_queries": len(QUERIES)}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"meta": meta, **res}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"meta": meta, "summary": res["summary"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
