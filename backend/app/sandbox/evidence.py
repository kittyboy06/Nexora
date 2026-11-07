"""Immutable Evidence Store for Sandbox Runs."""

import json
from pathlib import Path
from typing import Optional

from backend.app.sandbox.models import SandboxRunResult


class SandboxEvidenceStore:
    """Persists immutable telemetry and execution results for auditing and promotion."""

    def __init__(self, runs_dir: Optional[Path] = None) -> None:
        self.runs_dir = (runs_dir or Path("data/sandbox/runs")).resolve()
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def save_run_result(self, result: SandboxRunResult) -> Path:
        """Save a completed sandbox run result to disk."""
        target_path = self.runs_dir / f"{result.run_id}.json"
        data = result.model_dump()
        target_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return target_path

    def get_run_result(self, run_id: str) -> Optional[SandboxRunResult]:
        """Retrieve a specific sandbox run result by ID."""
        target_path = self.runs_dir / f"{run_id}.json"
        if not target_path.exists():
            return None
        try:
            data = json.loads(target_path.read_text(encoding="utf-8"))
            return SandboxRunResult.model_validate(data)
        except Exception:
            return None

    def list_run_results(self, limit: int = 50) -> list[SandboxRunResult]:
        """List past sandbox runs ordered by modification time descending."""
        if not self.runs_dir.exists():
            return []

        json_files = sorted(
            self.runs_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        results: list[SandboxRunResult] = []
        for p in json_files[:limit]:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                results.append(SandboxRunResult.model_validate(data))
            except Exception:
                continue

        return results

    def delete_run_result(self, run_id: str) -> bool:
        """Delete an evidence record."""
        target_path = self.runs_dir / f"{run_id}.json"
        if target_path.exists():
            target_path.unlink()
            return True
        return False
