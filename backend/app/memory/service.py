"""High-level Orchestration Service for Memory and Persistence."""

import csv
import io
import json
import logging
from typing import Optional

from backend.app.memory.backup import MemoryBackupService
from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import (
    MemoryBackupInfo,
    MemoryCategory,
    MemoryProposal,
    MemoryRecord,
    MemoryStatus,
    MemoryUpdateRequest,
)
from backend.app.memory.retrieval import MemoryRetrievalEngine
from backend.app.memory.store import DurableMemoryStore

logger = logging.getLogger("nexora.memory.service")


class MemoryService:
    """Core domain service orchestrating memory storage, policy filtering, retrieval, and backups."""

    def __init__(
        self,
        store: DurableMemoryStore,
        retrieval_engine: MemoryRetrievalEngine,
        backup_service: MemoryBackupService,
        database: MemoryDatabase,
    ) -> None:
        self.store = store
        self.retrieval_engine = retrieval_engine
        self.backup_service = backup_service
        self.db = database

    def propose_memory(
        self,
        proposal: MemoryProposal,
        auto_approve: bool = False,
        actor: str = "agent",
    ) -> MemoryRecord:
        """Screen and create a new proposed memory record."""
        return self.store.create_record(proposal, auto_approve=auto_approve, actor=actor)

    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        """Fetch memory record by ID."""
        return self.store.get_record(memory_id)

    def list_memories(
        self,
        category: Optional[MemoryCategory] = None,
        status: Optional[MemoryStatus] = None,
        query: Optional[str] = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List or search memory records with optional full-text query."""
        if query and query.strip():
            return self.retrieval_engine.search(query=query.strip(), category=category, limit=limit)
        return self.store.list_records(category=category, status=status, limit=limit)

    def approve_memory(self, memory_id: str, reviewer: str = "operator") -> Optional[MemoryRecord]:
        """Promote a pending memory record to active status."""
        return self.store.approve_proposal(memory_id, reviewer=reviewer)

    def update_memory(
        self,
        memory_id: str,
        updates: MemoryUpdateRequest,
        actor: str = "operator",
    ) -> Optional[MemoryRecord]:
        """Update an existing memory record."""
        return self.store.update_record(memory_id, updates, actor=actor)

    def revoke_memory(self, memory_id: str, actor: str = "operator", reason: str = "") -> bool:
        """Revoke a memory record, removing it from active recall."""
        return self.store.revoke_record(memory_id, actor=actor, reason=reason)

    def delete_memory(self, memory_id: str, actor: str = "operator") -> bool:
        """Permanently delete a memory record."""
        return self.store.delete_record(memory_id, actor=actor)

    def export_memories(self, format: str = "json") -> str:
        """Export all active memories formatted as JSON or CSV."""
        records = self.store.list_records(status=MemoryStatus.ACTIVE, limit=1000)

        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "key", "category", "value", "sensitivity", "created_at", "expires_at", "provenance"])
            for r in records:
                writer.writerow([r.id, r.key, r.category.value, r.value, r.sensitivity.value, r.created_at, r.expires_at, r.provenance_reason])
            return output.getvalue()

        # Default JSON export
        return json.dumps([r.model_dump() for r in records], indent=2)

    def create_backup(self) -> MemoryBackupInfo:
        """Trigger an online snapshot backup."""
        return self.backup_service.create_backup()

    def list_backups(self) -> list[MemoryBackupInfo]:
        """List existing backups."""
        return self.backup_service.list_backups()

    def restore_backup(self, backup_path: str) -> bool:
        """Restore database from a backup file."""
        return self.backup_service.restore_backup(backup_path)

    def format_planner_prompt_context(self, task_prompt: str) -> str:
        """Format bounded recalled memory context block for task planner prompts."""
        return self.retrieval_engine.format_planner_context(task_prompt=task_prompt)
