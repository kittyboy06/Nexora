"""Quarantine Download Manager for Isolated File Handling."""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import httpx

from backend.app.research.engines.http import DEFAULT_HEADERS
from backend.app.research.models import QuarantineItem
from backend.app.research.policy import DomainPolicy, SsrfSecurityError, validate_url_against_ssrf
from backend.app.research.sanitizer import sanitize_quarantine_filename

logger = logging.getLogger(__name__)


class QuarantineManager:
    """Manages secure, isolated file downloads into data/quarantine/<task_id>/."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (Path("data") / "quarantine")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _task_dir(self, task_id: str) -> Path:
        p = self.base_dir / task_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _manifest_file(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "manifest.json"

    def _load_manifest(self, task_id: str) -> list[dict]:
        mf = self._manifest_file(task_id)
        if not mf.exists():
            return []
        try:
            return json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_manifest(self, task_id: str, items: list[dict]) -> None:
        mf = self._manifest_file(task_id)
        mf.write_text(json.dumps(items, indent=2), encoding="utf-8")

    async def download_file(
        self,
        task_id: str,
        url: str,
        filename: Optional[str] = None,
        policy: Optional[DomainPolicy] = None,
    ) -> QuarantineItem:
        """Download remote asset into task quarantine directory with SHA-256 and size verification."""
        pol = policy or DomainPolicy()
        validated_url = validate_url_against_ssrf(url, pol)

        # Determine target safe filename
        if not filename or not filename.strip():
            parsed_path = urlparse(validated_url).path
            guessed_name = Path(parsed_path).name or "download.bin"
        else:
            guessed_name = filename.strip()

        safe_name = sanitize_quarantine_filename(guessed_name)
        task_folder = self._task_dir(task_id)
        dest_path = task_folder / safe_name

        hasher = hashlib.sha256()
        total_bytes = 0
        content_type = "application/octet-stream"

        async with httpx.AsyncClient(
            timeout=pol.timeout_seconds,
            follow_redirects=False,
            headers=DEFAULT_HEADERS,
        ) as client:
            current_url = validated_url
            redirect_count = 0
            while True:
                validate_url_against_ssrf(current_url, pol)
                async with client.stream("GET", current_url) as resp:
                    if resp.is_redirect:
                        redirect_count += 1
                        if redirect_count > pol.max_redirects:
                            raise SsrfSecurityError(
                                f"Too many redirects ({redirect_count} > {pol.max_redirects}) for URL '{url}'."
                            )
                        location = resp.headers.get("location")
                        if not location:
                            raise SsrfSecurityError("Redirect encountered without Location header.")
                        current_url = str(httpx.URL(current_url).join(location))
                        continue

                    if resp.status_code != 200:
                        raise RuntimeError(f"Download failed with HTTP status {resp.status_code}.")

                    content_type = resp.headers.get("content-type", content_type)

                    try:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.aiter_bytes():
                                total_bytes += len(chunk)
                                if total_bytes > pol.max_response_bytes:
                                    raise SsrfSecurityError(
                                        f"Downloaded file exceeded maximum size ({total_bytes} > {pol.max_response_bytes} bytes)."
                                    )
                                hasher.update(chunk)
                                f.write(chunk)
                    except Exception:
                        dest_path.unlink(missing_ok=True)
                        raise
                    validated_url = current_url
                    break

        sha256_hash = hasher.hexdigest()
        now_iso = datetime.now(timezone.utc).isoformat()

        item = QuarantineItem(
            task_id=task_id,
            filename=safe_name,
            original_url=validated_url,
            file_size=total_bytes,
            content_type=content_type,
            sha256_hash=sha256_hash,
            quarantine_path=str(dest_path),
            downloaded_at=now_iso,
        )

        # Update manifest
        manifest = self._load_manifest(task_id)
        # Replace if same filename exists
        manifest = [m for m in manifest if m.get("filename") != safe_name]
        manifest.append(item.model_dump())
        self._save_manifest(task_id, manifest)

        logger.info(
            "Quarantined download '%s' for task '%s' (%d bytes, sha256=%s)",
            safe_name,
            task_id,
            total_bytes,
            sha256_hash[:12],
        )
        return item

    def list_quarantined_files(self, task_id: str) -> list[QuarantineItem]:
        """List all quarantined files for a given task."""
        manifest = self._load_manifest(task_id)
        items: list[QuarantineItem] = []
        for m in manifest:
            try:
                items.append(QuarantineItem.model_validate(m))
            except Exception as e:
                logger.warning("Failed parsing quarantine manifest entry: %s", e)
        return items

    def delete_quarantined_file(self, task_id: str, filename: str) -> bool:
        """Remove a quarantined file and update manifest."""
        safe_name = sanitize_quarantine_filename(filename)
        dest = self._task_dir(task_id) / safe_name
        dest.unlink(missing_ok=True)

        manifest = self._load_manifest(task_id)
        updated = [m for m in manifest if m.get("filename") != safe_name]
        self._save_manifest(task_id, updated)
        return True
