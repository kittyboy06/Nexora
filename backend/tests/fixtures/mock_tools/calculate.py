import ast
import asyncio
import operator
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.tools.base import BaseTool

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


class CalculateArgs(BaseModel):
    expression: str = Field(..., min_length=1, max_length=100, description="Mathematical expression (e.g., '12 * 4 + 7')")


class MockCalculateTool(BaseTool):
    name = "mock_calculate"
    description = "Safely evaluate mathematical expressions."
    risk_level = RiskLevel.SAFE
    args_schema = CalculateArgs

    async def execute(self, expression: str) -> dict:
        await asyncio.sleep(0.05)
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = _safe_eval(tree)
            return {"expression": expression, "result": result}
        except Exception as exc:
            raise ValueError(f"Invalid math expression '{expression}': {exc}")
