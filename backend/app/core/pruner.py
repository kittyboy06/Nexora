"""Automated Quarantine and Ephemeral Data Pruner (Phase 14).

Enforces strict 24-hour TTL data retention policies for:
- Remote web download quarantines (`data/quarantine/*`).
- Ephemeral inspection artifacts and temporary desktop captures.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Optional

from backend.app.core.config import Settings

logger = logging.getLogger("nexora.core.pruner")

DEFAULT_QUARANTINE_TTL_SECONDS = 24.0 * 3600.0  # 24 Hours


class QuarantinePruner:
    """Manages TTL-based file pruning and directory sanitization for quarantine zones."""

    def __init__(
        self,
        quarantine_dir: Path,
        max_age_seconds: float = DEFAULT_QUARANTINE_TTL_SECONDS,
    ) -> None:
        self.quarantine_dir = quarantine_dir.resolve()
        self.max_age_seconds = max_age_seconds
        self._pruner_task: Optional[asyncio.Task] = None
        self._running = False

    def prune(self, max_age_seconds: Optional[float] = None) -> dict[str, Any]:
        """
        Scan quarantine directory and delete files older than max_age_seconds.
        Safely purges empty directories following file removal.
        """
        cutoff_age = max_age_seconds if max_age_seconds is not None else self.max_age_seconds
        now = time.time()
        scanned_count = 0
        pruned_count = 0
        bytes_freed = 0

        if not self.quarantine_dir.exists():
            return {
                "scanned_count": 0,
                "pruned_count": 0,
                "bytes_freed": 0,
                "status": "directory_not_found",
            }

        # Scan all regular files recursively
        for root, dirs, files in os.walk(self.quarantine_dir, topdown=False):
            root_path = Path(root)
            for fname in files:
                fpath = root_path / fname
                try:
                    scanned_count += 1
                    stat = fpath.stat()
                    file_age = now - stat.st_mtime
                    if file_age >= cutoff_age:
                        f_size = stat.st_size
                        fpath.unlink(missing_ok=True)
                        pruned_count += 1
                        bytes_freed += f_size
                        logger.info("Pruned expired quarantine file: %s (%d bytes)", fpath, f_size)
                except OSError as exc:
                    logger.warning("Error inspecting/deleting quarantine file %s: %s", fpath, exc)

            # Clean empty directories (except root quarantine dir itself)
            if root_path != self.quarantine_dir:
                try:
                    if not any(root_path.iterdir()):
                        root_path.rmdir()
                        logger.debug("Removed empty quarantine subdirectory: %s", root_path)
                except OSError:
                    pass

        logger.info(
            "Quarantine pruning sweep complete: scanned=%d, pruned=%d, freed=%d bytes",
            scanned_count,
            pruned_count,
            bytes_freed,
        )

        return {
            "scanned_count": scanned_count,
            "pruned_count": pruned_count,
            "bytes_freed": bytes_freed,
            "status": "success",
        }

    async def _loop(self, sweep_interval_seconds: float) -> None:
        """Periodic background sweep loop."""
        while self._running:
            try:
                self.prune()
            except Exception as exc:
                logger.error("Unexpected error during scheduled quarantine pruning: %s", exc)
            try:
                await asyncio.sleep(sweep_interval_seconds)
            except asyncio.CancelledError:
                break

    def start_background_sweep(self, sweep_interval_seconds: float = 3600.0) -> None:
        """Launch recurring background pruning sweep task."""
        if self._running:
            return
        self._running = True
        self._pruner_task = asyncio.create_task(self._loop(sweep_interval_seconds))
        logger.info("Quarantine background pruner started (interval=%0.1fs)", sweep_interval_seconds)

    async def stop_background_sweep(self) -> None:
        """Cleanly cancel recurring background pruner task."""
        self._running = False
        if self._pruner_task and not self._pruner_task.done():
            self._pruner_task.cancel()
            try:
                await self._pruner_task
            except asyncio.CancelledError:
                pass
        self._pruner_task = None
        logger.info("Quarantine background pruner stopped.")
