from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.messages import HumanMessage, ToolMessage
import requests

@tool
def get_stock_price(ticker: str) -> float:
    """Get the stock price for the stock exchange ticker for the company."""
    api_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    response = requests.get(api_url, headers={"User-Agent": "ch4-tool-use-course-demo/1.0 (graduate course reproduction; local, low volume)"})
    if response.status_code == 200:
        data = response.json()
        return data["chart"]["result"][0]["meta"]["regularMarketPrice"]
    else:
        raise ValueError(f"Failed to fetch stock price for {ticker}")


# Initialize the LLM with GPT-4o and bind the tools
llm = ChatOpenAI(model_name="qwen2.5:7b", temperature=0)
llm_with_tools = llm.bind_tools([get_stock_price])

messages = [HumanMessage("What is the stock price of Apple?")]

ai_msg = llm_with_tools.invoke(messages)
messages.append(ai_msg)

for tool_call in ai_msg.tool_calls:
    tool_msg = ToolMessage(content=str(get_stock_price.invoke(tool_call["args"])), tool_call_id=tool_call["id"], name=tool_call["name"])
    
    print(tool_msg.name)
    print(tool_call['args'])
    print(tool_msg.content)
    messages.append(tool_msg)
    print()

final_response = llm_with_tools.invoke(messages)
print(final_response.content)