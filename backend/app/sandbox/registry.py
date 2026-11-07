"""Versioned Catalog and Lifecycle Registry for Approved Generated Tools."""

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from backend.app.sandbox.models import (
    GeneratedToolManifest,
    GeneratedToolProposal,
    GeneratedToolRecord,
    SandboxRunResult,
    SandboxRunStatus,
)


class GeneratedToolRegistry:
    """Manages persistent, versioned storage, promotion, rollback, and enablement of generated tools."""

    def __init__(self, catalog_dir: Optional[Path] = None) -> None:
        self.catalog_dir = (catalog_dir or Path("data/tools/generated")).resolve()
        self.catalog_dir.mkdir(parents=True, exist_ok=True)

    def _tool_dir(self, tool_name: str) -> Path:
        return self.catalog_dir / tool_name

    def _meta_path(self, tool_name: str) -> Path:
        return self._tool_dir(tool_name) / "meta.json"

    def _read_meta(self, tool_name: str) -> dict[str, Any]:
        meta_file = self._meta_path(tool_name)
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"active_version": "1.0.0", "is_enabled": True}

    def _write_meta(self, tool_name: str, meta: dict[str, Any]) -> None:
        meta_file = self._meta_path(tool_name)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def promote(
        self,
        proposal: GeneratedToolProposal,
        evidence: SandboxRunResult,
        reviewer: str = "operator",
        version: Optional[str] = None,
    ) -> GeneratedToolRecord:
        """Promote a validated proposal with proven sandbox trial evidence to the versioned catalog."""
        # Verification 1: Evidence must prove sandbox test pass
        if evidence.status not in (SandboxRunStatus.TESTS_PASSED, SandboxRunStatus.EXECUTION_SUCCESS):
            raise ValueError(
                f"Cannot promote tool '{proposal.name}': trial run status was '{evidence.status.value}', expected TESTS_PASSED"
            )

        # Verification 2: Bit-for-bit SHA256 match
        current_sha256 = hashlib.sha256(proposal.code.encode("utf-8")).hexdigest()
        if evidence.source_sha256 != current_sha256:
            raise ValueError(
                f"Source code hash mismatch: trial evidence hash ({evidence.source_sha256[:8]}) does not match proposal ({current_sha256[:8]})"
            )

        tool_dir = self._tool_dir(proposal.name)
        tool_dir.mkdir(parents=True, exist_ok=True)

        meta = self._read_meta(proposal.name)
        target_version = version or meta.get("active_version", "1.0.0")

        # If this version already exists, auto-increment patch version
        version_dir = tool_dir / target_version
        if version_dir.exists() and not version:
            parts = target_version.split(".")
            if len(parts) == 3 and parts[-1].isdigit():
                parts[-1] = str(int(parts[-1]) + 1)
                target_version = ".".join(parts)
                version_dir = tool_dir / target_version

        version_dir.mkdir(parents=True, exist_ok=True)

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Write tool.py
        code_file = version_dir / "tool.py"
        code_file.write_text(proposal.code, encoding="utf-8")

        # Create Manifest
        manifest = GeneratedToolManifest(
            name=proposal.name,
            version=target_version,
            description=proposal.description,
            input_schema=proposal.input_schema,
            output_schema=proposal.output_schema,
            test_cases=proposal.test_cases,
            source_sha256=current_sha256,
            created_at=now_iso,
        )
        manifest_file = version_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")

        # Audit History
        audit_entry = {
            "action": "PROMOTE",
            "version": target_version,
            "reviewer": reviewer,
            "evidence_run_id": evidence.run_id,
            "source_sha256": current_sha256,
            "timestamp": now_iso,
        }
        audit_file = version_dir / "audit.json"
        audit_history: list[dict[str, Any]] = [audit_entry]
        audit_file.write_text(json.dumps(audit_history, indent=2), encoding="utf-8")

        # Update meta.json
        meta["active_version"] = target_version
        meta["is_enabled"] = True
        self._write_meta(proposal.name, meta)

        return GeneratedToolRecord(
            manifest=manifest,
            code=proposal.code,
            is_enabled=True,
            audit_history=audit_history,
        )

    def get_tool(self, tool_name: str, version: Optional[str] = None) -> Optional[GeneratedToolRecord]:
        """Fetch a generated tool record by name and version (or active version)."""
        tool_dir = self._tool_dir(tool_name)
        if not tool_dir.exists():
            return None

        meta = self._read_meta(tool_name)
        target_version = version or meta.get("active_version", "1.0.0")
        version_dir = tool_dir / target_version

        if not version_dir.exists():
            return None

        manifest_file = version_dir / "manifest.json"
        code_file = version_dir / "tool.py"
        audit_file = version_dir / "audit.json"

        if not manifest_file.exists() or not code_file.exists():
            return None

        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            manifest = GeneratedToolManifest.model_validate(manifest_data)
            code = code_file.read_text(encoding="utf-8")
            audit_history = []
            if audit_file.exists():
                audit_history = json.loads(audit_file.read_text(encoding="utf-8"))

            return GeneratedToolRecord(
                manifest=manifest,
                code=code,
                is_enabled=meta.get("is_enabled", True),
                audit_history=audit_history,
            )
        except Exception:
            return None

    def list_tools(self) -> list[GeneratedToolRecord]:
        """List all registered generated tools with their currently active version."""
        records: list[GeneratedToolRecord] = []
        if not self.catalog_dir.exists():
            return records

        for tool_path in self.catalog_dir.iterdir():
            if tool_path.is_dir():
                tool_rec = self.get_tool(tool_path.name)
                if tool_rec:
                    records.append(tool_rec)

        return sorted(records, key=lambda r: r.manifest.name)

    def list_versions(self, tool_name: str) -> list[str]:
        """List all available versions for a given tool name."""
        tool_dir = self._tool_dir(tool_name)
        if not tool_dir.exists():
            return []

        versions: list[str] = []
        for v_path in tool_dir.iterdir():
            if v_path.is_dir() and (v_path / "manifest.json").exists():
                versions.append(v_path.name)

        return sorted(versions)

    def set_enabled(self, tool_name: str, is_enabled: bool) -> bool:
        """Enable or disable an existing generated tool."""
        tool_dir = self._tool_dir(tool_name)
        if not tool_dir.exists():
            return False

        meta = self._read_meta(tool_name)
        meta["is_enabled"] = is_enabled
        self._write_meta(tool_name, meta)
        return True

    def rollback(self, tool_name: str, target_version: str) -> bool:
        """Roll back the active version of a generated tool to an earlier version."""
        tool_dir = self._tool_dir(tool_name)
        version_dir = tool_dir / target_version
        if not version_dir.exists() or not (version_dir / "manifest.json").exists():
            return False

        meta = self._read_meta(tool_name)
        old_version = meta.get("active_version")
        meta["active_version"] = target_version
        self._write_meta(tool_name, meta)

        # Append rollback event to target version audit log
        audit_file = version_dir / "audit.json"
        audit_history: list[dict[str, Any]] = []
        if audit_file.exists():
            try:
                audit_history = json.loads(audit_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        audit_history.append({
            "action": "ROLLBACK",
            "from_version": old_version,
            "to_version": target_version,
            "timestamp": now_iso,
        })
        audit_file.write_text(json.dumps(audit_history, indent=2), encoding="utf-8")
        return True

    def delete_tool(self, tool_name: str) -> bool:
        """Completely remove a generated tool and all its versions from the catalog."""
        tool_dir = self._tool_dir(tool_name)
        if tool_dir.exists():
            shutil.rmtree(tool_dir, ignore_errors=True)
            return True
        return False
