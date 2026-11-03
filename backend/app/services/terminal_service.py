"""Controlled Terminal Subprocess Runner & Security Service.

Enforces:
- Strict tokenized execution via asyncio.create_subprocess_exec (no shell=True).
- Command allowlist verification.
- Sandboxed working directory within workspace.
- Subprocess timeout handling with process termination.
- Standard output/error capture and size truncation (50 KB).
- Secret masking in output logs.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import time
from typing import Any

import psutil

from backend.app.core.config import Settings
from backend.app.core.exceptions import (
    CommandExecutionTimeoutException,
    CommandNotAllowedException,
    PathTraversalException,
)

logger = logging.getLogger("nexora.services.terminal")

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.\:\@\/\+=]{6,})['\"]?"),
    re.compile(r"(?i)bearer\s+([a-zA-Z0-9_\-\.\:\@\/\+=]{10,})"),
]


class TerminalService:
    """Safe, tokenized terminal execution service with allowlisting and jailing."""

    def __init__(self, settings: Settings, workspace_root: Path):
        self.settings = settings
        self.workspace_root = workspace_root.resolve()
        self.allowed_commands = {cmd.lower() for cmd in settings.ALLOWED_TERMINAL_COMMANDS}
        self.timeout_seconds = settings.TERMINAL_TIMEOUT_SECONDS
        self.max_output_bytes = settings.MAX_TERMINAL_OUTPUT_BYTES

    def get_system_info(self) -> dict[str, Any]:
        """Collect host system, CPU, memory, and OS architecture metrics safely."""
        mem = psutil.virtual_memory()
        boot_time = psutil.boot_time()
        uptime_seconds = max(0.0, round(time.time() - boot_time, 2))

        return {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_physical_cores": psutil.cpu_count(logical=False) or psutil.cpu_count(),
            "cpu_logical_cores": psutil.cpu_count(logical=True),
            "ram_total_mb": round(mem.total / (1024 * 1024), 2),
            "ram_available_mb": round(mem.available / (1024 * 1024), 2),
            "ram_percent_used": mem.percent,
            "boot_time": boot_time,
            "uptime_seconds": uptime_seconds,
        }

    def get_directory_info(self) -> dict[str, Any]:
        """Return host current working directory and designated workspace jail."""
        return {
            "current_working_directory": str(Path.cwd().resolve()),
            "workspace_directory": str(self.workspace_root),
        }

    def redact_secrets(self, text: str) -> str:
        """Mask API keys, auth tokens, and sensitive credentials in command outputs."""
        if not text:
            return text

        redacted = text
        for pat in SECRET_PATTERNS:
            # Replace secret values with [REDACTED]
            def _replacer(m: re.Match) -> str:
                full = m.group(0)
                secret = m.group(1) if len(m.groups()) == 1 else m.group(2)
                return full.replace(secret, "[REDACTED]")

            redacted = pat.sub(_replacer, redacted)

        return redacted

    def _resolve_command_binary(self, command: str) -> tuple[str, list[str]]:
        """Validate against allowlist and resolve binary path and default prepended args."""
        cmd_clean = command.strip().lower()
        cmd_base = cmd_clean[:-4] if cmd_clean.endswith(".exe") else cmd_clean

        # Strict elevation block
        if cmd_base in ("runas", "sudo", "powershell_ise"):
            raise CommandNotAllowedException(
                f"Administrative elevation commands ('{command}') are strictly prohibited."
            )

        if cmd_base not in self.allowed_commands and cmd_clean not in self.allowed_commands:
            raise CommandNotAllowedException(
                f"Command '{command}' is not in the allowed terminal commands allowlist: {sorted(self.allowed_commands)}"
            )

        # Map special Python/virtualenv tools to active Python interpreter for consistency
        if cmd_base == "python":
            return sys.executable, []
        if cmd_base == "pip":
            return sys.executable, ["-m", "pip"]
        if cmd_base == "pytest":
            return sys.executable, ["-m", "pytest"]

        # General binary resolution via system PATH
        resolved = shutil.which(command) or shutil.which(f"{command}.exe")
        if not resolved:
            raise CommandNotAllowedException(
                f"Binary for allowlisted command '{command}' was not found on system PATH."
            )

        return resolved, []

    async def execute_command(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: Path | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute an allowlisted command securely with tokenized arguments and timeout."""
        target_bin, prepended_args = self._resolve_command_binary(command)

        # Block elevation arguments
        input_args = args or []
        for a in input_args:
            if a.lower().strip() in ("runas", "sudo"):
                raise CommandNotAllowedException("Elevation arguments are strictly prohibited.")

        full_args = prepended_args + input_args

        # Resolve working directory jailed within workspace
        target_cwd = (cwd or self.workspace_root).resolve()
        try:
            target_cwd.relative_to(self.workspace_root)
        except ValueError:
            # If not inside workspace, fallback to workspace_root
            target_cwd = self.workspace_root

        logger.info(
            "Executing terminal command: %s %s (cwd=%s)",
            target_bin,
            full_args,
            target_cwd,
        )

        timeout_sec = timeout or self.timeout_seconds
        start_time = time.perf_counter()

        try:
            proc = await asyncio.create_subprocess_exec(
                target_bin,
                *full_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(target_cwd),
            )
        except OSError as e:
            logger.error("Failed to spawn process for command '%s': %s", command, e)
            raise CommandNotAllowedException(f"Failed to spawn command '{command}': {e}") from e

        try:
            raw_stdout, raw_stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            logger.warning("Command '%s' timed out after %0.1fs. Terminating.", command, timeout_sec)
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            raise CommandExecutionTimeoutException(
                f"Command '{command}' execution timed out after {timeout_sec} seconds."
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Check truncation threshold
        truncated = False
        if len(raw_stdout) > self.max_output_bytes:
            raw_stdout = raw_stdout[: self.max_output_bytes] + b"\n[...OUTPUT TRUNCATED BY NEXORA...]"
            truncated = True

        if len(raw_stderr) > self.max_output_bytes:
            raw_stderr = raw_stderr[: self.max_output_bytes] + b"\n[...ERROR TRUNCATED BY NEXORA...]"
            truncated = True

        stdout_str = self.redact_secrets(raw_stdout.decode("utf-8", errors="replace"))
        stderr_str = self.redact_secrets(raw_stderr.decode("utf-8", errors="replace"))

        return {
            "command": command,
            "arguments": input_args,
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "duration_ms": duration_ms,
            "truncated": truncated,
        }

    async def run_script(
        self,
        script_path: str,
        args: list[str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute a Python script located within the designated workspace jail."""
        target_path = (self.workspace_root / script_path).resolve()

        # Jail verification
        try:
            target_path.relative_to(self.workspace_root)
        except ValueError:
            raise PathTraversalException(
                f"Script path '{script_path}' escapes workspace jail: {self.workspace_root}"
            )

        if not target_path.is_file():
            raise FileNotFoundError(f"Python script not found: '{script_path}'")

        if target_path.suffix.lower() != ".py":
            raise CommandNotAllowedException(
                f"Only Python (.py) scripts are permitted for script execution: '{script_path}'"
            )

        full_args = [str(target_path)] + (args or [])
        return await self.execute_command(
            command="python",
            args=full_args,
            cwd=target_path.parent,
            timeout=timeout,
        )

    async def install_package(
        self,
        package_name: str,
        manager: str = "pip",
        upgrade: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Install a package dependency via pip or npm into the environment/workspace."""
        manager_clean = manager.strip().lower()
        if manager_clean not in ("pip", "npm"):
            raise CommandNotAllowedException(f"Unsupported package manager: '{manager}'. Allowed: pip, npm.")

        # Sanitize package name: prevent shell injection or extra flags
        safe_pkg_pattern = re.compile(r"^[a-zA-Z0-9_\-\.\:\@\/\[\]<>=!]+$")
        pkg_clean = package_name.strip()
        if not safe_pkg_pattern.match(pkg_clean) or pkg_clean.startswith("-"):
            raise CommandNotAllowedException(
                f"Invalid or unsafe package specification: '{package_name}'"
            )

        if manager_clean == "pip":
            pip_args = ["install"]
            if upgrade:
                pip_args.append("--upgrade")
            pip_args.append(pkg_clean)
            return await self.execute_command(
                command="pip",
                args=pip_args,
                cwd=self.workspace_root,
                timeout=timeout or 60.0,
            )
        else:  # npm
            npm_args = ["install"]
            if upgrade:
                npm_args.append("--save")
            npm_args.append(pkg_clean)
            return await self.execute_command(
                command="npm",
                args=npm_args,
                cwd=self.workspace_root,
                timeout=timeout or 60.0,
            )
