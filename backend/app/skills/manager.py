"""Local Skill Storage, Registry, and Lifecycle Manager."""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
from typing import Optional

from backend.app.core.config import get_settings
from backend.app.skills.models import (
    SkillBundle,
    SkillManifest,
    SkillPatchRequest,
    SkillProvenance,
    SkillSummary,
)

logger = logging.getLogger("nexora.skills.manager")

ID_REGEX = re.compile(r"^[a-z0-9\-_]+$")
VERSION_REGEX = re.compile(r"^\d+\.\d+\.\d+$")


class SkillManager:
    """Manages versioned skill bundles, local registry persistence, and cryptographic verification."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_settings().get_skills_data_dir()
        self.registry_file = self.base_dir / "registry.json"
        # In-memory storage: [skill_id][version] -> SkillBundle
        self._bundles: dict[str, dict[str, SkillBundle]] = {}
        self._registry_state: dict[str, dict] = {}
        self._ensure_storage()
        self.reload()

    def _ensure_storage(self) -> None:
        """Create base directory and initialize empty registry.json if missing."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            self._save_registry_state({})

    def _load_registry_state(self) -> dict[str, dict]:
        """Read registry.json tracking active versions and enabled flags."""
        if not self.registry_file.exists():
            return {}
        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to parse registry.json; re-initializing: %s", e)
            return {}

    def _save_registry_state(self, state: dict[str, dict]) -> None:
        """Persist registry.json."""
        self._registry_state = state
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error("Failed to write registry.json: %s", e)

    def reload(self) -> None:
        """Scan base_dir and reload all skill bundles into memory."""
        self._bundles.clear()
        self._registry_state = self._load_registry_state()

        if not self.base_dir.exists():
            return

        for skill_dir in self.base_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue

            skill_id = skill_dir.name
            if not ID_REGEX.match(skill_id):
                continue

            self._bundles[skill_id] = {}

            for version_dir in skill_dir.iterdir():
                if not version_dir.is_dir() or version_dir.name.startswith("."):
                    continue

                version = version_dir.name
                if not VERSION_REGEX.match(version):
                    continue

                bundle = self._load_bundle_from_disk(skill_id, version, version_dir)
                if bundle:
                    self._bundles[skill_id][version] = bundle

        # Reconcile registry state
        self._reconcile_registry()

    def _load_bundle_from_disk(
        self, skill_id: str, version: str, version_dir: Path
    ) -> Optional[SkillBundle]:
        """Safely parse manifest, markdown, and provenance from a version bundle directory."""
        manifest_path = version_dir / "manifest.json"
        skill_md_path = version_dir / "SKILL.md"
        provenance_path = version_dir / "provenance.json"

        # Check manifest
        if not manifest_path.exists():
            logger.warning("Missing manifest.json in %s", version_dir)
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest = SkillManifest(**manifest_data)
        except Exception as e:
            logger.warning("Failed to parse manifest.json in %s: %s", version_dir, e)
            # Create a broken bundle placeholder for UI reporting
            return SkillBundle(
                manifest=SkillManifest(
                    id=skill_id,
                    name=skill_id,
                    version=version,
                    description=f"Corrupted manifest: {e}",
                ),
                provenance=SkillProvenance(
                    source_url="unknown",
                    skill_sha256="",
                ),
                instructions="",
                is_enabled=False,
                is_active_version=False,
                is_valid=False,
                validation_error=f"Corrupted manifest.json: {e}",
            )

        # Check instructions
        if not skill_md_path.exists():
            return SkillBundle(
                manifest=manifest,
                provenance=SkillProvenance(source_url="unknown", skill_sha256=""),
                instructions="",
                is_enabled=False,
                is_active_version=False,
                is_valid=False,
                validation_error="Missing SKILL.md file",
            )

        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                instructions = f.read()
        except Exception as e:
            return SkillBundle(
                manifest=manifest,
                provenance=SkillProvenance(source_url="unknown", skill_sha256=""),
                instructions="",
                is_enabled=False,
                is_active_version=False,
                is_valid=False,
                validation_error=f"Cannot read SKILL.md: {e}",
            )

        # Calculate actual hash
        actual_hash = hashlib.sha256(instructions.encode("utf-8")).hexdigest()

        # Check provenance
        if provenance_path.exists():
            try:
                with open(provenance_path, "r", encoding="utf-8") as f:
                    prov_data = json.load(f)
                provenance = SkillProvenance(**prov_data)
            except Exception as e:
                provenance = SkillProvenance(
                    source_url="local",
                    skill_sha256=actual_hash,
                )
        else:
            provenance = SkillProvenance(
                source_url="local",
                skill_sha256=actual_hash,
            )

        # Integrity check
        is_valid = True
        validation_error = None
        if provenance.skill_sha256 and provenance.skill_sha256 != actual_hash:
            is_valid = False
            validation_error = (
                f"SHA-256 hash mismatch: expected {provenance.skill_sha256[:10]}..., "
                f"computed {actual_hash[:10]}..."
            )

        return SkillBundle(
            manifest=manifest,
            provenance=provenance,
            instructions=instructions,
            is_enabled=True,
            is_active_version=True,
            is_valid=is_valid,
            validation_error=validation_error,
        )

    def _reconcile_registry(self) -> None:
        """Synchronize in-memory enabled and active_version flags with registry.json."""
        state = dict(self._registry_state)
        updated = False

        for skill_id, versions in self._bundles.items():
            if not versions:
                continue

            entry = state.get(skill_id)
            if not entry:
                # Default: latest version is active, enabled by default
                latest_version = sorted(versions.keys(), reverse=True)[0]
                entry = {
                    "is_enabled": True,
                    "active_version": latest_version,
                }
                state[skill_id] = entry
                updated = True

            active_ver = entry.get("active_version")
            if active_ver not in versions:
                # Fallback to highest version available
                active_ver = sorted(versions.keys(), reverse=True)[0]
                entry["active_version"] = active_ver
                updated = True

            is_enabled = entry.get("is_enabled", True)

            for ver, bundle in versions.items():
                bundle.is_enabled = is_enabled
                bundle.is_active_version = ver == active_ver

        if updated:
            self._save_registry_state(state)

    def list_skills(
        self, enabled_only: bool = False, role: Optional[str] = None
    ) -> list[SkillSummary]:
        """List active version of all installed skills, optionally filtered."""
        results: list[SkillSummary] = []
        for skill_id, versions in self._bundles.items():
            for ver, bundle in versions.items():
                if not bundle.is_active_version:
                    continue
                if enabled_only and not bundle.is_enabled:
                    continue
                if role and bundle.manifest.target_roles:
                    if role not in bundle.manifest.target_roles:
                        continue
                results.append(SkillSummary.from_bundle(bundle))

        return sorted(results, key=lambda s: s.id)

    def get_skill(
        self, skill_id: str, version: Optional[str] = None
    ) -> Optional[SkillBundle]:
        """Retrieve a specific bundle by skill_id and optional version."""
        versions = self._bundles.get(skill_id)
        if not versions:
            return None

        if version:
            return versions.get(version)

        # Return active version
        for bundle in versions.values():
            if bundle.is_active_version:
                return bundle

        # Fallback to first available
        return next(iter(versions.values())) if versions else None

    def list_skill_versions(self, skill_id: str) -> list[SkillSummary]:
        """Return all installed versions for a given skill_id."""
        versions = self._bundles.get(skill_id)
        if not versions:
            return []
        return [SkillSummary.from_bundle(b) for b in versions.values()]

    def install_bundle(
        self,
        manifest: SkillManifest,
        instructions: str,
        provenance: Optional[SkillProvenance] = None,
        set_active: bool = True,
    ) -> SkillBundle:
        """Safely write a new skill bundle to disk and register it."""
        if not ID_REGEX.match(manifest.id):
            raise ValueError(f"Invalid skill id format: {manifest.id}")
        if not VERSION_REGEX.match(manifest.version):
            raise ValueError(f"Invalid skill version format: {manifest.version}")

        # Compute instructions hash
        content_hash = hashlib.sha256(instructions.encode("utf-8")).hexdigest()

        if provenance is None:
            provenance = SkillProvenance(
                source_url="local",
                skill_sha256=content_hash,
                installed_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            provenance.skill_sha256 = content_hash

        # Create destination directory
        target_dir = self.base_dir / manifest.id / manifest.version
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = target_dir / "manifest.json"
        skill_md_path = target_dir / "SKILL.md"
        provenance_path = target_dir / "provenance.json"

        # Write files
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))

        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(instructions)

        with open(provenance_path, "w", encoding="utf-8") as f:
            f.write(provenance.model_dump_json(indent=2))

        # Update registry state
        state = dict(self._registry_state)
        skill_entry = state.get(manifest.id, {"is_enabled": True, "active_version": manifest.version})
        if set_active:
            skill_entry["active_version"] = manifest.version
        state[manifest.id] = skill_entry
        self._save_registry_state(state)

        # Reload memory
        self.reload()

        installed = self.get_skill(manifest.id, manifest.version)
        if not installed:
            raise RuntimeError(f"Failed to reload installed skill {manifest.id} v{manifest.version}")
        return installed

    def patch_skill(self, skill_id: str, patch: SkillPatchRequest) -> Optional[SkillBundle]:
        """Update enabled state or active version."""
        if skill_id not in self._bundles:
            return None

        state = dict(self._registry_state)
        entry = state.get(skill_id, {})

        if patch.is_enabled is not None:
            entry["is_enabled"] = patch.is_enabled

        if patch.active_version is not None:
            if patch.active_version not in self._bundles[skill_id]:
                raise ValueError(
                    f"Version {patch.active_version} is not installed for skill {skill_id}"
                )
            entry["active_version"] = patch.active_version

        state[skill_id] = entry
        self._save_registry_state(state)
        self.reload()
        return self.get_skill(skill_id)

    def delete_skill(self, skill_id: str, version: Optional[str] = None) -> bool:
        """Delete a specific version bundle or the entire skill."""
        if skill_id not in self._bundles:
            return False

        if version:
            # Delete specific version
            target_ver_dir = self.base_dir / skill_id / version
            if target_ver_dir.exists():
                shutil.rmtree(target_ver_dir, ignore_errors=True)

            # Check if any version remains
            skill_dir = self.base_dir / skill_id
            remaining_subdirs = [
                d for d in skill_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
            ] if skill_dir.exists() else []

            if not remaining_subdirs:
                shutil.rmtree(skill_dir, ignore_errors=True)
                state = dict(self._registry_state)
                state.pop(skill_id, None)
                self._save_registry_state(state)
            else:
                # Pick a new active version if the deleted one was active
                state = dict(self._registry_state)
                entry = state.get(skill_id, {})
                if entry.get("active_version") == version:
                    entry["active_version"] = remaining_subdirs[0].name
                    state[skill_id] = entry
                    self._save_registry_state(state)
        else:
            # Delete entire skill
            skill_dir = self.base_dir / skill_id
            if skill_dir.exists():
                shutil.rmtree(skill_dir, ignore_errors=True)
            state = dict(self._registry_state)
            state.pop(skill_id, None)
            self._save_registry_state(state)

        self.reload()
        return True

    def verify_integrity(self, skill_id: str, version: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """Verify the cryptographic SHA-256 integrity of a skill on disk."""
        bundle = self.get_skill(skill_id, version)
        if not bundle:
            return False, f"Skill {skill_id} not found"

        skill_md_path = self.base_dir / bundle.manifest.id / bundle.manifest.version / "SKILL.md"
        if not skill_md_path.exists():
            return False, "SKILL.md missing on disk"

        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()
            computed_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if computed_hash != bundle.provenance.skill_sha256:
                return False, f"Hash mismatch: expected {bundle.provenance.skill_sha256}, got {computed_hash}"
            return True, None
        except Exception as e:
            return False, f"Failed to read SKILL.md: {e}"
