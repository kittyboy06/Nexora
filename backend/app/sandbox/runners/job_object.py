"""Windows Win32 Job Object Runner for Sandbox Process Isolation."""

import asyncio
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from backend.app.sandbox.models import SandboxRunResult, SandboxRunStatus, TestCase
from backend.app.sandbox.runners.base import SandboxRunner

if sys.platform == "win32":
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", wintypes.ULARGE_INTEGER),
            ("WriteOperationCount", wintypes.ULARGE_INTEGER),
            ("OtherOperationCount", wintypes.ULARGE_INTEGER),
            ("ReadTransferCount", wintypes.ULARGE_INTEGER),
            ("WriteTransferCount", wintypes.ULARGE_INTEGER),
            ("OtherTransferCount", wintypes.ULARGE_INTEGER),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_void_p),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9


class Win32JobObjectRunner(SandboxRunner):
    """Enforces OS-kernel level memory, process count, and lifetime limits via Win32 Job Objects."""

    def __init__(
        self,
        base_sandbox_dir: Optional[Path] = None,
        memory_limit_bytes: int = 256 * 1024 * 1024,  # 256 MB
        active_process_limit: int = 1,
    ) -> None:
        self.base_sandbox_dir = (
            base_sandbox_dir or Path("data/sandbox")
        ).resolve()
        self.memory_limit_bytes = memory_limit_bytes
        self.active_process_limit = active_process_limit
        self.base_sandbox_dir.mkdir(parents=True, exist_ok=True)

        if sys.platform == "win32":
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            self.kernel32.CreateJobObjectW.restype = wintypes.HANDLE

            self.kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                wintypes.LPVOID,
                wintypes.DWORD,
            ]
            self.kernel32.SetInformationJobObject.restype = wintypes.BOOL

            self.kernel32.AssignProcessToJobObject.argtypes = [
                wintypes.HANDLE,
                wintypes.HANDLE,
            ]
            self.kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

            self.kernel32.QueryInformationJobObject.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                wintypes.LPVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
            ]
            self.kernel32.QueryInformationJobObject.restype = wintypes.BOOL

            self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel32.CloseHandle.restype = wintypes.BOOL
        else:
            self.kernel32 = None

    def _create_and_configure_job(self) -> Optional[int]:
        """Create a Win32 Job Object and set hard limits."""
        if sys.platform != "win32" or not self.kernel32:
            return None

        hJob = self.kernel32.CreateJobObjectW(None, None)
        if not hJob:
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_JOB_MEMORY
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        info.ProcessMemoryLimit = self.memory_limit_bytes
        info.JobMemoryLimit = self.memory_limit_bytes
        info.BasicLimitInformation.ActiveProcessLimit = self.active_process_limit

        success = self.kernel32.SetInformationJobObject(
            hJob,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not success:
            self.kernel32.CloseHandle(hJob)
            return None

        return hJob

    def _query_peak_memory(self, hJob: int) -> int:
        """Query peak memory footprint from the Job Object before handle closure."""
        if sys.platform != "win32" or not self.kernel32 or not hJob:
            return 0

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        ret_len = wintypes.DWORD()
        success = self.kernel32.QueryInformationJobObject(
            hJob,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(ret_len),
        )
        if success:
            return int(info.PeakJobMemoryUsed or info.PeakProcessMemoryUsed)
        return 0

    def _sanitize_environment(self, workspace_path: Path) -> dict[str, str]:
        """Build a sterile environment with all ambient user secrets and API keys removed."""
        clean_env: dict[str, str] = {}

        # Preserve essential OS paths on Windows
        if sys.platform == "win32":
            clean_env["SystemRoot"] = os.environ.get("SystemRoot", "C:\\Windows")
            clean_env["ComSpec"] = os.environ.get("ComSpec", "C:\\Windows\\system32\\cmd.exe")
            # Minimal PATH: only Python executable directory and Windows System32
            py_dir = os.path.dirname(sys.executable)
            sys32 = os.path.join(clean_env["SystemRoot"], "system32")
            clean_env["PATH"] = f"{py_dir};{sys32};{clean_env['SystemRoot']}"
        else:
            clean_env["PATH"] = "/usr/bin:/bin"

        clean_env["PYTHONPATH"] = str(workspace_path)
        clean_env["PYTHONUNBUFFERED"] = "1"
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        tmp_dir = workspace_path / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        clean_env["TEMP"] = str(tmp_dir)
        clean_env["TMP"] = str(tmp_dir)

        return clean_env

    def _sync_execute(
        self,
        run_id: str,
        tool_name: str,
        code: str,
        mode: str,
        test_cases: Optional[list[TestCase]],
        runtime_arguments: Optional[dict[str, Any]],
        task_id: Optional[str],
        timeout_seconds: float,
    ) -> SandboxRunResult:
        """Synchronous execution worker run within asyncio thread pool."""
        workspace = self.base_sandbox_dir / run_id
        workspace.mkdir(parents=True, exist_ok=True)

        source_sha256 = hashlib.sha256(code.encode("utf-8")).hexdigest()
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Write tool file
        tool_file = workspace / "tool.py"
        tool_file.write_text(code, encoding="utf-8")

        # Copy entrypoint.py into workspace
        entrypoint_src = Path(__file__).resolve().parent.parent / "entrypoint.py"
        entrypoint_dst = workspace / "entrypoint.py"
        shutil.copy2(entrypoint_src, entrypoint_dst)

        # Write input.json
        input_payload: dict[str, Any] = {
            "mode": mode,
            "tool_name": tool_name,
            "runtime_arguments": runtime_arguments or {},
            "test_cases": [tc.model_dump() for tc in test_cases] if test_cases else [],
        }
        input_file = workspace / "input.json"
        input_file.write_text(json.dumps(input_payload, indent=2), encoding="utf-8")

        # Set up Job Object
        hJob = self._create_and_configure_job()
        clean_env = self._sanitize_environment(workspace)

        start_time = time.perf_counter()
        peak_memory_bytes = 0
        status = SandboxRunStatus.ERROR
        exit_code = -1
        stdout_text = ""
        stderr_text = ""
        output_payload = None
        test_results: list[dict[str, Any]] = []

        try:
            cmd = [sys.executable, str(entrypoint_dst)]
            proc = subprocess.Popen(
                cmd,
                cwd=str(workspace),
                env=clean_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if hJob and self.kernel32:
                self.kernel32.AssignProcessToJobObject(hJob, int(proc._handle))

            try:
                stdout_text, stderr_text = proc.communicate(timeout=timeout_seconds)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_text, stderr_text = proc.communicate()
                status = SandboxRunStatus.TIMEOUT
                exit_code = -99

            if hJob:
                peak_memory_bytes = self._query_peak_memory(hJob)

            # Check if OOM killed (memory limit exceeded)
            if peak_memory_bytes >= self.memory_limit_bytes or exit_code in (-1073741801, 3221225495):  # STATUS_NO_MEMORY (0xC0000017)
                status = SandboxRunStatus.OOM_KILLED
            elif status != SandboxRunStatus.TIMEOUT:
                output_file = workspace / "output.json"
                if output_file.exists():
                    try:
                        out_data = json.loads(output_file.read_text(encoding="utf-8"))
                        file_status = out_data.get("status")
                        if file_status == "TESTS_PASSED":
                            status = SandboxRunStatus.TESTS_PASSED
                        elif file_status == "TESTS_FAILED":
                            status = SandboxRunStatus.TESTS_FAILED
                        elif file_status == "EXECUTION_SUCCESS":
                            status = SandboxRunStatus.EXECUTION_SUCCESS
                        else:
                            status = SandboxRunStatus.ERROR

                        output_payload = out_data.get("output")
                        test_results = out_data.get("test_results", [])
                    except Exception as e:
                        status = SandboxRunStatus.ERROR
                        stderr_text += f"\nFailed reading output.json: {e}"
                else:
                    status = SandboxRunStatus.ERROR

        except Exception as ex:
            status = SandboxRunStatus.ERROR
            stderr_text += f"\nSandbox execution exception: {ex}"
        finally:
            if hJob and self.kernel32:
                self.kernel32.CloseHandle(hJob)

            # Clean up ephemeral workspace
            try:
                shutil.rmtree(workspace, ignore_errors=True)
            except Exception:
                pass

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return SandboxRunResult(
            run_id=run_id,
            task_id=task_id,
            tool_name=tool_name,
            status=status,
            exit_code=exit_code,
            execution_time_ms=execution_time_ms,
            peak_memory_bytes=peak_memory_bytes,
            test_results=test_results,
            output=output_payload,
            stdout=stdout_text,
            stderr=stderr_text,
            source_sha256=source_sha256,
            timestamp=now_iso,
        )

    async def run(
        self,
        tool_name: str,
        code: str,
        mode: str = "test",
        test_cases: Optional[list[TestCase]] = None,
        runtime_arguments: Optional[dict[str, Any]] = None,
        task_id: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ) -> SandboxRunResult:
        """Run tool in sandbox asynchronously without blocking the event loop."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        return await asyncio.to_thread(
            self._sync_execute,
            run_id=run_id,
            tool_name=tool_name,
            code=code,
            mode=mode,
            test_cases=test_cases,
            runtime_arguments=runtime_arguments,
            task_id=task_id,
            timeout_seconds=timeout_seconds,
        )
