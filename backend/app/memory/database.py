"""SQLite connection manager, schema setup, FTS5 virtual tables, and migrations."""

import contextlib
import logging
import sqlite3
import time
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger("nexora.memory.database")

CURRENT_SCHEMA_VERSION = 1

INIT_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS durable_memory (
    id TEXT PRIMARY KEY,
    key TEXT NOT NULL,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    status TEXT NOT NULL,
    provenance_task_id TEXT,
    provenance_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    version_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_category ON durable_memory(category);
CREATE INDEX IF NOT EXISTS idx_memory_status ON durable_memory(status);
CREATE INDEX IF NOT EXISTS idx_memory_key ON durable_memory(key);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    key,
    category,
    value,
    content='durable_memory',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON durable_memory BEGIN
    INSERT INTO memory_fts(rowid, id, key, category, value) VALUES (new.rowid, new.id, new.key, new.category, new.value);
END;

CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON durable_memory BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, id, key, category, value) VALUES('delete', old.rowid, old.id, old.key, old.category, old.value);
END;

CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON durable_memory BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, id, key, category, value) VALUES('delete', old.rowid, old.id, old.key, old.category, old.value);
    INSERT INTO memory_fts(rowid, id, key, category, value) VALUES (new.rowid, new.id, new.key, new.category, new.value);
END;

CREATE TABLE IF NOT EXISTS memory_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    task_id TEXT,
    details TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_memory_id ON memory_audit(memory_id);
"""


class MemoryDatabase:
    """Manages SQLite database initialization, WAL mode, migrations, and transactional execution."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = (db_path or Path("data/memory/nexora_memory.db")).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextlib.contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a transactional database connection that automatically commits or rolls back."""
        conn = self.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Execute initial schema scripts and record migration state."""
        conn = self.get_connection()
        try:
            conn.executescript(INIT_SQL)
            cursor = conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (CURRENT_SCHEMA_VERSION,))
            if not cursor.fetchone():
                now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, now_iso),
                )
                conn.commit()
            logger.info("Memory database initialized at %s (schema v%d)", self.db_path, CURRENT_SCHEMA_VERSION)
        finally:
            conn.close()

    def check_integrity(self) -> bool:
        """Run PRAGMA integrity_check to verify database health."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            return bool(row and row[0] == "ok")
        finally:
            conn.close()
