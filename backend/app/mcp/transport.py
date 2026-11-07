"""MCP Transport Abstractions and Subprocess Stdio Transport."""

from abc import ABC, abstractmethod
import asyncio
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("nexora.mcp.transport")


class McpTransportError(Exception):
    """Raised when an error occurs during transport communication or process management."""
    pass


class McpTransport(ABC):
    """Abstract base class for MCP client transports."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish transport connection or spawn child process."""
        pass

    @abstractmethod
    async def send_message(self, message: dict[str, Any]) -> None:
        """Serialize and send a JSON-RPC message."""
        pass

    @abstractmethod
    async def receive_message(self) -> Optional[dict[str, Any]]:
        """Read and parse the next JSON-RPC message, or None on EOF."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Gracefully terminate transport and release resources."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the transport is currently connected and active."""
        pass


class StdioTransport(McpTransport):
    """MCP transport communicating over standard input/output pipes of a spawned subprocess."""

    def __init__(
        self,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
    ):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.working_dir = working_dir
        self._process: Optional[asyncio.subprocess.Process] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._closed = False

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None and not self._closed

    async def connect(self) -> None:
        """Spawn child process with tokenized arguments and redirected pipes."""
        if self.is_connected:
            return

        # Prepare environment inheriting minimal required system variables + vault overrides
        full_env = dict(os.environ)
        full_env.update(self.env)

        logger.info(
            "Spawning MCP stdio server: command='%s', args=%s, cwd='%s'",
            self.command,
            self.args,
            self.working_dir,
        )

        try:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
                cwd=self.working_dir,
            )
            self._closed = False
            # Start background stderr consumer to prevent pipe clogging
            self._stderr_task = asyncio.create_task(self._consume_stderr())
        except Exception as e:
            logger.error("Failed to spawn MCP server process '%s': %s", self.command, e)
            raise McpTransportError(f"Failed to spawn MCP server process: {e}") from e

    async def _consume_stderr(self) -> None:
        """Consume child process stderr in background and log diagnostics."""
        if not self._process or not self._process.stderr:
            return
        try:
            while not self._process.stderr.at_eof():
                line = await self._process.stderr.readline()
                if line:
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        logger.debug("[MCP %s stderr] %s", self.command, decoded)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("Stderr stream closed for %s: %s", self.command, e)

    async def send_message(self, message: dict[str, Any]) -> None:
        """Send line-delimited JSON-RPC message to process stdin."""
        if not self.is_connected or not self._process or not self._process.stdin:
            raise McpTransportError("Cannot send message: MCP server process is not connected.")

        try:
            payload = json.dumps(message, separators=(",", ":")) + "\n"
            self._process.stdin.write(payload.encode("utf-8"))
            await self._process.stdin.drain()
        except Exception as e:
            logger.error("Failed to write to MCP server stdin: %s", e)
            raise McpTransportError(f"Error writing to MCP server pipe: {e}") from e

    async def receive_message(self) -> Optional[dict[str, Any]]:
        """Read next line-delimited JSON-RPC message from process stdout."""
        if not self._process or not self._process.stdout:
            return None

        while True:
            line = await self._process.stdout.readline()
            if not line:
                # EOF reached
                return None

            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                logger.warning("Ignored non-JSON line from MCP stdout: '%s' (%s)", text[:100], e)
                continue

    async def close(self) -> None:
        """Gracefully terminate child process and close pipes."""
        self._closed = True
        if self._stderr_task:
            self._stderr_task.cancel()
            self._stderr_task = None

        if not self._process:
            return

        proc = self._process
        self._process = None

        if proc.returncode is not None:
            return

        try:
            if proc.stdin and not proc.stdin.is_closing():
                proc.stdin.close()
                await proc.stdin.wait_closed()
        except Exception:
            pass

        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("MCP server process did not terminate gracefully; killing PID %s", proc.pid)
                proc.kill()
                await proc.wait()
        except Exception as e:
            logger.debug("Error while closing MCP server process: %s", e)
