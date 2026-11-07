"""Bridge dynamically mounting approved generated tools into NEXORA's central ToolRegistry."""

import logging
from typing import Any, Type
from pydantic import BaseModel, create_model

from backend.app.models.agent import RiskLevel
from backend.app.sandbox.models import GeneratedToolRecord, SandboxRunStatus
from backend.app.sandbox.registry import GeneratedToolRegistry
from backend.app.sandbox.runners.base import SandboxRunner
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.sandbox.bridge")


class GeneratedSandboxTool(BaseTool):
    """Dynamic BaseTool adapter executing an approved generated tool inside the sandbox."""

    def __init__(
        self,
        record: GeneratedToolRecord,
        runner: SandboxRunner,
    ) -> None:
        self.record = record
        self.runner = runner

        self.name = f"gen__{record.manifest.name}"
        self.description = f"[Generated Tool v{record.manifest.version}] {record.manifest.description}"
        self.risk_level = RiskLevel.CONTROLLED

        # Construct args schema
        self.args_schema = self._build_args_schema()

    def _build_args_schema(self) -> Type[BaseModel]:
        """Dynamically generate Pydantic args schema from manifest input_schema."""
        fields: dict[str, Any] = {}
        input_props = self.record.manifest.input_schema.get("properties", {})

        for prop_name, prop_spec in input_props.items():
            type_str = prop_spec.get("type", "string")
            py_type: Any = str
            if type_str == "integer":
                py_type = int
            elif type_str == "number":
                py_type = float
            elif type_str == "boolean":
                py_type = bool
            elif type_str == "array":
                py_type = list
            elif type_str == "object":
                py_type = dict

            is_required = prop_name in self.record.manifest.input_schema.get("required", [])
            default_val = ... if is_required else None
            fields[prop_name] = (py_type, default_val)

        if not fields:
            # Fallback permissive schema
            class DynamicGeneratedArgs(BaseModel):
                class Config:
                    extra = "allow"

            return DynamicGeneratedArgs

        return create_model(f"Args_{self.record.manifest.name}", **fields)

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the promoted tool within the isolated sandbox environment."""
        result = await self.runner.run(
            tool_name=self.record.manifest.name,
            code=self.record.code,
            mode="run",
            runtime_arguments=kwargs,
        )

        if result.status == SandboxRunStatus.EXECUTION_SUCCESS:
            return result.output

        error_detail = result.stderr or f"Sandbox run status: {result.status.value}"
        raise RuntimeError(f"Tool '{self.name}' sandbox execution failed: {error_detail}")


class GeneratedToolBridgeManager:
    """Synchronizes enabled generated tools with the central ToolRegistry."""

    def __init__(
        self,
        generated_registry: GeneratedToolRegistry,
        tool_registry: ToolRegistry,
        runner: SandboxRunner,
    ) -> None:
        self.generated_registry = generated_registry
        self.tool_registry = tool_registry
        self.runner = runner

    def sync_all(self) -> int:
        """Scan generated catalog and register/unregister tools based on enabled state."""
        records = self.generated_registry.list_tools()
        synced_count = 0

        for rec in records:
            gen_tool_name = f"gen__{rec.manifest.name}"
            if rec.is_enabled:
                tool_instance = GeneratedSandboxTool(record=rec, runner=self.runner)
                self.tool_registry.register(tool_instance)
                synced_count += 1
                logger.info("Mounted generated tool in ToolRegistry: %s", gen_tool_name)
            else:
                self.tool_registry.unregister(gen_tool_name)
                logger.info("Unmounted disabled generated tool from ToolRegistry: %s", gen_tool_name)

        return synced_count

    def register_tool(self, record: GeneratedToolRecord) -> None:
        """Register a single promoted tool in ToolRegistry."""
        if record.is_enabled:
            tool_instance = GeneratedSandboxTool(record=record, runner=self.runner)
            self.tool_registry.register(tool_instance)

    def unregister_tool(self, tool_name: str) -> None:
        """Unregister a tool from ToolRegistry."""
        gen_tool_name = f"gen__{tool_name}" if not tool_name.startswith("gen__") else tool_name
        self.tool_registry.unregister(gen_tool_name)
