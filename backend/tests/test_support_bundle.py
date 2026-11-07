"""Tests for Sanitized Diagnostics Support Bundle Exporter (Milestone 2)."""

import json
import zipfile
from pathlib import Path
import pytest

from backend.app.cli.doctor import export_support_bundle, get_sanitized_config


def test_export_support_bundle_structure(tmp_path: Path):
    out_zip = tmp_path / "test_bundle.zip"
    bundle_path = export_support_bundle(base_dir=tmp_path, output_zip=out_zip)
    assert bundle_path.exists()
    assert bundle_path.is_file()

    with zipfile.ZipFile(bundle_path, "r") as zf:
        namelist = zf.namelist()
        assert "system_info.json" in namelist
        assert "diagnostics_report.json" in namelist
        assert "component_status.json" in namelist
        assert "sanitized_config.json" in namelist
        assert "recent_logs.log" in namelist

        # Validate JSON parseability
        sys_info = json.loads(zf.read("system_info.json"))
        assert "os_name" in sys_info
        assert "python_version" in sys_info

        diag_report = json.loads(zf.read("diagnostics_report.json"))
        assert "overall_status" in diag_report


def test_support_bundle_secret_scrubbing(tmp_path: Path):
    # Setup mock logs with sensitive secrets
    log_dir = tmp_path / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    raw_log_file = log_dir / "nexora.log"

    sensitive_tokens = [
        "ghp_1234567890abcdef1234567890abcdef1234",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.secret",
        'password="SuperSecretPassword123!"',
        "sk-proj-abcde12345678901234567890",
    ]

    log_content = "INFO 2026-11-07 Starting NEXORA engine\n"
    for tok in sensitive_tokens:
        log_content += f"DEBUG Connecting with credential: {tok}\n"

    raw_log_file.write_text(log_content, encoding="utf-8")

    # Export bundle
    out_zip = tmp_path / "scrubbed_bundle.zip"
    export_support_bundle(base_dir=tmp_path, output_zip=out_zip)

    # Read exported logs from inside zip
    with zipfile.ZipFile(out_zip, "r") as zf:
        exported_logs = zf.read("recent_logs.log").decode("utf-8")

    # Verify zero secrets leaked
    for tok in sensitive_tokens:
        assert tok not in exported_logs

    # Verify replaced with [REDACTED_SECRET]
    assert "[REDACTED_SECRET]" in exported_logs


def test_get_sanitized_config():
    cfg = get_sanitized_config()
    assert isinstance(cfg, dict)
    # Check that any token or password fields are masked
    for k, v in cfg.items():
        if any(sub in k.lower() for sub in ("token", "secret", "password", "key")):
            if v:
                assert v == "[REDACTED_SECRET]"
