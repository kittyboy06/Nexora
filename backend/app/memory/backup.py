"""Online backup, integrity checks, and disaster recovery rollback for Memory."""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

from backend.app.memory.database import MemoryDatabase
from backend.app.memory.models import MemoryBackupInfo

logger = logging.getLogger("nexora.memory.backup")


class MemoryBackupService:
    """Manages zero-downtime online SQLite backups and verifiable rollbacks."""

    def __init__(
        self,
        database: MemoryDatabase,
        backup_dir: Optional[Path] = None,
    ) -> None:
        self.db = database
        self.backup_dir = (backup_dir or self.db.db_path.parent / "backups").resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> MemoryBackupInfo:
        """Create a point-in-time snapshot backup using SQLite's online backup engine."""
        timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        backup_file = self.backup_dir / f"nexora_memory_{timestamp_str}.db"

        # 1. Execute online backup
        source_conn = self.db.get_connection()
        dest_conn = sqlite3.connect(str(backup_file))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            source_conn.close()

        # 2. Verify backup integrity
        is_valid = self._verify_file_integrity(backup_file)
        if not is_valid:
            if backup_file.exists():
                backup_file.unlink()
            raise RuntimeError(f"Backup integrity check failed for {backup_file}")

        # 3. Read record count and stats
        record_count = 0
        verify_conn = sqlite3.connect(str(backup_file))
        try:
            cur = verify_conn.execute("SELECT COUNT(*) FROM durable_memory;")
            record_count = cur.fetchone()[0]
        finally:
            verify_conn.close()

        file_size = backup_file.stat().st_size
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        logger.info(
            "Created memory backup at %s (%d records, %d bytes)",
            backup_file,
            record_count,
            file_size,
        )

        return MemoryBackupInfo(
            backup_path=str(backup_file),
            record_count=record_count,
            file_size_bytes=file_size,
            created_at=now_iso,
            is_valid=is_valid,
        )

    def list_backups(self) -> list[MemoryBackupInfo]:
        """List all verified backups ordered by timestamp descending."""
        if not self.backup_dir.exists():
            return []

        backups: list[MemoryBackupInfo] = []
        for p in sorted(self.backup_dir.glob("*.db"), key=lambda f: f.stat().st_mtime, reverse=True):
            is_valid = self._verify_file_integrity(p)
            count = 0
            if is_valid:
                conn = sqlite3.connect(str(p))
                try:
                    cur = conn.execute("SELECT COUNT(*) FROM durable_memory;")
                    count = cur.fetchone()[0]
                except Exception:
                    pass
                finally:
                    conn.close()

            mtime_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))
            backups.append(
                MemoryBackupInfo(
                    backup_path=str(p),
                    record_count=count,
                    file_size_bytes=p.stat().st_size,
                    created_at=mtime_iso,
                    is_valid=is_valid,
                )
            )

        return backups

    def restore_backup(self, backup_path: str) -> bool:
        """Atomically restore the database from a verified backup file."""
        source_path = Path(backup_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Backup file not found: {source_path}")

        # 1. Verify backup file integrity before touching primary database
        if not self._verify_file_integrity(source_path):
            raise ValueError(f"Cannot restore from corrupt backup: {source_path}")

        # 2. Perform online restore from backup to primary database
        backup_conn = sqlite3.connect(str(source_path))
        target_conn = self.db.get_connection()
        try:
            backup_conn.backup(target_conn)
        finally:
            target_conn.close()
            backup_conn.close()

        # 3. Verify primary database health post-restore
        post_ok = self.db.check_integrity()
        if not post_ok:
            raise RuntimeError("Primary database integrity check failed after restore")

        logger.info("Successfully restored memory database from %s", source_path)
        return True

    def _verify_file_integrity(self, file_path: Path) -> bool:
        """Run PRAGMA integrity_check on a specific SQLite file."""
        if not file_path.exists():
            return False
        conn = sqlite3.connect(str(file_path))
        try:
            cur = conn.execute("PRAGMA integrity_check;")
            row = cur.fetchone()
            return bool(row and row[0] == "ok")
        except Exception:
            return False
        finally:
            conn.close()
