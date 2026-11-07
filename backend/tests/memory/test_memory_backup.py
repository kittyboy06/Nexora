"""Unit tests for SQLite Online Backup, Integrity Verification, and Rollback."""

import pytest
from pathlib import Path

from backend.app.memory.backup import MemoryBackupService
from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import MemoryCategory, MemoryProposal
from backend.app.memory.store import DurableMemoryStore


@pytest.fixture
def test_setup(tmp_path: Path):
    db_file = tmp_path / "primary.db"
    backup_dir = tmp_path / "backups"
    db = MemoryDatabase(db_path=db_file)
    store = DurableMemoryStore(database=db)
    backup_svc = MemoryBackupService(database=db, backup_dir=backup_dir)
    return db, store, backup_svc


def test_create_and_list_backups(test_setup):
    db, store, backup_svc = test_setup

    # Insert test records
    store.create_record(
        MemoryProposal(
            key="pref:lang",
            category=MemoryCategory.USER_PREFERENCE,
            value="Python",
            provenance_reason="User pref",
        )
    )
    store.create_record(
        MemoryProposal(
            key="fact:os",
            category=MemoryCategory.PROJECT_FACT,
            value="Windows 11",
            provenance_reason="Host OS",
        )
    )

    # Create backup
    info = backup_svc.create_backup()
    assert info.is_valid is True
    assert info.record_count == 2
    assert Path(info.backup_path).exists()
    assert info.file_size_bytes > 0

    # List backups
    backups = backup_svc.list_backups()
    assert len(backups) == 1
    assert backups[0].backup_path == info.backup_path


def test_restore_and_rollback_flow(test_setup):
    db, store, backup_svc = test_setup

    # 1. State 1: 1 record
    store.create_record(
        MemoryProposal(
            key="pref:format",
            category=MemoryCategory.USER_PREFERENCE,
            value="Markdown",
            provenance_reason="Doc pref",
        )
    )
    backup_info = backup_svc.create_backup()

    # 2. State 2: Add 2 more records and delete State 1 record
    rec2 = store.create_record(
        MemoryProposal(
            key="fact:temp",
            category=MemoryCategory.PROJECT_FACT,
            value="Temporary",
            provenance_reason="temp",
        )
    )
    rec1 = store.get_record_by_key("pref:format")
    store.delete_record(rec1.id)

    # In State 2: pref:format is deleted, only fact:temp exists
    assert store.get_record_by_key("pref:format") is None
    assert store.get_record_by_key("fact:temp") is not None

    # 3. Restore State 1 from backup
    success = backup_svc.restore_backup(backup_info.backup_path)
    assert success is True

    # 4. Verify State 1 is restored!
    restored_rec = store.get_record_by_key("pref:format")
    assert restored_rec is not None
    assert restored_rec.value == "Markdown"
    assert store.get_record_by_key("fact:temp") is None


def test_restore_rejects_corrupted_file(test_setup, tmp_path: Path):
    _, _, backup_svc = test_setup

    bad_file = tmp_path / "corrupt.db"
    bad_file.write_bytes(b"NOT A SQLITE DATABASE CORRUPT DATA")

    with pytest.raises(ValueError, match="Cannot restore from corrupt backup"):
        backup_svc.restore_backup(str(bad_file))
