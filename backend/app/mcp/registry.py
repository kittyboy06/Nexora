"""MCP Server Configuration and Lifecycle State Registry."""

import json
import logging
from pathlib import Path
from typing import Optional

from backend.app.core.config import get_settings
from backend.app.mcp.models import (
    McpServerConfig,
    McpServerRecord,
    McpServerStatus,
    McpServerUpdateRequest,
    McpToolDefinition,
)

logger = logging.getLogger("nexora.mcp.registry")


class McpServerRegistry:
    """Manages persistence of server manifests, approval states, and advertised capabilities."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_settings().get_mcp_data_dir()
        self.servers_file = self.base_dir / "servers.json"
        self._servers: dict[str, McpServerRecord] = {}
        self._ensure_storage()
        self.reload()

    def _ensure_storage(self) -> None:
        """Create base directory and initialize empty servers.json if missing."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.servers_file.exists():
            self._save_to_disk({})

    def reload(self) -> None:
        """Load servers.json from disk into memory."""
        self._servers.clear()
        if not self.servers_file.exists():
            return

        try:
            with open(self.servers_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            for sid, sdata in raw_data.items():
                record = McpServerRecord(**sdata)
                # Ensure runtime status is reset to STOPPED or DISCOVERED on restart
                if record.status == McpServerStatus.CONNECTED:
                    record.status = McpServerStatus.STOPPED
                self._servers[sid] = record
        except Exception as e:
            logger.error("Failed to load servers.json: %s", e)

    def _save_to_disk(self, data: Optional[dict] = None) -> None:
        """Write current in-memory servers to servers.json."""
        payload = data if data is not None else {
            sid: record.model_dump(mode="json") for sid, record in self._servers.items()
        }
        try:
            with open(self.servers_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.error("Failed to save servers.json: %s", e)

    def list_servers(self) -> list[McpServerRecord]:
        """Return all registered MCP server records."""
        return sorted(list(self._servers.values()), key=lambda s: s.config.id)

    def get_server(self, server_id: str) -> Optional[McpServerRecord]:
        """Retrieve a specific server record by ID."""
        return self._servers.get(server_id)

    def register_server(self, config: McpServerConfig) -> McpServerRecord:
        """Register a new server configuration. Requires operator approval before launch."""
        status = McpServerStatus.APPROVED if config.is_approved else McpServerStatus.DISCOVERED
        record = McpServerRecord(
            config=config,
            status=status,
            advertised_tools=[],
        )
        self._servers[config.id] = record
        self._save_to_disk()
        logger.info("Registered MCP server '%s' (status: %s)", config.id, status)
        return record

    def update_server(self, server_id: str, update: McpServerUpdateRequest) -> Optional[McpServerRecord]:
        """Update server configuration. Reset approval if command, args, or env changed."""
        record = self._servers.get(server_id)
        if not record:
            return None

        cfg = record.config
        security_altered = False

        if update.name is not None:
            cfg.name = update.name
        if update.description is not None:
            cfg.description = update.description
        if update.command is not None and update.command != cfg.command:
            cfg.command = update.command
            security_altered = True
        if update.args is not None and update.args != cfg.args:
            cfg.args = update.args
            security_altered = True
        if update.env is not None and update.env != cfg.env:
            cfg.env = update.env
            security_altered = True
        if update.working_dir is not None and update.working_dir != cfg.working_dir:
            cfg.working_dir = update.working_dir
            security_altered = True
        if update.is_enabled is not None:
            cfg.is_enabled = update.is_enabled

        # Reset approval if security-relevant fields were modified
        if security_altered:
            cfg.is_approved = False
            record.status = McpServerStatus.DISCOVERED
            logger.warning(
                "MCP server '%s' configuration changed; approval revoked. Operator must re-approve.",
                server_id,
            )

        self._save_to_disk()
        return record

    def approve_server(self, server_id: str) -> Optional[McpServerRecord]:
        """Mark a server's launch configuration as approved by the operator."""
        record = self._servers.get(server_id)
        if not record:
            return None

        record.config.is_approved = True
        record.status = McpServerStatus.APPROVED
        self._save_to_disk()
        logger.info("MCP server '%s' approved by operator.", server_id)
        return record

    def update_runtime_state(
        self,
        server_id: str,
        status: McpServerStatus,
        advertised_tools: Optional[list[McpToolDefinition]] = None,
        protocol_version: Optional[str] = None,
        ping_latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> Optional[McpServerRecord]:
        """Update runtime telemetry for an active or failed server."""
        record = self._servers.get(server_id)
        if not record:
            return None

        record.status = status
        if advertised_tools is not None:
            record.advertised_tools = advertised_tools
        if protocol_version is not None:
            record.protocol_version = protocol_version
        if ping_latency_ms is not None:
            record.ping_latency_ms = ping_latency_ms
        if error is not None:
            record.last_error = error

        self._save_to_disk()
        return record

    def delete_server(self, server_id: str) -> bool:
        """Remove a server record from registry."""
        if server_id in self._servers:
            del self._servers[server_id]
            self._save_to_disk()
            logger.info("Deleted MCP server '%s' from registry.", server_id)
            return True
        return False
