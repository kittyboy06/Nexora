"""SQLite connection manager, schema setup, and migrations for NEXORA Scheduler."""

import contextlib
import logging
import sqlite3
from pathlib import Path
from typing import Generator

logger = logging.getLogger("nexora.scheduler.database")

INIT_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prompt_template TEXT NOT NULL,
    model_profile_id TEXT,
    trigger_type TEXT NOT NULL,
    trigger_expression TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL,
    missed_run_policy TEXT NOT NULL,
    concurrency_policy TEXT NOT NULL,
    max_instances INTEGER NOT NULL DEFAULT 1,
    retry_grace_seconds INTEGER NOT NULL DEFAULT 300,
    next_run_at TEXT,
    last_run_at TEXT,
    template_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_runs (
    run_id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL,
    task_id TEXT,
    run_key TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    dispatched_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT,
    FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON schedules(next_run_at) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_schedules_status ON schedules(status);
CREATE INDEX IF NOT EXISTS idx_schedule_runs_schedule_id ON schedule_runs(schedule_id);
CREATE INDEX IF NOT EXISTS idx_schedule_runs_status ON schedule_runs(status);
CREATE INDEX IF NOT EXISTS idx_schedule_runs_scheduled_for ON schedule_runs(scheduled_for);
"""


class SchedulerDatabase:
    """Manages SQLite connections and schema initialization in WAL mode."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Apply schema and set WAL mode."""
        with self.get_connection() as conn:
            conn.executescript(INIT_SQL)
        logger.info("Initialized Scheduler SQLite database at %s", self.db_path)

    @contextlib.contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a configured SQLite connection with row factory and WAL pragmas."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode; transactions handled explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()
