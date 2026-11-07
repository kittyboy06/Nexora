"""Abstract Base Class for Sandbox Runners."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from backend.app.sandbox.models import SandboxRunResult, TestCase


class SandboxRunner(ABC):
    """Abstract interface defining the execution contract for a code sandbox."""

    @abstractmethod
    async def run(
        self,
        tool_name: str,
        code: str,
        mode: str = "test",
        test_cases: Optional[list[TestCase]] = None,
        runtime_arguments: Optional[dict[str, Any]] = None,
        task_id: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ) -> SandboxRunResult:
        """Execute the tool within the sandbox isolation environment."""
        pass
