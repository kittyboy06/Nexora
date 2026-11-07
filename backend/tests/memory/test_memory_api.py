"""Integration tests for Memory API Endpoints."""

import pytest
import pytest_asyncio
import httpx
from pathlib import Path

from backend.app.main import create_app
from backend.app.memory.backup import MemoryBackupService
from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import MemoryCategory, MemoryStatus, SensitivityLevel
from backend.app.memory.retrieval import MemoryRetrievalEngine
from backend.app.memory.service import MemoryService
from backend.app.memory.store import DurableMemoryStore


@pytest_asyncio.fixture
async def memory_api_client(tmp_path: Path):
    """Set up test client with isolated Memory database and service."""
    db_file = tmp_path / "api_test_memory.db"
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

    app = create_app()
    app.state.memory_db = db
    app.state.memory_store = store
    app.state.memory_retrieval_engine = retrieval
    app.state.memory_backup_service = backup_svc
    app.state.memory_service = service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, service, store


@pytest.mark.asyncio
async def test_api_create_and_reject_secret(memory_api_client):
    client, _, _ = memory_api_client

    # 1. Create valid memory
    payload = {
        "key": "pref:cli_tool",
        "category": "user_preference",
        "value": "Prefer uv package manager for python environments",
        "sensitivity": "LOW",
        "provenance_reason": "User said in session",
    }
    resp = await client.post("/api/memory/records", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "pref:cli_tool"
    assert data["status"] == "ACTIVE"

    # 2. Reject secret in proposal
    bad_payload = {
        "key": "secret_key",
        "category": "user_preference",
        "value": "My token is ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        "sensitivity": "HIGH",
        "provenance_reason": "Contains token",
    }
    bad_resp = await client.post("/api/memory/records", json=bad_payload)
    assert bad_resp.status_code == 400
    assert "credential pattern" in bad_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_api_lifecycle_approve_revoke_delete(memory_api_client):
    client, _, store = memory_api_client

    # 1. Create a medium-sensitivity project fact (staged as PENDING_APPROVAL)
    fact_payload = {
        "key": "fact:node_engine",
        "category": "project_fact",
        "value": "Node.js v20 LTS",
        "sensitivity": "MEDIUM",
        "provenance_reason": "package.json",
    }
    resp = await client.post("/api/memory/records", json=fact_payload)
    assert resp.status_code == 200
    rec = resp.json()
    assert rec["status"] == "PENDING_APPROVAL"
    mem_id = rec["id"]

    # 2. Approve record
    appr_resp = await client.post(f"/api/memory/records/{mem_id}/approve")
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "ACTIVE"

    # 3. Update record value
    patch_resp = await client.patch(f"/api/memory/records/{mem_id}", json={"value": "Node.js v22 LTS"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["value"] == "Node.js v22 LTS"

    # 4. Search records
    search_resp = await client.get("/api/memory/records?query=Node.js")
    assert search_resp.status_code == 200
    hits = search_resp.json()
    assert any(h["id"] == mem_id for h in hits)

    # 5. Revoke record
    rev_resp = await client.post(f"/api/memory/records/{mem_id}/revoke?reason=outdated")
    assert rev_resp.status_code == 200
    assert rev_resp.json()["revoked"] is True

    # 6. Delete record
    del_resp = await client.delete(f"/api/memory/records/{mem_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_api_export_audit_and_backup(memory_api_client):
    client, service, store = memory_api_client

    # Create a record so there is active data
    await client.post(
        "/api/memory/records",
        json={
            "key": "pref:theme",
            "category": "user_preference",
            "value": "High contrast dark mode",
            "sensitivity": "LOW",
            "provenance_reason": "Preferences modal",
        },
    )

    # Export as JSON
    exp_json = await client.get("/api/memory/export?format=json")
    assert exp_json.status_code == 200
    assert "High contrast dark mode" in exp_json.text

    # Export as CSV
    exp_csv = await client.get("/api/memory/export?format=csv")
    assert exp_csv.status_code == 200
    assert "pref:theme" in exp_csv.text

    # Audit log
    audit_resp = await client.get("/api/memory/audit")
    assert audit_resp.status_code == 200
    audits = audit_resp.json()
    assert len(audits) >= 1

    # Trigger backup
    backup_resp = await client.post("/api/memory/backup")
    assert backup_resp.status_code == 200
    backup_data = backup_resp.json()
    assert backup_data["is_valid"] is True
    backup_path = backup_data["backup_path"]

    # List backups
    list_backups = await client.get("/api/memory/backups")
    assert list_backups.status_code == 200
    assert len(list_backups.json()) >= 1

    # Restore backup
    restore_resp = await client.post(f"/api/memory/restore?backup_path={backup_path}")
    assert restore_resp.status_code == 200
    assert restore_resp.json()["restored"] is True
