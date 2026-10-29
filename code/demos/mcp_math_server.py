"""Minimal MCP server (stdio) exposing safe arithmetic, built with the official SDK's FastMCP.

Same capability as the book's MCP_math_server.py, but speaks real MCP (JSON-RPC 2.0):
initialize -> tools/list -> tools/call.
"""
import ast
import operator

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("math")

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


@mcp.tool()
def evaluate_arithmetic(expression: str) -> float:
    """Evaluate an arithmetic expression using only + - * / ** and parentheses, e.g. "(3 + 5) * 12"."""
    return _eval(ast.parse(expression, mode="eval").body)


if __name__ == "__main__":
    mcp.run()  # stdio transport
