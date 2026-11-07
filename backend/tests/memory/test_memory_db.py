"""Unit tests for SQLite Database Manager and FTS5 triggers."""

import sqlite3
import pytest
from pathlib import Path

from backend.app.memory.database import MemoryDatabase, CURRENT_SCHEMA_VERSION


@pytest.fixture
def test_db(tmp_path: Path) -> MemoryDatabase:
    db_file = tmp_path / "test_memory.db"
    return MemoryDatabase(db_path=db_file)


def test_database_initialization(test_db: MemoryDatabase):
    assert test_db.db_path.exists()
    assert test_db.check_integrity() is True

    conn = test_db.get_connection()
    try:
        # Check migration version
        row = conn.execute("SELECT version FROM schema_migrations;").fetchone()
        assert row is not None
        assert row["version"] == CURRENT_SCHEMA_VERSION

        # Check WAL mode
        wal_row = conn.execute("PRAGMA journal_mode;").fetchone()
        assert wal_row[0].lower() == "wal"
    finally:
        conn.close()


def test_transaction_commit_and_rollback(test_db: MemoryDatabase):
    # Test commit
    with test_db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO durable_memory (id, key, category, value, sensitivity, status, created_at, updated_at, version_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("mem_1", "pref:test", "user_preference", "pytest", "LOW", "ACTIVE", "2026-11-07T00:00:00Z", "2026-11-07T00:00:00Z", "hash1"),
        )

    # Verify present
    conn = test_db.get_connection()
    try:
        row = conn.execute("SELECT * FROM durable_memory WHERE id = 'mem_1';").fetchone()
        assert row is not None
        assert row["value"] == "pytest"
    finally:
        conn.close()

    # Test rollback on exception
    with pytest.raises(RuntimeError):
        with test_db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO durable_memory (id, key, category, value, sensitivity, status, created_at, updated_at, version_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("mem_2", "pref:bad", "user_preference", "bad_val", "LOW", "ACTIVE", "2026-11-07T00:00:00Z", "2026-11-07T00:00:00Z", "hash2"),
            )
            raise RuntimeError("Intentional abort")

    # Verify mem_2 does NOT exist
    conn = test_db.get_connection()
    try:
        row = conn.execute("SELECT * FROM durable_memory WHERE id = 'mem_2';").fetchone()
        assert row is None
    finally:
        conn.close()


def test_fts5_triggers_insert_update_delete(test_db: MemoryDatabase):
    # 1. Insert and verify automatic FTS5 indexing
    with test_db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO durable_memory (id, key, category, value, sensitivity, status, created_at, updated_at, version_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("mem_search", "fact:compiler", "project_fact", "Application uses Clang on Windows x64 architecture", "MEDIUM", "ACTIVE", "2026-11-07T00:00:00Z", "2026-11-07T00:00:00Z", "hash_c"),
        )

    conn = test_db.get_connection()
    try:
        # Search for 'Clang' in FTS
        fts_rows = conn.execute("SELECT * FROM memory_fts WHERE memory_fts MATCH 'Clang';").fetchall()
        assert len(fts_rows) == 1
        assert fts_rows[0]["id"] == "mem_search"

        # Search for 'Windows' in FTS
        fts_rows_win = conn.execute("SELECT * FROM memory_fts WHERE memory_fts MATCH 'Windows';").fetchall()
        assert len(fts_rows_win) == 1
    finally:
        conn.close()

    # 2. Update and verify FTS5 re-indexing
    with test_db.transaction() as conn:
        conn.execute(
            "UPDATE durable_memory SET value = ? WHERE id = 'mem_search';",
            ("Application uses MSVC on Windows x64 architecture",),
        )

    conn = test_db.get_connection()
    try:
        # Old term 'Clang' should no longer match
        fts_old = conn.execute("SELECT * FROM memory_fts WHERE memory_fts MATCH 'Clang';").fetchall()
        assert len(fts_old) == 0

        # New term 'MSVC' should match
        fts_new = conn.execute("SELECT * FROM memory_fts WHERE memory_fts MATCH 'MSVC';").fetchall()
        assert len(fts_new) == 1
    finally:
        conn.close()

    # 3. Delete and verify FTS5 removal
    with test_db.transaction() as conn:
        conn.execute("DELETE FROM durable_memory WHERE id = 'mem_search';")

    conn = test_db.get_connection()
    try:
        fts_del = conn.execute("SELECT * FROM memory_fts WHERE memory_fts MATCH 'MSVC';").fetchall()
        assert len(fts_del) == 0
    finally:
        conn.close()
