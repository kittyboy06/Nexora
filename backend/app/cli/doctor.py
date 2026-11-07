"""NEXORA Pre-Flight Diagnostics Doctor.

Inspects environment prerequisites, dependencies, Windows capabilities,
Ollama availability, and SQLite WAL storage permissions.
"""

import ctypes
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import get_settings
from backend.app.memory.security import MemorySecurityGate


class CheckResult:
    """Encapsulates the result of a single diagnostic check."""

    def __init__(self, name: str, status: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.name = name
        self.status = status  # "PASS", "WARN", "FAIL"
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


def check_python_environment() -> CheckResult:
    """Validate Python version and critical runtime dependencies."""
    major, minor, micro = sys.version_info.major, sys.version_info.minor, sys.version_info.micro
    version_str = f"{major}.{minor}.{micro}"

    critical_packages = ["fastapi", "pydantic", "httpx", "pytest"]
    installed = {}
    missing = []

    for pkg in critical_packages:
        try:
            mod = __import__(pkg)
            installed[pkg] = getattr(mod, "__version__", "installed")
        except ImportError:
            missing.append(pkg)

    if major < 3 or (major == 3 and minor < 11):
        return CheckResult(
            name="Python Runtime",
            status="FAIL",
            message=f"Python {version_str} detected. NEXORA requires Python >= 3.11 (3.14+ recommended).",
            details={"version": version_str, "executable": sys.executable, "missing_packages": missing},
        )

    if missing:
        return CheckResult(
            name="Python Runtime",
            status="FAIL",
            message=f"Python {version_str} is compatible, but missing critical packages: {', '.join(missing)}",
            details={"version": version_str, "executable": sys.executable, "missing_packages": missing},
        )

    return CheckResult(
        name="Python Runtime",
        status="PASS",
        message=f"Python {version_str} verified with all critical packages present.",
        details={"version": version_str, "executable": sys.executable, "packages": installed},
    )


def check_dotnet_environment() -> CheckResult:
    """Detect .NET 8 SDK or desktop runtime for WinUI 3 dashboard."""
    candidates = [
        shutil.which("dotnet"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe"),
        r"C:\Program Files\dotnet\dotnet.exe",
    ]

    dotnet_path = None
    for cand in candidates:
        if cand and os.path.isfile(cand):
            dotnet_path = cand
            break

    if not dotnet_path:
        return CheckResult(
            name=".NET SDK & Desktop",
            status="WARN",
            message=".NET 8 SDK (dotnet.exe) not found. Required to compile or test the WinUI 3 desktop client.",
            details={"searched_paths": [c for c in candidates if c]},
        )

    try:
        proc = subprocess.run([dotnet_path, "--version"], capture_output=True, text=True, timeout=5)
        version = proc.stdout.strip()
        return CheckResult(
            name=".NET SDK & Desktop",
            status="PASS",
            message=f".NET SDK {version} detected at '{dotnet_path}'.",
            details={"version": version, "path": dotnet_path},
        )
    except Exception as exc:
        return CheckResult(
            name=".NET SDK & Desktop",
            status="WARN",
            message=f".NET binary found at '{dotnet_path}' but execution returned: {exc}",
            details={"path": dotnet_path, "error": str(exc)},
        )


def check_ollama_service(base_url: str = "http://localhost:11434") -> CheckResult:
    """Verify local Ollama server connectivity and model availability."""
    tags_url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "NexoraDoctor/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                if models:
                    return CheckResult(
                        name="Ollama Model Service",
                        status="PASS",
                        message=f"Ollama is online with {len(models)} installed model(s): {', '.join(models[:3])}{'...' if len(models) > 3 else ''}.",
                        details={"endpoint": base_url, "model_count": len(models), "models": models},
                    )
                else:
                    return CheckResult(
                        name="Ollama Model Service",
                        status="WARN",
                        message="Ollama is running, but no models are downloaded. Run 'ollama pull qwen2.5:7b'.",
                        details={"endpoint": base_url, "model_count": 0},
                    )
    except Exception as exc:
        return CheckResult(
            name="Ollama Model Service",
            status="WARN",
            message=f"Ollama is unreachable at {base_url}. (Offline tests remain fully supported).",
            details={"endpoint": base_url, "error": str(exc)},
        )


def check_windows_capabilities() -> CheckResult:
    """Verify Windows OS, Win32 Job Object support, and UI Automation access."""
    if sys.platform != "win32":
        return CheckResult(
            name="Windows OS Capabilities",
            status="WARN",
            message=f"Operating system is '{sys.platform}'. Native Windows sandboxing and WinUI 3 require Windows 10/11.",
            details={"platform": sys.platform},
        )

    details = {}

    # Test Win32 Job Object creation
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateJobObjectW(None, None)
        if handle:
            kernel32.CloseHandle(handle)
            details["job_objects"] = "supported"
        else:
            details["job_objects"] = "failed_create_handle"
    except Exception as exc:
        details["job_objects"] = f"error: {exc}"

    # Test UI Automation Core library
    try:
        uia = ctypes.windll.LoadLibrary("UIAutomationCore.dll")
        if uia:
            details["ui_automation"] = "supported"
        else:
            details["ui_automation"] = "failed_load_dll"
    except Exception as exc:
        details["ui_automation"] = f"error: {exc}"

    if details.get("job_objects") == "supported" and details.get("ui_automation") == "supported":
        return CheckResult(
            name="Windows OS Capabilities",
            status="PASS",
            message="Win32 Job Objects and UI Automation Core are verified.",
            details=details,
        )
    else:
        return CheckResult(
            name="Windows OS Capabilities",
            status="WARN",
            message="Some Windows native subsystems could not be initialized.",
            details=details,
        )


def check_storage_and_wal(base_dir: Optional[Path] = None) -> CheckResult:
    """Verify read/write permissions and SQLite Write-Ahead Logging (WAL) support."""
    if not base_dir:
        # Detect repo root
        cwd = Path.cwd()
        base_dir = cwd.parent if cwd.name == "backend" else cwd

    data_dir = base_dir / "data"
    subdirs = ["memory", "scheduler", "tasks", "workspace", "quarantine", "logs"]
    created = []

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        for s in subdirs:
            p = data_dir / s
            p.mkdir(parents=True, exist_ok=True)
            created.append(s)

        # Test SQLite WAL mode file creation
        test_db = data_dir / "test_wal_probe.db"
        wal_mode = "unknown"
        conn = sqlite3.connect(str(test_db))
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            row = conn.execute("PRAGMA journal_mode;").fetchone()
            wal_mode = row[0] if row else "unknown"
            conn.execute("CREATE TABLE probe (id INT);")
            conn.execute("INSERT INTO probe VALUES (1);")
        finally:
            conn.close()

        # Clean probe files
        for ext in ["", "-wal", "-shm"]:
            f = Path(str(test_db) + ext)
            if f.exists():
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass

        return CheckResult(
            name="Storage & SQLite WAL",
            status="PASS",
            message=f"Storage verified: all data directories writable; SQLite WAL mode confirmed ({wal_mode}).",
            details={"data_dir": str(data_dir), "directories": created, "wal_mode": wal_mode},
        )
    except Exception as exc:
        return CheckResult(
            name="Storage & SQLite WAL",
            status="FAIL",
            message=f"Storage permissions or SQLite WAL initialization failed: {exc}",
            details={"data_dir": str(data_dir), "error": str(exc)},
        )


def run_all_checks(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Execute all pre-flight diagnostic checks and return structured results."""
    checks = [
        check_python_environment(),
        check_dotnet_environment(),
        check_ollama_service(),
        check_windows_capabilities(),
        check_storage_and_wal(base_dir),
    ]

    has_fail = any(c.status == "FAIL" for c in checks)
    has_warn = any(c.status == "WARN" for c in checks)

    overall_status = "FAIL" if has_fail else ("WARN" if has_warn else "PASS")

    return {
        "overall_status": overall_status,
        "checks": [c.to_dict() for c in checks],
    }


def print_doctor_report(results: Dict[str, Any]) -> int:
    """Render a human-readable CLI report with status indicators."""
    print("\n" + "=" * 60)
    print("        NEXORA Pre-Flight Diagnostics Doctor")
    print("=" * 60 + "\n")

    symbols = {
        "PASS": "[ OK ]",
        "WARN": "[WARN]",
        "FAIL": "[FAIL]",
    }

    for check in results.get("checks", []):
        st = check.get("status", "INFO")
        sym = symbols.get(st, "[ ? ]")
        name = check.get("name", "Unknown Check")
        msg = check.get("message", "")
        print(f"{sym} {name}")
        print(f"       {msg}\n")

    overall = results.get("overall_status", "UNKNOWN")
    print("-" * 60)
    if overall == "PASS":
        print("RESULT: READY - All pre-flight requirements satisfied.\n")
        return 0
    elif overall == "WARN":
        print("RESULT: COMPATIBLE WITH WARNINGS - Core capabilities ready; optional components noted above.\n")
        return 0
    else:
        print("RESULT: PREREQUISITES FAILED - Address the FAIL issues above before running NEXORA.\n")
        return 1


def get_sanitized_config() -> Dict[str, Any]:
    """Retrieve application configuration with all sensitive credentials scrubbed."""
    try:
        cfg = get_settings().model_dump()
        sanitized = {}
        sensitive_substrings = ("token", "secret", "password", "key", "auth", "credential")
        for k, v in cfg.items():
            if any(sub in k.lower() for sub in sensitive_substrings) and v:
                sanitized[k] = "[REDACTED_SECRET]"
            elif isinstance(v, (set, tuple)):
                sanitized[k] = sorted(list(v)) if isinstance(v, set) else list(v)
            elif isinstance(v, Path):
                sanitized[k] = str(v)
            else:
                sanitized[k] = v
        return sanitized
    except Exception as exc:
        return {"error": f"Failed to dump config: {exc}"}


def export_support_bundle(base_dir: Optional[Path] = None, output_zip: Optional[Path] = None) -> Path:
    """
    Collect system diagnostics, component health, and scrubbed logs into a sanitized ZIP archive.
    Strictly scrubs all secrets, API keys, and auth tokens.
    Excludes quarantined desktop screenshots and raw user prompts.
    """
    if not base_dir:
        cwd = Path.cwd()
        base_dir = cwd.parent if cwd.name == "backend" else cwd

    diag_dir = base_dir / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)

    if not output_zip:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_zip = diag_dir / f"nexora-diagnostics-{timestamp}.zip"

    # 1. System Information
    system_info = {
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "cpu_count": os.cpu_count(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    # 2. Diagnostics Report
    diagnostics_report = run_all_checks(base_dir)

    # 3. Component Status
    data_dir = base_dir / "data"
    component_status = {
        "tasks_dir_present": (data_dir / "tasks").exists(),
        "task_count": len(list((data_dir / "tasks").glob("*.json"))) if (data_dir / "tasks").exists() else 0,
        "memory_db_present": (data_dir / "memory" / "nexora_memory.db").exists(),
        "scheduler_db_present": (data_dir / "scheduler" / "nexora_scheduler.db").exists(),
        "skills_installed": len(list((data_dir / "skills").iterdir())) if (data_dir / "skills").exists() else 0,
        "mcp_servers_installed": len(list((data_dir / "mcp").glob("*.json"))) if (data_dir / "mcp").exists() else 0,
        "generated_tools_count": len(list((data_dir / "tools" / "generated").glob("*.py"))) if (data_dir / "tools" / "generated").exists() else 0,
    }

    # 4. Recent Logs (Last 500 lines, scrubbed)
    log_file = data_dir / "logs" / "nexora.log"
    recent_logs_text = "No log file found."
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                recent_lines = lines[-500:] if len(lines) > 500 else lines
                recent_logs_text = "".join(recent_lines)
        except Exception as exc:
            recent_logs_text = f"Error reading log file: {exc}"

    # Pass through Phase 11 Secret Scrubber
    scrubbed_logs = MemorySecurityGate.scrub_secrets(recent_logs_text)

    # 5. Sanitized Config
    sanitized_config = get_sanitized_config()

    # Create ZIP archive
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("system_info.json", json.dumps(system_info, indent=2, default=str))
        zf.writestr("diagnostics_report.json", json.dumps(diagnostics_report, indent=2, default=str))
        zf.writestr("component_status.json", json.dumps(component_status, indent=2, default=str))
        zf.writestr("sanitized_config.json", json.dumps(sanitized_config, indent=2, default=str))
        zf.writestr("recent_logs.log", scrubbed_logs)

    return output_zip


def main() -> int:
    """CLI entrypoint."""
    if "--export" in sys.argv:
        out_idx = sys.argv.index("--out") + 1 if "--out" in sys.argv and sys.argv.index("--out") + 1 < len(sys.argv) else None
        target_path = Path(sys.argv[out_idx]) if out_idx else None
        bundle_path = export_support_bundle(output_zip=target_path)
        print(f"Exported sanitized diagnostics support bundle to: {bundle_path}")
        return 0

    results = run_all_checks()
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
        return 0 if results.get("overall_status") != "FAIL" else 1
    return print_doctor_report(results)


if __name__ == "__main__":
    sys.exit(main())
