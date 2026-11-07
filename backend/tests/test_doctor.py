"""Unit tests for the NEXORA Pre-Flight Diagnostics Doctor."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.app.cli.doctor import (
    check_dotnet_environment,
    check_ollama_service,
    check_python_environment,
    check_storage_and_wal,
    check_windows_capabilities,
    run_all_checks,
)


def test_check_python_environment():
    res = check_python_environment()
    assert res.status == "PASS"
    assert "Python" in res.message
    assert "version" in res.details


def test_check_dotnet_environment():
    res = check_dotnet_environment()
    # On this machine, dotnet.exe is present in LocalAppData
    assert res.status in ("PASS", "WARN")
    if res.status == "PASS":
        assert "version" in res.details
        assert "path" in res.details


def test_check_ollama_service_unreachable():
    # Test against closed port
    res = check_ollama_service(base_url="http://127.0.0.1:54321")
    assert res.status == "WARN"
    assert "unreachable" in res.message


def test_check_ollama_service_mock_models():
    mock_response = io.BytesIO(b'{"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2"}]}')
    mock_cm = MagicMock()
    mock_cm.status = 200
    mock_cm.read.return_value = mock_response.getvalue()
    mock_cm.__enter__.return_value = mock_cm

    with patch("urllib.request.urlopen", return_value=mock_cm):
        res = check_ollama_service("http://localhost:11434")
        assert res.status == "PASS"
        assert res.details["model_count"] == 2
        assert "qwen2.5:7b" in res.details["models"]


def test_check_windows_capabilities():
    res = check_windows_capabilities()
    assert res.status in ("PASS", "WARN")
    if res.status == "PASS":
        assert res.details.get("job_objects") == "supported"
        assert res.details.get("ui_automation") == "supported"


def test_check_storage_and_wal(tmp_path: Path):
    res = check_storage_and_wal(base_dir=tmp_path)
    assert res.status == "PASS"
    assert "all data directories writable" in res.message
    # Probe file should be cleaned up
    assert not (tmp_path / "data" / "test_wal_probe.db").exists()


def test_run_all_checks(tmp_path: Path):
    report = run_all_checks(base_dir=tmp_path)
    assert "overall_status" in report
    assert report["overall_status"] in ("PASS", "WARN", "FAIL")
    assert len(report["checks"]) == 5
