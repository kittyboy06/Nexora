"""FastAPI Endpoints for MCP Server Management, Approval, and Vault Secrets."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.mcp.bridge import McpCapabilityBridge
from backend.app.mcp.models import (
    McpServerConfig,
    McpServerCreateRequest,
    McpServerRecord,
    McpServerStatus,
    McpServerUpdateRequest,
    McpVaultItemSummary,
    McpVaultWriteRequest,
)
from backend.app.mcp.protocol import McpProtocolError
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.session import McpSecurityError, McpSessionPool
from backend.app.mcp.vault import McpVaultService
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.mcp.router")

router = APIRouter(prefix="/mcp", tags=["mcp"])


def get_mcp_registry(request: Request) -> McpServerRegistry:
    registry = getattr(request.app.state, "mcp_registry", None)
    if registry is None:
        registry = McpServerRegistry()
        request.app.state.mcp_registry = registry
    return registry


def get_mcp_vault(request: Request) -> McpVaultService:
    vault = getattr(request.app.state, "mcp_vault", None)
    if vault is None:
        vault = McpVaultService()
        request.app.state.mcp_vault = vault
    return vault


def get_mcp_session_pool(request: Request) -> McpSessionPool:
    pool = getattr(request.app.state, "mcp_session_pool", None)
    if pool is None:
        registry = get_mcp_registry(request)
        vault = get_mcp_vault(request)
        pool = McpSessionPool(registry=registry, vault=vault)
        request.app.state.mcp_session_pool = pool
    return pool


def get_tool_registry(request: Request) -> ToolRegistry:
    tool_registry = getattr(request.app.state, "tool_registry", None)
    if tool_registry is None:
        tool_registry = ToolRegistry()
        request.app.state.tool_registry = tool_registry
    return tool_registry


# ---------------------------------------------------------------------------
# Vault Secret Endpoints
# ---------------------------------------------------------------------------


@router.get("/vault", response_model=list[McpVaultItemSummary])
async def list_vault_secrets(
    vault: McpVaultService = Depends(get_mcp_vault),
) -> list[McpVaultItemSummary]:
    """List metadata summaries of secrets in the encrypted vault."""
    return vault.list_secrets()


@router.post("/vault")
async def write_vault_secret(
    req: McpVaultWriteRequest,
    vault: McpVaultService = Depends(get_mcp_vault),
) -> dict:
    """Add or update an encrypted secret in the local vault."""
    vault.set_secret(req.key, req.secret_value, req.description)
    return {"status": "saved", "key": req.key}


@router.delete("/vault/{key}")
async def delete_vault_secret(
    key: str,
    vault: McpVaultService = Depends(get_mcp_vault),
) -> dict:
    """Delete a secret from the encrypted vault."""
    deleted = vault.delete_secret(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found in vault.")
    return {"status": "deleted", "key": key}


# ---------------------------------------------------------------------------
# Server Configuration & Lifecycle Endpoints
# ---------------------------------------------------------------------------


@router.get("/servers", response_model=list[McpServerRecord])
async def list_servers(
    registry: McpServerRegistry = Depends(get_mcp_registry),
) -> list[McpServerRecord]:
    """List all registered MCP servers and their current status."""
    return registry.list_servers()


@router.post("/servers", response_model=McpServerRecord)
async def register_server(
    req: McpServerCreateRequest,
    registry: McpServerRegistry = Depends(get_mcp_registry),
) -> McpServerRecord:
    """Register a new MCP server configuration. Requires approval before launch."""
    existing = registry.get_server(req.id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Server with ID '{req.id}' already exists.")

    cfg = McpServerConfig(
        id=req.id,
        name=req.name,
        description=req.description,
        command=req.command,
        args=req.args,
        env=req.env,
        working_dir=req.working_dir,
        is_approved=False,
    )
    return registry.register_server(cfg)


@router.get("/servers/{server_id}", response_model=McpServerRecord)
async def get_server(
    server_id: str,
    registry: McpServerRegistry = Depends(get_mcp_registry),
) -> McpServerRecord:
    """Retrieve full record for an MCP server."""
    record = registry.get_server(server_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return record


@router.put("/servers/{server_id}", response_model=McpServerRecord)
async def update_server(
    server_id: str,
    update: McpServerUpdateRequest,
    registry: McpServerRegistry = Depends(get_mcp_registry),
    pool: McpSessionPool = Depends(get_mcp_session_pool),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> McpServerRecord:
    """Update server configuration. If command/args/env change, approval is revoked and session stopped."""
    # Disconnect active session if running
    await pool.disconnect_server(server_id)
    McpCapabilityBridge.unregister_server_tools(server_id, tool_registry)

    updated = registry.update_server(server_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return updated


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: str,
    registry: McpServerRegistry = Depends(get_mcp_registry),
    pool: McpSessionPool = Depends(get_mcp_session_pool),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> dict:
    """Disconnect session, unregister tools, and delete server configuration."""
    await pool.disconnect_server(server_id)
    McpCapabilityBridge.unregister_server_tools(server_id, tool_registry)

    deleted = registry.delete_server(server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return {"status": "deleted", "id": server_id}


@router.post("/servers/{server_id}/approve", response_model=McpServerRecord)
async def approve_server(
    server_id: str,
    registry: McpServerRegistry = Depends(get_mcp_registry),
) -> McpServerRecord:
    """Explicit operator approval for server launch configuration."""
    approved = registry.approve_server(server_id)
    if not approved:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return approved


@router.post("/servers/{server_id}/connect", response_model=McpServerRecord)
async def connect_server(
    server_id: str,
    registry: McpServerRegistry = Depends(get_mcp_registry),
    pool: McpSessionPool = Depends(get_mcp_session_pool),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> McpServerRecord:
    """Connect to approved server, complete handshake, and register tools in ToolRegistry."""
    record = registry.get_server(server_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")

    if not record.config.is_approved:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot connect to server '{server_id}': Launch configuration is not approved by operator.",
        )

    try:
        session = pool.get_or_create_session(server_id)
        await session.connect()

        # Register advertised capabilities into central ToolRegistry
        McpCapabilityBridge.register_server_tools(
            server_id=server_id,
            tools=session.record.advertised_tools,
            session=session,
            registry=tool_registry,
        )

        updated = registry.update_runtime_state(
            server_id=server_id,
            status=McpServerStatus.CONNECTED,
            advertised_tools=session.record.advertised_tools,
            protocol_version=session.record.protocol_version,
        )
        return updated or session.record
    except McpSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        registry.update_runtime_state(server_id=server_id, status=McpServerStatus.ERROR, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to connect to MCP server: {e}")


@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(
    server_id: str,
    registry: McpServerRegistry = Depends(get_mcp_registry),
    pool: McpSessionPool = Depends(get_mcp_session_pool),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> dict:
    """Disconnect active server session and unregister capabilities from ToolRegistry."""
    record = registry.get_server(server_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")

    await pool.disconnect_server(server_id)
    McpCapabilityBridge.unregister_server_tools(server_id, tool_registry)
    return {"status": "disconnected", "id": server_id}


@router.post("/servers/{server_id}/ping")
async def ping_server(
    server_id: str,
    pool: McpSessionPool = Depends(get_mcp_session_pool),
    registry: McpServerRegistry = Depends(get_mcp_registry),
) -> dict:
    """Send JSON-RPC ping to measure roundtrip latency."""
    session = pool.get_session(server_id)
    if not session or not session.is_connected:
        raise HTTPException(status_code=400, detail=f"Server '{server_id}' is not connected.")

    try:
        latency = await session.ping()
        registry.update_runtime_state(server_id, status=McpServerStatus.CONNECTED, ping_latency_ms=latency)
        return {"status": "ok", "latency_ms": latency}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ping failed: {e}")
