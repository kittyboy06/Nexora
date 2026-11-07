"""Unit Tests for Quarantine Data Pruner and Log Rotation (Phase 14)."""

import asyncio
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import time
import pytest

from backend.app.core.config import Settings
from backend.app.core.logging import setup_logging
from backend.app.core.pruner import QuarantinePruner


def test_quarantine_pruning_removes_expired_files(tmp_path: Path):
    """Verify files older than TTL are pruned while fresh files are retained."""
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True)

    old_file = quarantine_dir / "old_download.bin"
    old_file.write_bytes(b"A" * 1024)  # 1 KB

    fresh_file = quarantine_dir / "fresh_download.bin"
    fresh_file.write_bytes(b"B" * 512)   # 512 B

    # Set old_file mtime to 48 hours ago
    two_days_ago = time.time() - (48 * 3600)
    os.utime(old_file, (two_days_ago, two_days_ago))

    # Keep fresh_file mtime at current time
    pruner = QuarantinePruner(quarantine_dir=quarantine_dir, max_age_seconds=24 * 3600)
    result = pruner.prune()

    assert result["scanned_count"] == 2
    assert result["pruned_count"] == 1
    assert result["bytes_freed"] == 1024
    assert not old_file.exists()
    assert fresh_file.exists()


def test_quarantine_pruning_cleans_empty_subdirectories(tmp_path: Path):
    """Verify empty subdirectories are purged after expired contents are pruned."""
    quarantine_dir = tmp_path / "quarantine"
    task_subdir = quarantine_dir / "task_12345"
    task_subdir.mkdir(parents=True)

    expired_file = task_subdir / "screenshot.png"
    expired_file.write_bytes(b"PNG_DATA" * 100)

    # Set mtime to 30 hours ago
    past_time = time.time() - (30 * 3600)
    os.utime(expired_file, (past_time, past_time))

    pruner = QuarantinePruner(quarantine_dir=quarantine_dir, max_age_seconds=24 * 3600)
    result = pruner.prune()

    assert result["pruned_count"] == 1
    assert not expired_file.exists()
    assert not task_subdir.exists()
    assert quarantine_dir.exists()


def test_quarantine_pruning_missing_directory_handled(tmp_path: Path):
    """Verify pruning on a nonexistent directory safely returns without error."""
    missing_dir = tmp_path / "nonexistent_dir"
    pruner = QuarantinePruner(quarantine_dir=missing_dir)
    result = pruner.prune()

    assert result["scanned_count"] == 0
    assert result["pruned_count"] == 0
    assert result["status"] == "directory_not_found"


@pytest.mark.asyncio
async def test_quarantine_background_sweep_lifecycle(tmp_path: Path):
    """Verify background sweep starts, executes, and stops cleanly."""
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True)

    pruner = QuarantinePruner(quarantine_dir=quarantine_dir, max_age_seconds=10.0)
    pruner.start_background_sweep(sweep_interval_seconds=0.1)
    assert pruner._running is True
    assert pruner._pruner_task is not None

    await asyncio.sleep(0.2)
    await pruner.stop_background_sweep()
    assert pruner._running is False
    assert pruner._pruner_task is None


def test_log_rotation_configuration(tmp_path: Path):
    """Verify setup_logging configures RotatingFileHandler with 10MB limit and 5 backups."""
    log_file = tmp_path / "logs" / "test_nexora.log"
    settings = Settings(LOG_FILE=str(log_file))

    # Clear root handlers for isolated test
    import logging
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    root.handlers.clear()

    try:
        logger = setup_logging(settings)
        rotating_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating_handlers) == 1
        rh = rotating_handlers[0]
        assert rh.maxBytes == 10 * 1024 * 1024  # 10 MB
        assert rh.backupCount == 5
    finally:
        # Restore old handlers
        for h in root.handlers:
            h.close()
        root.handlers = old_handlers
