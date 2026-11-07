"""Unit tests for Durable Memory Store, Security Gate, and Lifecycle transitions."""

import pytest
from pathlib import Path

from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import (
    MemoryCategory,
    MemoryProposal,
    MemoryStatus,
    MemoryUpdateRequest,
    SensitivityLevel,
)
from backend.app.memory.security import MemorySecurityException, MemorySecurityGate
from backend.app.memory.store import DurableMemoryStore


@pytest.fixture
def store(tmp_path: Path) -> DurableMemoryStore:
    db = MemoryDatabase(db_path=tmp_path / "test_store.db")
    return DurableMemoryStore(database=db)


def test_security_gate_secret_detection():
    # Valid texts
    assert MemorySecurityGate.contains_secret("User prefers dark mode")[0] is False
    assert MemorySecurityGate.contains_secret("Backend uses Python 3.14 on Windows")[0] is False

    # Secrets
    assert MemorySecurityGate.contains_secret("My token is ghp_1234567890abcdefghijklmnopqrstuvwxyz")[0] is True
    assert MemorySecurityGate.contains_secret("API key: sk-abcdefghijklmnopqrstuvwxyz123456")[0] is True
    assert MemorySecurityGate.contains_secret("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")[0] is True
    assert MemorySecurityGate.contains_secret("password = 'super_secret_password_123'")[0] is True
    assert MemorySecurityGate.contains_secret("-----BEGIN RSA PRIVATE KEY-----")[0] is True


def test_store_rejects_secret_proposal(store: DurableMemoryStore):
    proposal = MemoryProposal(
        key="secret_token",
        category=MemoryCategory.USER_PREFERENCE,
        value="Here is my token: ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        sensitivity=SensitivityLevel.HIGH,
        provenance_reason="Test secret rejection",
    )

    with pytest.raises(MemorySecurityException, match="credential pattern"):
        store.create_record(proposal)

    # Verify audit event recorded rejection
    audits = store.list_audit_entries()
    assert len(audits) == 1
    assert audits[0].action == "REJECT_SECRET"


def test_store_lifecycle_and_auto_approval(store: DurableMemoryStore):
    # 1. Low sensitivity preference -> auto-approved ACTIVE
    pref_proposal = MemoryProposal(
        key="pref:editor",
        category=MemoryCategory.USER_PREFERENCE,
        value="VS Code with Vim keybindings",
        sensitivity=SensitivityLevel.LOW,
        provenance_reason="User specified editor in chat",
    )
    pref_rec = store.create_record(pref_proposal)
    assert pref_rec.status == MemoryStatus.ACTIVE
    assert pref_rec.expires_at is None
    assert MemorySecurityGate.verify_integrity(pref_rec.key, pref_rec.value, pref_rec.sensitivity, pref_rec.version_hash)

    # 2. Project fact -> staged as PENDING_APPROVAL with 90-day default TTL
    fact_proposal = MemoryProposal(
        key="fact:db_engine",
        category=MemoryCategory.PROJECT_FACT,
        value="PostgreSQL 16 in Docker container",
        sensitivity=SensitivityLevel.MEDIUM,
        provenance_reason="Extracted from docker-compose.yml",
    )
    fact_rec = store.create_record(fact_proposal)
    assert fact_rec.status == MemoryStatus.PENDING_APPROVAL
    assert fact_rec.expires_at is not None

    # 3. Approve pending fact
    approved = store.approve_proposal(fact_rec.id, reviewer="operator_alice")
    assert approved is not None
    assert approved.status == MemoryStatus.ACTIVE


def test_store_update_and_revoke(store: DurableMemoryStore):
    proposal = MemoryProposal(
        key="pref:theme",
        category=MemoryCategory.USER_PREFERENCE,
        value="Dark Theme",
        sensitivity=SensitivityLevel.LOW,
        provenance_reason="Initial setting",
    )
    rec = store.create_record(proposal)

    # Update value
    updated = store.update_record(rec.id, MemoryUpdateRequest(value="Light Theme", reason="User switched"))
    assert updated is not None
    assert updated.value == "Light Theme"
    assert updated.version_hash != rec.version_hash

    # Updating with secret should be rejected
    with pytest.raises(MemorySecurityException):
        store.update_record(rec.id, MemoryUpdateRequest(value="sk-1234567890abcdefghijklmnopqrstuvwxyz"))

    # Revoke record
    revoked = store.revoke_record(rec.id, reason="No longer valid")
    assert revoked is True
    refetched = store.get_record(rec.id)
    assert refetched is not None
    assert refetched.status == MemoryStatus.REVOKED

    # Active listing should exclude revoked
    active_recs = store.list_records(status=MemoryStatus.ACTIVE)
    assert not any(r.id == rec.id for r in active_recs)


def test_store_delete_and_audit(store: DurableMemoryStore):
    proposal = MemoryProposal(
        key="fact:temporary",
        category=MemoryCategory.PROJECT_FACT,
        value="Disposable project note",
        provenance_reason="Temporary note",
    )
    rec = store.create_record(proposal)
    assert store.get_record(rec.id) is not None

    # Delete permanently
    assert store.delete_record(rec.id) is True
    assert store.get_record(rec.id) is None

    # Check audit trail
    audits = store.list_audit_entries(memory_id=rec.id)
    assert len(audits) >= 2
    actions = [a.action for a in audits]
    assert "PROPOSE" in actions
    assert "DELETE" in actions
