"""Capture Broker, Visual Redaction and Screenshot Evidence Management."""

from datetime import datetime, timezone, timedelta
import hashlib
import io
import logging
import os
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.models import (
    ScreenshotEvidence,
    TargetWindowBinding,
    UIElementNode,
)

logger = logging.getLogger("nexora.desktop.capture")


class CaptureBroker:
    """Acquires, redacts, hashes, and manages short-lived desktop verification screenshots."""

    def __init__(self, adapter: DesktopAdapter, storage_dir: Path) -> None:
        self.adapter = adapter
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._evidence_records: list[ScreenshotEvidence] = []

    def capture_and_redact(
        self,
        binding: TargetWindowBinding,
        task_id: str = "default_task",
    ) -> ScreenshotEvidence:
        """Capture window rect, blackout sensitive password controls, and persist evidence."""
        raw_bytes, orig_w, orig_h = self.adapter.capture_window(binding.hwnd)

        # Open image with Pillow
        try:
            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        except Exception as e:
            logger.debug("Creating fallback RGB canvas for raw capture: %s", e)
            image = Image.new("RGB", (orig_w or 800, orig_h or 600), color=(30, 30, 30))

        # Inspect tree to discover sensitive coordinate regions to redact
        tree = self.adapter.inspect_tree(binding.hwnd)
        sensitive_nodes = self._find_sensitive_nodes(tree)

        draw = ImageDraw.Draw(image)
        is_redacted = False

        for node in sensitive_nodes:
            # Calculate coordinates relative to window bounds
            rel_x1 = max(0, node.bounding_rect.x - binding.bounds.x)
            rel_y1 = max(0, node.bounding_rect.y - binding.bounds.y)
            rel_x2 = min(image.width, rel_x1 + node.bounding_rect.width)
            rel_y2 = min(image.height, rel_y1 + node.bounding_rect.height)

            if rel_x2 > rel_x1 and rel_y2 > rel_y1:
                draw.rectangle([rel_x1, rel_y1, rel_x2, rel_y2], fill="black")
                is_redacted = True
                logger.info(
                    "Redacted sensitive element '%s' [%s, %s, %s, %s]",
                    node.name or node.automation_id,
                    rel_x1, rel_y1, rel_x2, rel_y2
                )

        # Encode to PNG buffer
        out_buf = io.BytesIO()
        image.save(out_buf, format="PNG")
        final_bytes = out_buf.getvalue()

        # Compute deterministic SHA-256
        sha256_hash = hashlib.sha256(final_bytes).hexdigest()
        image_id = f"snap_{sha256_hash[:12]}"

        # Write to task quarantine directory
        task_dir = self.storage_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        file_path = task_dir / f"{image_id}.png"
        file_path.write_bytes(final_bytes)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=24)

        record = ScreenshotEvidence(
            image_id=image_id,
            task_id=task_id,
            hwnd=binding.hwnd,
            file_path=str(file_path),
            sha256_hash=sha256_hash,
            width=image.width,
            height=image.height,
            is_redacted=is_redacted,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
        )

        self._evidence_records.append(record)
        return record

    def list_evidence(self, task_id: Optional[str] = None) -> list[ScreenshotEvidence]:
        """List captured screenshot evidence, optionally filtered by task ID."""
        if task_id:
            return [e for e in self._evidence_records if e.task_id == task_id]
        return list(self._evidence_records)

    def get_evidence(self, image_id: str) -> Optional[ScreenshotEvidence]:
        """Retrieve screenshot evidence metadata by image ID."""
        return next((e for e in self._evidence_records if e.image_id == image_id), None)

    def cleanup_expired(self, now: Optional[datetime] = None) -> int:
        """Purge screenshot files that have passed their expiration timestamp."""
        current_time = now or datetime.now(timezone.utc)
        purged_count = 0
        retained: list[ScreenshotEvidence] = []

        for record in self._evidence_records:
            try:
                exp_dt = datetime.fromisoformat(record.expires_at)
                if exp_dt <= current_time:
                    p = Path(record.file_path)
                    if p.exists():
                        p.unlink()
                    purged_count += 1
                else:
                    retained.append(record)
            except Exception as e:
                logger.warning("Failed processing expiry for %s: %s", record.image_id, e)
                retained.append(record)

        self._evidence_records = retained
        return purged_count

    def _find_sensitive_nodes(self, node: UIElementNode) -> list[UIElementNode]:
        """Recursively collect nodes that represent passwords or sensitive credentials."""
        results: list[UIElementNode] = []
        is_sensitive = (
            node.is_password
            or "password" in node.name.lower()
            or "password" in node.automation_id.lower()
            or "secure" in node.control_type.lower()
        )
        if is_sensitive:
            results.append(node)

        for child in node.children:
            results.extend(self._find_sensitive_nodes(child))
        return results
