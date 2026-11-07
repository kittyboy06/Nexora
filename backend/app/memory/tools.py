"""Core tool providing on-demand memory recall to agents during task execution."""

from typing import Any, Optional, Type
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.memory.models import MemoryCategory
from backend.app.memory.retrieval import MemoryRetrievalEngine
from backend.app.memory.store import DurableMemoryStore
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class MemoryQueryArgs(BaseModel):
    """Input parameters for memory query tool."""

    query: str = Field(..., min_length=1, description="Keywords or topic to recall from long-term memory")
    category: Optional[str] = Field(
        default=None,
        description="Optional category filter: 'user_preference', 'project_fact', or 'system_constraint'",
    )
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum number of memory items to return")


class MemoryQueryTool(BaseTool):
    """Enables agents to query active durable preferences and verified project facts."""

    def __init__(
        self,
        retrieval_engine: MemoryRetrievalEngine,
        store: DurableMemoryStore,
    ) -> None:
        self.retrieval_engine = retrieval_engine
        self.store = store

        self.name = "memory_query"
        self.description = (
            "Query long-term persistent memory for saved user preferences, coding conventions, "
            "and project facts recorded in prior sessions."
        )
        self.risk_level = RiskLevel.SAFE
        self.args_schema = MemoryQueryArgs

    async def execute(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 5,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Perform full-text memory lookup and log audit trail."""
        cat_enum: Optional[MemoryCategory] = None
        if category:
            try:
                cat_enum = MemoryCategory(category.lower())
            except ValueError:
                pass

        results = self.retrieval_engine.search(
            query=query,
            category=cat_enum,
            limit=max_results,
        )

        # Audit the recall event
        recalled_ids = [r.id for r in results]
        self.store.record_audit(
            memory_id="query_batch",
            action="RECALL",
            actor="agent",
            details={"query": query, "recalled_count": len(results), "ids": recalled_ids},
        )

        return {
            "query": query,
            "count": len(results),
            "memories": [
                {
                    "id": r.id,
                    "key": r.key,
                    "category": r.category.value,
                    "value": r.value,
                    "provenance": r.provenance_reason,
                    "created_at": r.created_at,
                }
                for r in results
            ],
        }


def register_memory_tools(
    tool_registry: ToolRegistry,
    retrieval_engine: MemoryRetrievalEngine,
    store: DurableMemoryStore,
) -> None:
    """Register memory query capabilities into NEXORA central tool registry."""
    tool = MemoryQueryTool(retrieval_engine=retrieval_engine, store=store)
    tool_registry.register(tool)
