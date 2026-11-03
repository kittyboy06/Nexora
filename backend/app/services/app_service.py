"""Windows Application Control & Process Supervisor Service.

Provides secure desktop application discovery via Windows Registry and Start Menu,
executable validation, managed process launching with PID tracking, and process
inspection and termination with Windows system process denylist protection.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

import psutil

try:
    import winreg
except ImportError:
    winreg = None  # Non-Windows fallback for test mocking

from backend.app.core.config import Settings
from backend.app.core.exceptions import (
    AppNotFoundException,
    ProcessNotFoundException,
    SystemProcessProtectedException,
)

logger = logging.getLogger("nexora.services.app")


class AppService:
    """Windows Application Control and Process Supervision Service."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.protected_process_names = {p.lower() for p in settings.PROTECTED_PROCESS_NAMES}
        self._launched_pids: set[int] = set()
        self._cached_apps: list[dict[str, Any]] | None = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl_seconds: float = 300.0  # 5 minutes

    @property
    def launched_pids(self) -> set[int]:
        """Set of PIDs launched directly by NEXORA."""
        return set(self._launched_pids)

    def list_installed_apps(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Discover installed desktop applications across Windows Registry, App Paths, and Start Menu.

        Results are cached in memory for performance.
        """
        now = time.time()
        if (
            not force_refresh
            and self._cached_apps is not None
            and (now - self._cache_timestamp) < self._cache_ttl_seconds
        ):
            return list(self._cached_apps)

        apps_by_name: dict[str, dict[str, Any]] = {}

        # 1. Scan Windows Registry Uninstall keys (64-bit and 32-bit, HKLM and HKCU)
        if winreg is not None:
            uninstall_roots = [
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for root, subkey in uninstall_roots:
                self._scan_registry_uninstall(root, subkey, apps_by_name)

            # 2. Scan App Paths (registered executable names)
            app_path_roots = [
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
            ]
            for root, subkey in app_path_roots:
                self._scan_app_paths(root, subkey, apps_by_name)

        # 3. Scan Start Menu shortcuts
        self._scan_start_menu_shortcuts(apps_by_name)

        # 4. Scan common built-in Windows utilities
        self._scan_builtin_utilities(apps_by_name)

        sorted_apps = sorted(apps_by_name.values(), key=lambda a: a["name"].lower())
        self._cached_apps = sorted_apps
        self._cache_timestamp = now
        logger.info("Discovered %d installed desktop applications.", len(sorted_apps))
        return list(sorted_apps)

    def _scan_registry_uninstall(self, root: int, subkey: str, catalog: dict[str, dict[str, Any]]) -> None:
        """Enumerate application uninstall keys in the registry."""
        try:
            with winreg.OpenKey(root, subkey) as key:
                num_subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(num_subkeys):
                    try:
                        name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, name) as app_key:
                            self._extract_app_from_key(app_key, catalog)
                    except OSError:
                        continue
        except OSError:
            pass

    def _extract_app_from_key(self, app_key: Any, catalog: dict[str, dict[str, Any]]) -> None:
        """Extract application metadata from a registry uninstall key."""
        try:
            display_name, _ = winreg.QueryValueEx(app_key, "DisplayName")
            if not display_name or not isinstance(display_name, str):
                return
            display_name = display_name.strip()
            if not display_name:
                return

            # Ignore Windows updates / patches / security updates
            system_component, _ = self._safe_query_value(app_key, "SystemComponent")
            if system_component == 1:
                return

            version, _ = self._safe_query_value(app_key, "DisplayVersion")
            publisher, _ = self._safe_query_value(app_key, "Publisher")
            install_loc, _ = self._safe_query_value(app_key, "InstallLocation")
            display_icon, _ = self._safe_query_value(app_key, "DisplayIcon")

            # Resolve executable path if available
            exe_path = self._sanitize_executable_path(display_icon) or self._sanitize_executable_path(install_loc)

            app_id = display_name.lower()
            if app_id not in catalog or (exe_path and not catalog[app_id].get("executable_path")):
                catalog[app_id] = {
                    "name": display_name,
                    "executable_path": exe_path,
                    "version": str(version) if version else None,
                    "publisher": str(publisher) if publisher else None,
                    "source": "registry",
                }
        except OSError:
            pass

    def _scan_app_paths(self, root: int, subkey: str, catalog: dict[str, dict[str, Any]]) -> None:
        """Enumerate registered executable targets in App Paths."""
        try:
            with winreg.OpenKey(root, subkey) as key:
                num_subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(num_subkeys):
                    try:
                        app_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, app_name) as app_key:
                            val, _ = winreg.QueryValueEx(app_key, "")
                            exe_path = self._sanitize_executable_path(val)
                            clean_name = Path(app_name).stem.capitalize()
                            app_id = clean_name.lower()
                            if app_id not in catalog:
                                catalog[app_id] = {
                                    "name": clean_name,
                                    "executable_path": exe_path,
                                    "version": None,
                                    "publisher": None,
                                    "source": "app_paths",
                                }
                    except OSError:
                        continue
        except OSError:
            pass

    def _scan_start_menu_shortcuts(self, catalog: dict[str, dict[str, Any]]) -> None:
        """Scan Start Menu folders for application shortcuts."""
        search_dirs = [
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        ]
        app_data = os.environ.get("APPDATA")
        if app_data:
            search_dirs.append(Path(app_data) / r"Microsoft\Windows\Start Menu\Programs")

        for s_dir in search_dirs:
            if not s_dir.exists():
                continue
            try:
                for root, _, files in os.walk(s_dir):
                    for file in files:
                        if file.lower().endswith(".lnk"):
                            shortcut_name = Path(file).stem
                            app_id = shortcut_name.lower()
                            if app_id not in catalog:
                                catalog[app_id] = {
                                    "name": shortcut_name,
                                    "executable_path": None,
                                    "version": None,
                                    "publisher": None,
                                    "source": "start_menu",
                                }
            except OSError:
                pass

    def _scan_builtin_utilities(self, catalog: dict[str, dict[str, Any]]) -> None:
        """Add common built-in Windows applications resolved via system PATH."""
        builtins = ["notepad", "calc", "mspaint", "cmd", "powershell"]
        for b in builtins:
            resolved = shutil.which(f"{b}.exe") or shutil.which(b)
            if resolved:
                app_id = b.lower()
                if app_id not in catalog or not catalog[app_id].get("executable_path"):
                    catalog[app_id] = {
                        "name": b.capitalize(),
                        "executable_path": str(Path(resolved).resolve()),
                        "version": None,
                        "publisher": "Microsoft Corporation",
                        "source": "system",
                    }

    @staticmethod
    def _safe_query_value(key: Any, value_name: str) -> tuple[Any, int] | tuple[None, None]:
        try:
            return winreg.QueryValueEx(key, value_name)
        except OSError:
            return None, None

    @staticmethod
    def _sanitize_executable_path(raw_path: Any) -> str | None:
        """Strip quotes, icon indexes (e.g. ,0), and trailing parameters."""
        if not raw_path or not isinstance(raw_path, str):
            return None
        clean = raw_path.strip().strip('"').strip("'")
        if "," in clean and clean.split(",")[-1].strip().isdigit():
            clean = clean.split(",")[0].strip().strip('"')
        if clean.lower().endswith(".exe") and os.path.isfile(clean):
            return str(Path(clean).resolve())
        # Try checking if path exists directly
        if os.path.isfile(clean):
            return str(Path(clean).resolve())
        return None

    def find_app(self, query: str) -> list[dict[str, Any]]:
        """Search catalog by application name, publisher, or executable path."""
        q = query.strip().lower()
        if not q:
            return []

        # Ensure catalog is loaded
        catalog = self.list_installed_apps()

        exact_matches: list[dict[str, Any]] = []
        prefix_matches: list[dict[str, Any]] = []
        substring_matches: list[dict[str, Any]] = []

        for app in catalog:
            name_lower = app["name"].lower()
            publisher_lower = (app.get("publisher") or "").lower()
            exe_lower = (app.get("executable_path") or "").lower()

            if q == name_lower:
                exact_matches.append(app)
            elif name_lower.startswith(q):
                prefix_matches.append(app)
            elif q in name_lower or q in publisher_lower or q in exe_lower:
                substring_matches.append(app)

        results = exact_matches + prefix_matches + substring_matches

        # If still empty, check if query matches a binary on system PATH
        if not results:
            resolved = shutil.which(query) or shutil.which(f"{query}.exe")
            if resolved:
                return [
                    {
                        "name": Path(resolved).stem.capitalize(),
                        "executable_path": str(Path(resolved).resolve()),
                        "version": None,
                        "publisher": "System",
                        "source": "system",
                    }
                ]

        return results

    def resolve_executable(self, target: str) -> Path:
        """Resolve an application name, alias, or path to a validated .exe Path."""
        target_path = Path(target)

        # 1. Direct path check
        if target_path.is_file():
            if target_path.suffix.lower() != ".exe":
                raise AppNotFoundException(f"Target '{target}' is not a Windows executable (.exe).")
            return target_path.resolve()

        # 2. PATH resolution
        which_path = shutil.which(target) or shutil.which(f"{target}.exe")
        if which_path and Path(which_path).is_file():
            return Path(which_path).resolve()

        # 3. Catalog lookup
        matches = self.find_app(target)
        for match in matches:
            exe_path = match.get("executable_path")
            if exe_path and Path(exe_path).is_file():
                return Path(exe_path).resolve()

        raise AppNotFoundException(
            f"Application '{target}' could not be resolved to an existing Windows executable."
        )

    def launch_app(self, app_name_or_path: str, arguments: list[str] | None = None) -> dict[str, Any]:
        """Launch a desktop application asynchronously without blocking NEXORA.

        Validates executable, launches process in detached mode, and records PID.
        """
        exe_path = self.resolve_executable(app_name_or_path)

        cmd = [str(exe_path)] + (arguments or [])
        logger.info("Launching desktop application: %s (args: %s)", exe_path, arguments)

        # On Windows, launch as detached process with new process group
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            proc = subprocess.Popen(
                cmd,
                creationflags=creationflags,
                close_fds=True,
            )
        except OSError as e:
            logger.error("Failed to launch application '%s': %s", exe_path, e)
            raise AppNotFoundException(f"Failed to start process '{exe_path}': {e}") from e

        self._launched_pids.add(proc.pid)
        logger.info("Application '%s' launched successfully with PID %d", exe_path.name, proc.pid)

        return {
            "pid": proc.pid,
            "name": exe_path.name,
            "executable_path": str(exe_path),
            "status": "launched",
        }

    def get_running_processes(
        self, include_system: bool = False, limit: int | None = 100
    ) -> list[dict[str, Any]]:
        """List active processes, filtering out protected Windows system processes by default."""
        results: list[dict[str, Any]] = []

        for proc in psutil.process_iter(["pid", "name", "memory_info", "status", "create_time"]):
            try:
                info = proc.info
                pid = info.get("pid")
                name = info.get("name") or "unknown"

                if pid is None or pid in (0, 4):  # System Idle and System
                    if not include_system:
                        continue

                name_lower = name.lower()
                if not include_system and name_lower in self.protected_process_names:
                    continue

                mem_info = info.get("memory_info")
                mem_mb = round(mem_info.rss / (1024 * 1024), 2) if mem_info else 0.0

                results.append(
                    {
                        "pid": pid,
                        "name": name,
                        "memory_mb": mem_mb,
                        "status": info.get("status") or "running",
                        "is_managed": pid in self._launched_pids,
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort by memory usage descending
        results.sort(key=lambda p: p["memory_mb"], reverse=True)
        if limit and limit > 0:
            return results[:limit]
        return results

    def get_process_details(self, pid: int) -> dict[str, Any]:
        """Fetch detailed performance and runtime metrics for a specific process PID."""
        if not psutil.pid_exists(pid):
            raise ProcessNotFoundException(f"Process PID {pid} not found or already terminated.")

        try:
            proc = psutil.Process(pid)
            name = proc.name()
            status = proc.status()
            create_time = proc.create_time()
            uptime_seconds = max(0.0, round(time.time() - create_time, 2))
            num_threads = proc.num_threads()

            # Memory
            mem_info = proc.memory_info()
            mem_mb = round(mem_info.rss / (1024 * 1024), 2)

            # CPU percentage (non-blocking)
            cpu_percent = proc.cpu_percent(interval=None)

            # Executable path (handle AccessDenied)
            try:
                exe = proc.exe()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                exe = None

            is_protected = name.lower() in self.protected_process_names or pid in (0, 4)

            return {
                "pid": pid,
                "name": name,
                "executable_path": exe,
                "status": status,
                "cpu_percent": cpu_percent,
                "memory_mb": mem_mb,
                "create_time": create_time,
                "uptime_seconds": uptime_seconds,
                "num_threads": num_threads,
                "is_protected": is_protected,
                "is_managed": pid in self._launched_pids,
            }
        except psutil.NoSuchProcess:
            raise ProcessNotFoundException(f"Process PID {pid} terminated while reading details.")
        except psutil.AccessDenied as e:
            raise SystemProcessProtectedException(
                f"Access denied reading details for process PID {pid}: {e}"
            )

    def close_app(self, pid: int, force: bool = False) -> dict[str, Any]:
        """Terminate a running process, protecting critical Windows system processes."""
        if not psutil.pid_exists(pid):
            raise ProcessNotFoundException(f"Process PID {pid} not found or already terminated.")

        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
        except psutil.NoSuchProcess:
            raise ProcessNotFoundException(f"Process PID {pid} already exited.")

        name_lower = proc_name.lower()
        if name_lower in self.protected_process_names or pid in (0, 4):
            raise SystemProcessProtectedException(
                f"Access denied: Process '{proc_name}' (PID {pid}) is a protected Windows system component."
            )

        try:
            if force:
                proc.kill()
            else:
                proc.terminate()

            # Attempt graceful wait
            try:
                proc.wait(timeout=3.0)
            except psutil.TimeoutExpired:
                if force:
                    logger.warning("Process PID %d did not terminate within timeout.", pid)

            self._launched_pids.discard(pid)
            logger.info("Process '%s' (PID %d) terminated (force=%s)", proc_name, pid, force)

            return {
                "pid": pid,
                "name": proc_name,
                "status": "terminated" if force else "closed",
                "force": force,
            }
        except psutil.NoSuchProcess:
            self._launched_pids.discard(pid)
            return {"pid": pid, "name": proc_name, "status": "closed", "force": force}
        except psutil.AccessDenied as e:
            raise SystemProcessProtectedException(
                f"Access denied terminating process '{proc_name}' (PID {pid}): {e}"
            )
