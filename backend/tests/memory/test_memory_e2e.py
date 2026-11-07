"""End-to-End lifecycle tests for Phase 11: Memory and Persistence Platform."""

import pytest
import pytest_asyncio
import httpx
from pathlib import Path

from backend.app.main import create_app
from backend.app.memory.backup import MemoryBackupService
from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import (
    MemoryCategory,
    MemoryProposal,
    MemoryStatus,
    SensitivityLevel,
)
from backend.app.memory.retrieval import MemoryRetrievalEngine
from backend.app.memory.service import MemoryService
from backend.app.memory.store import DurableMemoryStore
from backend.app.memory.tools import MemoryQueryTool, register_memory_tools
from backend.app.tools.registry import ToolRegistry


@pytest_asyncio.fixture
async def memory_e2e_env(tmp_path: Path):
    """Set up full Phase 11 test environment with isolated DB and HTTP client."""
    db_file = tmp_path / "e2e_nexora_memory.db"
    backup_dir = tmp_path / "backups"

    db = MemoryDatabase(db_path=db_file)
    store = DurableMemoryStore(database=db)
    retrieval = MemoryRetrievalEngine(store=store, database=db)
    backup_svc = MemoryBackupService(database=db, backup_dir=backup_dir)
    service = MemoryService(
        store=store,
        retrieval_engine=retrieval,
        backup_service=backup_svc,
        database=db,
    )

    registry = ToolRegistry()
    register_memory_tools(registry, retrieval, store)

    app = create_app()
    app.state.memory_db = db
    app.state.memory_store = store
    app.state.memory_retrieval_engine = retrieval
    app.state.memory_backup_service = backup_svc
    app.state.memory_service = service
    app.state.tool_registry = registry

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield {
            "client": client,
            "service": service,
            "store": store,
            "retrieval": retrieval,
            "backup_svc": backup_svc,
            "registry": registry,
            "db": db,
        }


@pytest.mark.asyncio
async def test_full_memory_lifecycle_e2e(memory_e2e_env):
    """Verify complete end-to-end memory proposal, vetting, recall, backup, and deletion flow."""
    client: httpx.AsyncClient = memory_e2e_env["client"]
    service: MemoryService = memory_e2e_env["service"]
    store: DurableMemoryStore = memory_e2e_env["store"]
    registry: ToolRegistry = memory_e2e_env["registry"]

    # 1. Deterministic Secret Scrubber rejects credential proposals
    secret_payload = {
        "key": "leaked_token",
        "category": "system_constraint",
        "value": "ghp_1234567890abcdefghijklmnopqrstuvwxyz1234",
        "sensitivity": "HIGH",
        "provenance_reason": "Testing secret rejection",
    }
    resp = await client.post("/api/memory/records", json=secret_payload)
    assert resp.status_code == 400
    assert "credential pattern" in resp.json()["error"]["message"]

    # Verify audit recorded rejection
    audits = store.list_audit_entries(limit=5)
    assert any(a.action == "REJECT_SECRET" for a in audits)

    # 2. Agent proposes low-risk user preference -> auto-approved to ACTIVE
    pref_payload = {
        "key": "pref:formatting_indent",
        "category": "user_preference",
        "value": "4 spaces for Python and 2 spaces for TypeScript",
        "sensitivity": "LOW",
        "provenance_reason": "Operator stated preference in Task #101",
    }
    resp = await client.post("/api/memory/records", json=pref_payload)
    assert resp.status_code == 200
    pref_data = resp.json()
    assert pref_data["status"] == "ACTIVE"
    pref_id = pref_data["id"]

    # 3. Agent proposes sensitive project fact -> staged as PENDING_APPROVAL
    fact_payload = {
        "key": "project:production_db_cluster",
        "category": "project_fact",
        "value": "PostgreSQL 16 distributed cluster on port 5432 with replica at 10.0.0.5",
        "sensitivity": "HIGH",
        "provenance_reason": "Extracted from infrastructure deployment manifests",
    }
    resp = await client.post("/api/memory/records", json=fact_payload)
    assert resp.status_code == 200
    fact_data = resp.json()
    assert fact_data["status"] == "PENDING_APPROVAL"
    fact_id = fact_data["id"]

    # 4. FTS5 retrieval excludes pending memories
    search_resp = await client.get("/api/memory/records?query=PostgreSQL")
    assert search_resp.status_code == 200
    records = search_resp.json()
    assert len(records) == 0  # Still pending, so not searchable

    # 5. Operator reviews and approves pending fact
    approve_resp = await client.post(f"/api/memory/records/{fact_id}/approve")
    assert approve_resp.status_code == 200
    approved_data = approve_resp.json()
    assert approved_data["status"] == "ACTIVE"

    # Now retrieval returns the approved record
    search_resp = await client.get("/api/memory/records?query=PostgreSQL")
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 1

    # 6. Planner context injection formats prompt block with XML demarcation & token safety
    prompt_context = service.format_planner_prompt_context("Configure PostgreSQL connection pool")
    assert "<recalled_memory_context>" in prompt_context
    assert "</recalled_memory_context>" in prompt_context
    assert "PostgreSQL 16 distributed cluster" in prompt_context
    assert "historical context only" in prompt_context.lower()

    # 7. Agent executes memory_query tool during execution
    query_tool = registry.get("memory_query")
    assert query_tool is not None
    tool_result = await query_tool.execute(query="spaces")
    assert tool_result["count"] >= 1
    assert any("4 spaces for Python" in m["value"] for m in tool_result["memories"])

    # Verify RECALL audit entry was generated
    recent_audits = store.list_audit_entries(limit=10)
    assert any(a.action == "RECALL" for a in recent_audits)

    # 8. Operator updates an existing record
    update_resp = await client.patch(
        f"/api/memory/records/{fact_id}",
        json={
            "value": "PostgreSQL 16 distributed cluster on port 5432 with failover replica at 10.0.0.6",
            "reason": "Replica IP changed after network failover test",
        },
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert "10.0.0.6" in updated_data["value"]
    assert updated_data["version_hash"] != fact_data["version_hash"]

    # 9. Operator creates online SQLite backup
    backup_resp = await client.post("/api/memory/backup")
    assert backup_resp.status_code == 200
    backup_info = backup_resp.json()
    assert backup_info["is_valid"] is True
    assert backup_info["record_count"] >= 2
    backup_path = backup_info["backup_path"]

    # 10. Operator exports memories as JSON and CSV
    export_json = await client.get("/api/memory/export?format=json")
    assert export_json.status_code == 200
    assert "pref:formatting_indent" in export_json.text

    export_csv = await client.get("/api/memory/export?format=csv")
    assert export_csv.status_code == 200
    assert "id,key,category,value" in export_csv.text
    assert "project:production_db_cluster" in export_csv.text

    # 11. Operator revokes a record -> excluded from search
    revoke_resp = await client.post(
        f"/api/memory/records/{fact_id}/revoke?reason=Cluster+decommissioned"
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["revoked"] is True

    post_revoke_search = await client.get("/api/memory/records?query=PostgreSQL")
    assert len(post_revoke_search.json()) == 0

    # 12. Operator restores backup -> restores database to previous active state
    restore_resp = await client.post(
        f"/api/memory/restore?backup_path={backup_path}"
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["restored"] is True

    # After restore, the record is ACTIVE again
    post_restore_search = await client.get("/api/memory/records?query=PostgreSQL")
    assert len(post_restore_search.json()) == 1

    # 13. Operator permanently deletes record
    del_resp = await client.delete(f"/api/memory/records/{pref_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # Confirm it's gone from database
    get_del = await client.get(f"/api/memory/records/{pref_id}")
    assert get_del.status_code == 404
