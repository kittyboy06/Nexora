"""CRUD Store and repository for Durable Memory and Audit Trails."""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import (
    MemoryAuditEntry,
    MemoryCategory,
    MemoryProposal,
    MemoryRecord,
    MemoryStatus,
    MemoryUpdateRequest,
    SensitivityLevel,
)
from backend.app.memory.security import MemorySecurityException, MemorySecurityGate


class DurableMemoryStore:
    """Manages transactional CRUD operations, status transitions, and audit records."""

    def __init__(self, database: MemoryDatabase) -> None:
        self.db = database

    def create_record(
        self,
        proposal: MemoryProposal,
        auto_approve: bool = False,
        actor: str = "agent",
    ) -> MemoryRecord:
        """Screen and persist a proposed memory record."""
        # 1. Deterministic Secret Screening
        has_secret_k, msg_k = MemorySecurityGate.contains_secret(proposal.key)
        has_secret_v, msg_v = MemorySecurityGate.contains_secret(proposal.value)
        if has_secret_k or has_secret_v:
            err = msg_k or msg_v
            # Record audit event of rejection
            self.record_audit(
                memory_id="pending_rejected",
                action="REJECT_SECRET",
                actor=actor,
                task_id=proposal.provenance_task_id,
                details={"error": err, "key": proposal.key},
            )
            raise MemorySecurityException(f"Memory proposal rejected: {err}")

        # 2. Determine initial lifecycle status
        status = MemoryStatus.PENDING_APPROVAL
        if auto_approve:
            status = MemoryStatus.ACTIVE
        elif (
            proposal.category == MemoryCategory.USER_PREFERENCE
            and proposal.sensitivity == SensitivityLevel.LOW
        ):
            status = MemoryStatus.ACTIVE

        # 3. Compute timestamps and expiration TTL
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        expires_at_iso: Optional[str] = None
        if proposal.ttl_days:
            expires_at_iso = (now_dt + timedelta(days=proposal.ttl_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif proposal.category == MemoryCategory.PROJECT_FACT:
            # Default 90-day retention for learned project facts
            expires_at_iso = (now_dt + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        version_hash = MemorySecurityGate.compute_version_hash(
            key=proposal.key,
            value=proposal.value,
            sensitivity=proposal.sensitivity,
        )

        record = MemoryRecord(
            id=mem_id,
            key=proposal.key.strip(),
            category=proposal.category,
            value=proposal.value.strip(),
            sensitivity=proposal.sensitivity,
            status=status,
            provenance_task_id=proposal.provenance_task_id,
            provenance_reason=proposal.provenance_reason,
            created_at=now_iso,
            updated_at=now_iso,
            expires_at=expires_at_iso,
            version_hash=version_hash,
        )

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO durable_memory (
                    id, key, category, value, sensitivity, status,
                    provenance_task_id, provenance_reason,
                    created_at, updated_at, expires_at, version_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.id,
                    record.key,
                    record.category.value,
                    record.value,
                    record.sensitivity.value,
                    record.status.value,
                    record.provenance_task_id,
                    record.provenance_reason,
                    record.created_at,
                    record.updated_at,
                    record.expires_at,
                    record.version_hash,
                ),
            )

            audit_action = "APPROVE" if status == MemoryStatus.ACTIVE else "PROPOSE"
            conn.execute(
                """
                INSERT INTO memory_audit (memory_id, action, actor, task_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    record.id,
                    audit_action,
                    actor,
                    record.provenance_task_id,
                    json.dumps({"key": record.key, "status": record.status.value}),
                    now_iso,
                ),
            )

        return record

    def get_record(self, memory_id: str) -> Optional[MemoryRecord]:
        """Fetch a specific memory record by ID."""
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM durable_memory WHERE id = ?;", (memory_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)
        finally:
            conn.close()

    def get_record_by_key(self, key: str) -> Optional[MemoryRecord]:
        """Fetch memory record by exact key."""
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM durable_memory WHERE key = ?;", (key,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)
        finally:
            conn.close()

    def list_records(
        self,
        category: Optional[MemoryCategory] = None,
        status: Optional[MemoryStatus] = None,
        include_expired: bool = False,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List memory records with optional filters."""
        query = "SELECT * FROM durable_memory WHERE 1=1"
        params: list[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category.value)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if not include_expired:
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            query += " AND (expires_at IS NULL OR expires_at > ?)"
            params.append(now_iso)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        conn = self.db.get_connection()
        try:
            cursor = conn.execute(query, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def approve_proposal(self, memory_id: str, reviewer: str = "operator") -> Optional[MemoryRecord]:
        """Promote a PENDING_APPROVAL record to ACTIVE status."""
        rec = self.get_record(memory_id)
        if not rec:
            return None

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE durable_memory SET status = ?, updated_at = ? WHERE id = ?;",
                (MemoryStatus.ACTIVE.value, now_iso, memory_id),
            )
            conn.execute(
                """
                INSERT INTO memory_audit (memory_id, action, actor, task_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    memory_id,
                    "APPROVE",
                    reviewer,
                    rec.provenance_task_id,
                    json.dumps({"previous_status": rec.status.value, "new_status": MemoryStatus.ACTIVE.value}),
                    now_iso,
                ),
            )

        return self.get_record(memory_id)

    def update_record(
        self,
        memory_id: str,
        updates: MemoryUpdateRequest,
        actor: str = "operator",
    ) -> Optional[MemoryRecord]:
        """Update an existing memory record's value or attributes."""
        rec = self.get_record(memory_id)
        if not rec:
            return None

        new_val = updates.value if updates.value is not None else rec.value
        new_cat = updates.category if updates.category is not None else rec.category
        new_sens = updates.sensitivity if updates.sensitivity is not None else rec.sensitivity
        new_exp = updates.expires_at if updates.expires_at is not None else rec.expires_at

        # Verify secret screening on new value
        if updates.value is not None:
            has_secret, err = MemorySecurityGate.contains_secret(updates.value)
            if has_secret:
                raise MemorySecurityException(f"Update rejected: {err}")

        new_hash = MemorySecurityGate.compute_version_hash(rec.key, new_val, new_sens)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE durable_memory SET
                    value = ?, category = ?, sensitivity = ?, expires_at = ?,
                    version_hash = ?, updated_at = ?
                WHERE id = ?;
                """,
                (
                    new_val,
                    new_cat.value,
                    new_sens.value,
                    new_exp,
                    new_hash,
                    now_iso,
                    memory_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO memory_audit (memory_id, action, actor, task_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    memory_id,
                    "UPDATE",
                    actor,
                    rec.provenance_task_id,
                    json.dumps({"reason": updates.reason or "Record modified"}),
                    now_iso,
                ),
            )

        return self.get_record(memory_id)

    def revoke_record(self, memory_id: str, actor: str = "operator", reason: str = "") -> bool:
        """Revoke/soft-delete a record, preventing it from being returned in model recall."""
        rec = self.get_record(memory_id)
        if not rec:
            return False

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE durable_memory SET status = ?, updated_at = ? WHERE id = ?;",
                (MemoryStatus.REVOKED.value, now_iso, memory_id),
            )
            conn.execute(
                """
                INSERT INTO memory_audit (memory_id, action, actor, task_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (memory_id, "REVOKE", actor, rec.provenance_task_id, json.dumps({"reason": reason}), now_iso),
            )

        return True

    def delete_record(self, memory_id: str, actor: str = "operator") -> bool:
        """Permanently delete a record and update audit log."""
        rec = self.get_record(memory_id)
        if not rec:
            return False

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM durable_memory WHERE id = ?;", (memory_id,))
            conn.execute(
                """
                INSERT INTO memory_audit (memory_id, action, actor, task_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (memory_id, "DELETE", actor, rec.provenance_task_id, json.dumps({"key": rec.key}), now_iso),
            )

        return True

    def record_audit(
        self,
        memory_id: str,
        action: str,
        actor: str,
        task_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Append an audit event."""
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO memory_audit (memory_id, action, actor, task_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    memory_id,
                    action,
                    actor,
                    task_id,
                    json.dumps(details or {}),
                    now_iso,
                ),
            )

    def list_audit_entries(self, memory_id: Optional[str] = None, limit: int = 100) -> list[MemoryAuditEntry]:
        """Fetch audit timeline entries."""
        query = "SELECT * FROM memory_audit WHERE 1=1"
        params: list[Any] = []

        if memory_id:
            query += " AND memory_id = ?"
            params.append(memory_id)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        conn = self.db.get_connection()
        try:
            cursor = conn.execute(query, params)
            entries = []
            for row in cursor.fetchall():
                entries.append(
                    MemoryAuditEntry(
                        id=row["id"],
                        memory_id=row["memory_id"],
                        action=row["action"],
                        actor=row["actor"],
                        task_id=row["task_id"],
                        details=row["details"],
                        timestamp=row["timestamp"],
                    )
                )
            return entries
        finally:
            conn.close()

    def _row_to_record(self, row: Any) -> MemoryRecord:
        """Convert a sqlite3.Row to MemoryRecord model."""
        return MemoryRecord(
            id=row["id"],
            key=row["key"],
            category=MemoryCategory(row["category"]),
            value=row["value"],
            sensitivity=SensitivityLevel(row["sensitivity"]),
            status=MemoryStatus(row["status"]),
            provenance_task_id=row["provenance_task_id"],
            provenance_reason=row["provenance_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            version_hash=row["version_hash"],
        )
