"""R1: the book's first tool loop (p.74-75) with the configured LLM, as the repo writes it and as the print edition indents it.

repo   : final_response = llm_with_tools.invoke(messages) runs once, after all tool results are appended.
print  : the same call sits inside the for loop, so the model is asked to answer after each tool result,
         while later tool calls are still unanswered.
"""
import json
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos"))
from _common import llm_label, make_llm, meta, save  # noqa: E402


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


QUERY = "What is 393 * 12.25? Also, what is 11 + 49?"


def run(variant: str, llm_with_tools) -> dict:
    messages = [HumanMessage(QUERY)]
    ai_msg = llm_with_tools.invoke(messages)
    messages.append(ai_msg)
    calls, finals = [], []
    for tool_call in ai_msg.tool_calls:
        selected_tool = {"add": add, "multiply": multiply, "exponentiate": exponentiate}[tool_call["name"].lower()]
        tool_msg = selected_tool.invoke(tool_call)
        calls.append({"name": tool_msg.name, "args": tool_call["args"], "content": tool_msg.content})
        messages.append(tool_msg)
        if variant == "print":
            try:
                finals.append(llm_with_tools.invoke(messages).content)
            except Exception as e:  # noqa: BLE001 - OpenAI rejects unanswered tool_call_ids; record it
                finals.append(f"{type(e).__name__}: {str(e)[:200]}")
    if variant == "repo":
        finals.append(llm_with_tools.invoke(messages).content)
    return {"variant": variant, "tool_calls": calls, "final_responses": finals}


def main():
    llm_with_tools = make_llm().bind_tools([multiply, exponentiate, add])
    res = {"meta": meta(model=llm_label(), query=QUERY), "runs": [run(v, llm_with_tools) for v in ("repo", "print")]}
    print(json.dumps(res["runs"], indent=1, ensure_ascii=False))
    save("r1_book_calculator.json", res)


if __name__ == "__main__":
    main()
