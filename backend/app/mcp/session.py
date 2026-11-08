"""MCP Client Session Engine and Idle Connection Pool."""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Optional

from backend.app.core.config import get_settings
from backend.app.mcp.models import (
    McpServerRecord,
    McpServerStatus,
    McpToolDefinition,
    compute_manifest_fingerprint,
)
from backend.app.mcp.protocol import McpProtocolError, McpProtocolHandler
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.transport import McpTransport, StdioTransport
from backend.app.mcp.vault import McpVaultService

logger = logging.getLogger("nexora.mcp.session")


class McpSecurityError(Exception):
    """Raised when an unapproved server attempts execution or security policy is violated."""
    pass


class McpClientSession:
    """Manages an active connection session, protocol handshake, and tool dispatch to an MCP server."""

    def __init__(
        self,
        record: McpServerRecord,
        vault: McpVaultService,
        transport: Optional[McpTransport] = None,
        idle_timeout_seconds: float = 600.0,
    ):
        self.record = record
        self.vault = vault
        self.transport = transport
        self.idle_timeout_seconds = idle_timeout_seconds

        self._protocol = McpProtocolHandler()
        self._lock = asyncio.Lock()
        self._last_active_at = time.time()
        self._idle_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> bool:
        return (
            self.record.status == McpServerStatus.CONNECTED
            and self.transport is not None
            and self.transport.is_connected
        )

    async def connect(self) -> None:
        """Establish transport connection, execute protocol handshake, and discover capabilities."""
        async with self._lock:
            if self.is_connected:
                return

            if not self.record.config.is_approved:
                raise McpSecurityError(
                    f"Cannot connect to MCP server '{self.record.config.id}': Launch configuration is not approved by operator."
                )

            # Fingerprint integrity verification
            current_fp = compute_manifest_fingerprint(
                command=self.record.config.command,
                args=self.record.config.args,
                env=self.record.config.env,
                working_dir=self.record.config.working_dir,
            )
            if self.record.approved_fingerprint and self.record.approved_fingerprint != current_fp:
                self.record.config.is_approved = False
                self.record.status = McpServerStatus.DISCOVERED
                raise McpSecurityError(
                    f"Cannot connect to MCP server '{self.record.config.id}': Launch configuration has been modified since approval (fingerprint mismatch). Re-authorization required."
                )

            if not self.record.config.is_enabled:
                raise McpSecurityError(
                    f"Cannot connect to MCP server '{self.record.config.id}': Server is disabled by operator policy."
                )

            logger.info("Connecting to MCP server '%s'...", self.record.config.id)

            try:
                # Instantiate transport if not injected (e.g. for testing)
                if self.transport is None:
                    resolved_env = self.vault.resolve_environment(self.record.config.env)
                    self.transport = StdioTransport(
                        command=self.record.config.command,
                        args=self.record.config.args,
                        env=resolved_env,
                        working_dir=self.record.config.working_dir,
                    )

                await self.transport.connect()

                # Step 1: Handshake initialize
                init_id, init_msg = self._protocol.build_initialize(
                    client_name="Nexora",
                    client_version=get_settings().APP_VERSION,
                )
                await self.transport.send_message(init_msg)
                init_resp = await asyncio.wait_for(self.transport.receive_message(), timeout=10.0)
                init_result = self._protocol.parse_response(init_resp, expected_id=init_id)
                self.record.protocol_version = init_result.get("protocolVersion")

                # Step 2: Handshake initialized notification
                await self.transport.send_message(self._protocol.build_initialized())

                # Step 3: Capability discovery (tools/list)
                tools_id, tools_msg = self._protocol.build_tools_list()
                await self.transport.send_message(tools_msg)
                tools_resp = await asyncio.wait_for(self.transport.receive_message(), timeout=10.0)
                tools_result = self._protocol.parse_response(tools_resp, expected_id=tools_id)

                discovered_tools: list[McpToolDefinition] = []
                for t in tools_result.get("tools", []):
                    discovered_tools.append(
                        McpToolDefinition(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            input_schema=t.get("inputSchema", {}),
                        )
                    )

                self.record.advertised_tools = discovered_tools
                self.record.status = McpServerStatus.CONNECTED
                self.record.last_connected_at = datetime.now(timezone.utc).isoformat()
                self.record.last_error = None
                self._last_active_at = time.time()

                # Start idle connection timer
                if self._idle_task is None or self._idle_task.done():
                    self._idle_task = asyncio.create_task(self._monitor_idle())

                logger.info(
                    "Connected to MCP server '%s' (v%s, %d tools advertised).",
                    self.record.config.id,
                    self.record.protocol_version,
                    len(self.record.advertised_tools),
                )

            except Exception as e:
                self.record.status = McpServerStatus.ERROR
                self.record.last_error = str(e)
                logger.error("Connection failed for MCP server '%s': %s", self.record.config.id, e)
                if self.transport:
                    await self.transport.close()
                raise

    async def _monitor_idle(self) -> None:
        """Background coroutine that shuts down idle subprocess after timeout."""
        try:
            while self.is_connected:
                await asyncio.sleep(15.0)
                idle_duration = time.time() - self._last_active_at
                if idle_duration >= self.idle_timeout_seconds:
                    logger.info(
                        "MCP server '%s' reached idle timeout (%.1f s); cleanly shutting down process.",
                        self.record.config.id,
                        idle_duration,
                    )
                    await self.disconnect()
                    break
        except asyncio.CancelledError:
            pass

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float = 30.0,
    ) -> Any:
        """Invoke an advertised tool on the remote server with timeout enforcement."""
        if not self.is_connected:
            await self.connect()

        async with self._lock:
            self._last_active_at = time.time()
            req_id, call_msg = self._protocol.build_tools_call(tool_name, arguments)

            try:
                await self.transport.send_message(call_msg)
                resp = await asyncio.wait_for(
                    self.transport.receive_message(), timeout=timeout_seconds
                )
                if resp is None:
                    raise McpProtocolError(-32000, "MCP server closed pipe unexpectedly during tool execution.")
                return self._protocol.parse_response(resp, expected_id=req_id)
            except asyncio.TimeoutError:
                logger.error("Tool '%s' on server '%s' timed out after %.1f s", tool_name, self.record.config.id, timeout_seconds)
                raise McpProtocolError(-32000, f"Tool execution timed out after {timeout_seconds}s")
            except Exception as e:
                logger.error("Tool execution failed on MCP server '%s': %s", self.record.config.id, e)
                raise

    async def ping(self) -> float:
        """Send JSON-RPC ping request and measure roundtrip latency in milliseconds."""
        if not self.is_connected:
            await self.connect()

        async with self._lock:
            self._last_active_at = time.time()
            req_id, ping_msg = self._protocol.build_ping()
            start = time.perf_counter()
            await self.transport.send_message(ping_msg)
            resp = await asyncio.wait_for(self.transport.receive_message(), timeout=5.0)
            latency_ms = (time.perf_counter() - start) * 1000.0
            self._protocol.parse_response(resp, expected_id=req_id)
            self.record.ping_latency_ms = round(latency_ms, 2)
            return self.record.ping_latency_ms

    async def disconnect(self) -> None:
        """Cleanly close connection and terminate server subprocess."""
        if self._idle_task:
            self._idle_task.cancel()
            self._idle_task = None

        if self.transport:
            await self.transport.close()

        self.record.status = McpServerStatus.STOPPED
        logger.info("Disconnected MCP server '%s'.", self.record.config.id)


class McpSessionPool:
    """Manages active McpClientSession instances and idle pooling across all registered servers."""

    def __init__(
        self,
        registry: McpServerRegistry,
        vault: McpVaultService,
        idle_timeout_seconds: float = 600.0,
    ):
        self.registry = registry
        self.vault = vault
        self.idle_timeout_seconds = idle_timeout_seconds
        self._sessions: dict[str, McpClientSession] = {}

    def get_session(self, server_id: str) -> Optional[McpClientSession]:
        """Retrieve existing active session for a server."""
        return self._sessions.get(server_id)

    def get_or_create_session(
        self,
        server_id: str,
        transport: Optional[McpTransport] = None,
    ) -> McpClientSession:
        """Retrieve or instantiate a session for a registered server."""
        if server_id in self._sessions:
            sess = self._sessions[server_id]
            if transport is not None and sess.transport is not transport:
                sess.transport = transport
            return sess

        record = self.registry.get_server(server_id)
        if not record:
            raise ValueError(f"MCP server '{server_id}' is not registered.")

        session = McpClientSession(
            record=record,
            vault=self.vault,
            transport=transport,
            idle_timeout_seconds=self.idle_timeout_seconds,
        )
        self._sessions[server_id] = session
        return session

    async def disconnect_server(self, server_id: str) -> None:
        """Disconnect and evict a server session."""
        session = self._sessions.pop(server_id, None)
        if session:
            await session.disconnect()
            self.registry.update_runtime_state(server_id, status=McpServerStatus.STOPPED)

    async def disconnect_all(self) -> None:
        """Cleanly disconnect all active server sessions (e.g. during shutdown)."""
        logger.info("Closing all active MCP server sessions (%d active)...", len(self._sessions))
        for sid, session in list(self._sessions.items()):
            try:
                await session.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting MCP server '%s': %s", sid, e)
        self._sessions.clear()
