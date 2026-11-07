"""Research Evidence Store for Immutable Provenance Records."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Optional
import uuid

from backend.app.research.models import FetchResult, ResearchEvidence

logger = logging.getLogger(__name__)


class ResearchEvidenceStore:
    """Persists and retrieves structured research evidence artifacts partitioned by task_id."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (Path("data") / "research")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _task_dir(self, task_id: str) -> Path:
        p = self.base_dir / task_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def record_evidence(
        self,
        task_id: str,
        fetch_result: FetchResult,
    ) -> ResearchEvidence:
        """Create and persist an immutable evidence record from a FetchResult."""
        evidence_id = f"ev_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        snippet = fetch_result.content[:500]
        if len(fetch_result.content) > 500:
            snippet += "..."

        evidence = ResearchEvidence(
            evidence_id=evidence_id,
            task_id=task_id,
            url=fetch_result.url,
            title=fetch_result.title,
            timestamp=now_iso,
            content_snippet=snippet,
            content_hash=fetch_result.content_hash,
            citations=fetch_result.citations,
            engine=fetch_result.engine,
            screenshot_path=fetch_result.screenshot_path,
        )

        dest_file = self._task_dir(task_id) / f"{evidence_id}.json"
        dest_file.write_text(json.dumps(evidence.model_dump(), indent=2), encoding="utf-8")
        logger.info("Recorded research evidence '%s' for task '%s' (source: %s)", evidence_id, task_id, fetch_result.url)
        return evidence

    def list_evidence(self, task_id: str) -> list[ResearchEvidence]:
        """List all recorded research evidence artifacts for a given task."""
        tdir = self.base_dir / task_id
        if not tdir.exists():
            return []

        results: list[ResearchEvidence] = []
        for f in tdir.glob("ev_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append(ResearchEvidence.model_validate(data))
            except Exception as e:
                logger.warning("Failed to load evidence file '%s': %s", f, e)

        # Sort descending by timestamp
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results

    def get_evidence(self, task_id: str, evidence_id: str) -> Optional[ResearchEvidence]:
        """Load a specific evidence record."""
        target = self.base_dir / task_id / f"{evidence_id}.json"
        if not target.exists():
            return None
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            return ResearchEvidence.model_validate(data)
        except Exception:
            return None
