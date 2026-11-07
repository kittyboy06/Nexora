"""Task-Scoped Isolated Agent Runtime and Tool Proxy for Fleet Nodes."""

import json
import uuid
from typing import Any
from backend.app.agent.fleet.catalog import SpecialistCatalog, SpecialistProfile
from backend.app.agent.fleet.models import Artifact, FleetNode
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class CapabilityNotPermittedError(Exception):
    """Raised when an agent attempts to invoke a tool outside its node's capability allowlist."""
    pass


class ScopedToolProxy:
    """Restricted tool registry proxy that limits tool discovery and execution to a strict allowlist."""

    def __init__(self, base_registry: ToolRegistry, allowlist: list[str]) -> None:
        self._base = base_registry
        self._allowlist = set(allowlist)

    def get(self, name: str) -> BaseTool | None:
        """Lookup tool only if permitted by the allowlist."""
        if name not in self._allowlist:
            return None
        return self._base.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if tool is registered AND permitted by allowlist."""
        return name in self._allowlist and (self._base.get(name) is not None)

    def list_tools(self) -> list[BaseTool]:
        """Return list of permitted tools."""
        return [t for t in self._base.list_tools() if t.name in self._allowlist]

    def get_tool_names(self) -> list[str]:
        """Return list of permitted tool names."""
        return [name for name in self._base.get_tool_names() if name in self._allowlist]

    def get_specs(self) -> list[dict[str, Any]]:
        """Return tool specs filtered strictly to the allowlist."""
        return [tool.get_spec() for tool in self.list_tools()]


class AgentRuntime:
    """Ephemeral, task-scoped execution runtime for a single FleetNode."""

    def __init__(
        self,
        node: FleetNode,
        profile: SpecialistProfile,
        input_artifacts: list[Artifact],
        tool_proxy: ScopedToolProxy,
    ) -> None:
        self.runtime_id = f"rt_{uuid.uuid4().hex[:12]}"
        self.node = node
        self.profile = profile
        self.input_artifacts = input_artifacts
        self.tool_proxy = tool_proxy
        self.token_budget = node.token_budget

    def build_system_prompt(self) -> str:
        """Construct isolated prompt containing only role instructions, node objective, and input artifacts."""
        lines = [
            f"=== ROLE: {self.profile.display_name.upper()} ===",
            self.profile.system_prompt_template,
            "",
            "=== SUBTASK OBJECTIVE ===",
            self.node.objective,
        ]

        if self.input_artifacts:
            lines.append("")
            lines.append("=== INPUT ARTIFACTS FROM UPSTREAM SPECIALISTS ===")
            for art in self.input_artifacts:
                lines.append(f"--- Artifact ID: {art.artifact_id} (Producer: {art.producer_role}) ---")
                if isinstance(art.content, (dict, list)):
                    lines.append(json.dumps(art.content, indent=2))
                else:
                    lines.append(str(art.content))

        lines.extend([
            "",
            "=== EXECUTION CONSTRAINTS ===",
            f"You are strictly bounded to this subtask. Token budget: {self.token_budget}.",
            f"Permitted tools: {list(self.node.capability_allowlist) if self.node.capability_allowlist else 'None'}.",
            "Return concise, factual, structured results upon completing your objective.",
        ])

        return "\n".join(lines)

    def verify_tool_access(self, tool_name: str) -> None:
        """Verify that the requested tool is authorized in the node's capability allowlist."""
        if tool_name not in self.node.capability_allowlist:
            raise CapabilityNotPermittedError(
                f"Agent in role '{self.profile.role_id}' (node '{self.node.node_id}') "
                f"attempted to access unauthorized tool '{tool_name}'."
            )


class AgentRuntimeFactory:
    """Factory creating isolated AgentRuntime instances for ready fleet nodes."""

    @staticmethod
    def create_runtime(
        node: FleetNode,
        catalog: SpecialistCatalog,
        input_artifacts: list[Artifact],
        tool_registry: ToolRegistry,
    ) -> AgentRuntime:
        """Construct an isolated AgentRuntime with scoped tool proxy and bounded context."""
        profile = catalog.get(node.role)
        if not profile:
            raise ValueError(f"Unknown specialist role '{node.role}' in catalog.")

        # Build scoped tool proxy
        proxy = ScopedToolProxy(
            base_registry=tool_registry,
            allowlist=node.capability_allowlist,
        )

        return AgentRuntime(
            node=node,
            profile=profile,
            input_artifacts=input_artifacts,
            tool_proxy=proxy,
        )
