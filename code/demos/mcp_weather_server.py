"""Minimal MCP server over streamable HTTP (http://127.0.0.1:8000/mcp) with the book's dummy weather data.

Same data as the book's MCP_weather_server.py, but speaks real MCP (JSON-RPC 2.0) via FastMCP.
"""
import sys

from mcp.server.fastmcp import FastMCP

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
mcp = FastMCP("weather", port=PORT, log_level="WARNING")

TEMPS = {"nyc": "58°F", "new york": "58°F", "london": "48°F", "san francisco": "62°F"}


@mcp.tool()
def get_current_weather(city: str) -> str:
    """Get the current temperature for a city (dummy data). Not for forecasts."""
    return f"The current temperature in {city.title()} is {TEMPS.get(city.strip().lower(), '65°F (approx)')}."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
