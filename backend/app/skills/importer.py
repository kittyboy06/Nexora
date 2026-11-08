"""Skill Importer Service with Path-Traversal Hardening and Sanitization."""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any, Optional, Tuple
import yaml

from backend.app.skills.manager import SkillManager
from backend.app.skills.models import (
    SkillBundle,
    SkillManifest,
    SkillPatchRequest,
    SkillProvenance,
)

logger = logging.getLogger("nexora.skills.importer")

SLUG_CLEANER = re.compile(r"[^a-z0-9\-_]+")
FORBIDDEN_ROOTS = {"c:\\windows", "c:\\program files", "c:\\program files (x86)", "\\windows", "/etc", "/usr", "/bin"}


class SkillImportError(Exception):
    """Raised when skill import validation fails."""
    pass


class SkillImporterService:
    """Safely inspects, parses, and imports skill packages from local folders or text payloads."""

    def __init__(self, manager: Optional[SkillManager] = None):
        self.manager = manager or SkillManager()

    def validate_safe_path(self, folder_path: str) -> Path:
        """Ensure input path is a valid directory and outside sensitive system roots."""
        if not folder_path or not folder_path.strip():
            raise SkillImportError("Folder path cannot be empty.")

        try:
            resolved = Path(folder_path.strip()).resolve()
        except Exception as e:
            raise SkillImportError(f"Invalid path structure: {e}")

        if not resolved.exists():
            raise SkillImportError(f"Directory does not exist: {resolved}")

        if not resolved.is_dir():
            raise SkillImportError(f"Path is not a directory: {resolved}")

        # Check against forbidden system roots
        resolved_str = str(resolved).lower()
        for root in FORBIDDEN_ROOTS:
            if resolved_str == root or resolved_str.startswith(root + "\\") or resolved_str.startswith(root + "/"):
                raise SkillImportError(f"Import forbidden from protected system location: {resolved}")

        # Check for filesystem roots (e.g. C:\ or D:\ directly)
        if resolved.parent == resolved:
            raise SkillImportError(f"Import directly from filesystem root is forbidden: {resolved}")

        return resolved

    def parse_markdown_frontmatter(self, content: str) -> Tuple[dict[str, Any], str]:
        """Extract YAML frontmatter between leading --- delimiters if present."""
        lines = content.splitlines(keepends=True)
        if len(lines) >= 3 and lines[0].strip() == "---":
            frontmatter_lines = []
            body_start_idx = -1
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    body_start_idx = i + 1
                    break
                frontmatter_lines.append(lines[i])

            if body_start_idx != -1:
                raw_fm = "".join(frontmatter_lines)
                try:
                    parsed = yaml.safe_load(raw_fm) or {}
                    if isinstance(parsed, dict):
                        body = "".join(lines[body_start_idx:])
                        return parsed, body
                except Exception as e:
                    logger.warning("Failed parsing frontmatter YAML: %s", e)

        return {}, content

    def import_from_folder(
        self, folder_path: str, enable_immediately: bool = False
    ) -> SkillBundle:
        """Import a skill from a local folder containing manifest and instruction markdown."""
        target_dir = self.validate_safe_path(folder_path)

        manifest_data: dict[str, Any] = {}
        instructions_text = ""

        # Check for dedicated manifest file
        manifest_candidates = [
            target_dir / "manifest.json",
            target_dir / "manifest.yaml",
            target_dir / "manifest.yml",
            target_dir / "skill.yaml",
            target_dir / "skill.yml",
            target_dir / "skill.json",
        ]

        for cand in manifest_candidates:
            if cand.exists() and cand.is_file():
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        if cand.suffix == ".json":
                            manifest_data = json.load(f)
                        else:
                            manifest_data = yaml.safe_load(f) or {}
                        if isinstance(manifest_data, dict):
                            break
                except Exception as e:
                    logger.warning("Error reading manifest candidate %s: %s", cand, e)

        # Check for instruction markdown
        instructions_candidates = [
            target_dir / "SKILL.md",
            target_dir / "skill.md",
            target_dir / "instructions.md",
            target_dir / "README.md",
        ]

        found_instructions_file = False
        for icand in instructions_candidates:
            if icand.exists() and icand.is_file():
                try:
                    with open(icand, "r", encoding="utf-8") as f:
                        raw_text = f.read()

                    # Check for frontmatter
                    fm, body = self.parse_markdown_frontmatter(raw_text)
                    if fm and not manifest_data:
                        manifest_data = fm
                    instructions_text = body.strip()
                    found_instructions_file = True
                    break
                except Exception as e:
                    logger.warning("Error reading instructions file %s: %s", icand, e)

        if not found_instructions_file or not instructions_text:
            raise SkillImportError(
                f"No instruction markdown (SKILL.md, instructions.md, README.md) found in {target_dir}"
            )

        # Synthesize / sanitize manifest fields if partially missing
        folder_slug = SLUG_CLEANER.sub("-", target_dir.name.lower()).strip("-") or "imported-skill"
        skill_id = manifest_data.get("id") or folder_slug
        skill_id = SLUG_CLEANER.sub("-", str(skill_id).lower()).strip("-")
        if not skill_id:
            skill_id = "imported-skill"

        name = manifest_data.get("name") or target_dir.name.replace("-", " ").replace("_", " ").title()
        version = manifest_data.get("version") or "1.0.0"
        description = manifest_data.get("description") or f"Imported skill from {target_dir.name}"

        tags = manifest_data.get("tags") or ["imported", "local"]
        if not isinstance(tags, list):
            tags = [str(tags)]

        target_roles = manifest_data.get("target_roles") or []
        if not isinstance(target_roles, list):
            target_roles = [str(target_roles)]

        manifest = SkillManifest(
            id=skill_id,
            name=str(name)[:100],
            version=str(version),
            description=str(description)[:500],
            tags=tags,
            author=str(manifest_data.get("author", "operator")),
            license=str(manifest_data.get("license", "MIT")),
            target_roles=target_roles,
            required_tools=manifest_data.get("required_tools") or [],
            category=str(manifest_data.get("category", "local")),
        )

        content_hash = hashlib.sha256(instructions_text.encode("utf-8")).hexdigest()
        provenance = SkillProvenance(
            source_url=f"local://{target_dir}",
            skill_sha256=content_hash,
            installed_at=datetime.now(timezone.utc).isoformat(),
            reviewer="operator",
        )

        bundle = self.manager.install_bundle(
            manifest=manifest,
            instructions=instructions_text,
            provenance=provenance,
            set_active=True,
        )

        # Fail-closed default: disabled until explicitly enabled or requested
        if not enable_immediately:
            self.manager.patch_skill(manifest.id, SkillPatchRequest(is_enabled=False))
            bundle = self.manager.get_skill(manifest.id, manifest.version) or bundle

        return bundle

    def import_from_paste(
        self,
        manifest_yaml: str,
        instructions: str,
        enable_immediately: bool = False,
        source_note: str = "pasted",
    ) -> SkillBundle:
        """Import a skill directly from pasted YAML/JSON manifest and markdown instructions."""
        if not manifest_yaml or not manifest_yaml.strip():
            raise SkillImportError("Manifest YAML/JSON content cannot be empty.")
        if not instructions or not instructions.strip():
            raise SkillImportError("Instructions Markdown cannot be empty.")

        try:
            parsed = yaml.safe_load(manifest_yaml.strip())
            if not isinstance(parsed, dict):
                raise SkillImportError("Manifest content must parse to a key-value mapping.")
        except Exception as e:
            raise SkillImportError(f"Failed to parse manifest YAML/JSON: {e}")

        try:
            manifest = SkillManifest(**parsed)
        except Exception as e:
            raise SkillImportError(f"Manifest schema validation error: {e}")

        content_hash = hashlib.sha256(instructions.strip().encode("utf-8")).hexdigest()
        provenance = SkillProvenance(
            source_url=f"paste://{source_note}",
            skill_sha256=content_hash,
            installed_at=datetime.now(timezone.utc).isoformat(),
            reviewer="operator",
        )

        bundle = self.manager.install_bundle(
            manifest=manifest,
            instructions=instructions.strip(),
            provenance=provenance,
            set_active=True,
        )

        if not enable_immediately:
            self.manager.patch_skill(manifest.id, SkillPatchRequest(is_enabled=False))
            bundle = self.manager.get_skill(manifest.id, manifest.version) or bundle

        return bundle
