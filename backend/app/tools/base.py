from abc import ABC, abstractmethod
from typing import Any, Type
from pydantic import BaseModel
from backend.app.models.agent import RiskLevel


class BaseTool(ABC):
    """Abstract base class for all NEXORA tools."""

    name: str
    description: str
    risk_level: RiskLevel
    args_schema: Type[BaseModel]

    def validate_args(self, raw_args: dict[str, Any]) -> BaseModel:
        """Validate input arguments against tool's Pydantic schema."""
        return self.args_schema(**raw_args)

    def get_risk_level(self, raw_args: dict[str, Any]) -> RiskLevel:
        """Dynamically evaluate effective risk level based on specific operation arguments."""
        return self.risk_level

    def get_spec(self) -> dict[str, Any]:
        """Return standardized tool specification for LLM planning."""
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "parameters": self.args_schema.model_json_schema(),
        }

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool logic."""
        pass
