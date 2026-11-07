"""Unit tests for Memory Retrieval Engine and memory_query Tool."""

import pytest
from pathlib import Path

from backend.app.models.agent import RiskLevel
from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import MemoryCategory, MemoryProposal, SensitivityLevel
from backend.app.memory.retrieval import MemoryRetrievalEngine
from backend.app.memory.store import DurableMemoryStore
from backend.app.memory.tools import MemoryQueryTool, register_memory_tools
from backend.app.tools.registry import ToolRegistry


@pytest.fixture
def retrieval_setup(tmp_path: Path):
    db = MemoryDatabase(db_path=tmp_path / "test_retrieval.db")
    store = DurableMemoryStore(database=db)
    engine = MemoryRetrievalEngine(store=store, database=db)
    tool_reg = ToolRegistry()
    return db, store, engine, tool_reg


def test_fts5_search_and_category_filtering(retrieval_setup):
    _, store, engine, _ = retrieval_setup

    store.create_record(
        MemoryProposal(
            key="pref:python_tests",
            category=MemoryCategory.USER_PREFERENCE,
            value="User prefers pytest with strict fixtures over unittest",
            sensitivity=SensitivityLevel.LOW,
            provenance_reason="User preference prompt",
        )
    )
    store.create_record(
        MemoryProposal(
            key="fact:docker_setup",
            category=MemoryCategory.PROJECT_FACT,
            value="Docker container uses alpine linux base image",
            provenance_reason="Dockerfile review",
        ),
        auto_approve=True,
    )
    store.create_record(
        MemoryProposal(
            key="fact:csharp_tests",
            category=MemoryCategory.PROJECT_FACT,
            value="Desktop project uses xUnit with Moq framework",
            provenance_reason="C# test inspection",
        ),
        auto_approve=True,
    )

    # Search for 'pytest'
    pytest_hits = engine.search("pytest")
    assert len(pytest_hits) >= 1
    assert pytest_hits[0].key == "pref:python_tests"

    # Search for 'linux'
    linux_hits = engine.search("alpine linux")
    assert len(linux_hits) >= 1
    assert linux_hits[0].key == "fact:docker_setup"

    # Filter by category
    fact_hits = engine.search("test", category=MemoryCategory.PROJECT_FACT)
    assert all(r.category == MemoryCategory.PROJECT_FACT for r in fact_hits)


def test_format_planner_context(retrieval_setup):
    _, store, engine, _ = retrieval_setup

    store.create_record(
        MemoryProposal(
            key="pref:style",
            category=MemoryCategory.USER_PREFERENCE,
            value="Write modular functional code with explicit types",
            sensitivity=SensitivityLevel.LOW,
            provenance_reason="User preference",
        )
    )

    context_xml = engine.format_planner_context("Refactor code style", max_tokens=500)
    assert "<recalled_memory_context>" in context_xml
    assert "<recalled_memory" in context_xml
    assert "Write modular functional code" in context_xml
    assert "These are historical context only" in context_xml


@pytest.mark.asyncio
async def test_memory_query_tool_execution(retrieval_setup):
    _, store, engine, tool_reg = retrieval_setup
    register_memory_tools(tool_reg, engine, store)

    store.create_record(
        MemoryProposal(
            key="fact:api_version",
            category=MemoryCategory.PROJECT_FACT,
            value="The backend API uses OpenAPI v3 with FastAPI",
            provenance_reason="main.py",
        ),
        auto_approve=True,
    )

    tool = tool_reg.get("memory_query")
    assert tool is not None
    assert tool.risk_level == RiskLevel.SAFE

    # Execute query
    result = await tool.execute(query="FastAPI OpenAPI")
    assert result["count"] >= 1
    assert any("FastAPI" in m["value"] for m in result["memories"])

    # Verify audit was logged
    audits = store.list_audit_entries()
    assert any(a.action == "RECALL" for a in audits)
