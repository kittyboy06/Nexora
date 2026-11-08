"""Domain Models for Phase 8: Universal MCP Platform."""

import hashlib
import json
from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.agent import RiskLevel


def compute_manifest_fingerprint(
    command: str,
    args: list[str],
    env: dict[str, str],
    working_dir: Optional[str] = None,
) -> str:
    """Compute deterministic SHA-256 fingerprint over normalized launch configuration."""
    canonical = {
        "command": command.strip().lower(),
        "args": [str(a).strip() for a in args],
        "working_dir": str(working_dir).strip().lower() if working_dir else "",
        "env_keys": sorted(list(env.keys())),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class McpServerStatus(str, Enum):
    """Lifecycle and operational state of a registered MCP server."""

    DISCOVERED = "DISCOVERED"          # Inspected/created; awaiting operator review
    APPROVED = "APPROVED"              # Approved to launch; not currently running
    CONNECTED = "CONNECTED"            # Active stdio pipe; protocol handshake complete
    STOPPED = "STOPPED"                # Process idle or cleanly stopped
    ERROR = "ERROR"                    # Process crashed, handshake failed, or pipe error
    REVOKED = "REVOKED"                # Disabled or revoked by operator policy


class McpServerConfig(BaseModel):
    """Declarative launch and environment configuration for an MCP server."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(
        ...,
        pattern=r"^[a-z0-9\-_]+$",
        min_length=1,
        max_length=64,
        description="Unique slug identifier for the MCP server",
    )
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    description: str = Field(default="", max_length=500, description="Summary of server capabilities")
    transport: Literal["stdio", "sse"] = Field(
        default="stdio",
        description="Underlying protocol transport mechanism",
    )
    command: str = Field(..., description="Executable path or CLI name (e.g. npx, uvx, python, binary)")
    args: list[str] = Field(default_factory=list, description="CLI command line arguments")
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables. Values with prefix 'ref:vault/<key>' are resolved from vault",
    )
    working_dir: Optional[str] = Field(default=None, description="Optional working directory for child process")
    is_approved: bool = Field(default=False, description="Whether the launch configuration has been approved by operator")
    is_enabled: bool = Field(default=True, description="Whether the server is enabled for tool execution")


class McpToolDefinition(BaseModel):
    """Advertised tool capability discovered during MCP tools/list negotiation."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Raw tool name advertised by the server")
    description: str = Field(default="", description="Tool documentation advertised by server")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for input parameters")
    risk_level: RiskLevel = Field(
        default=RiskLevel.SENSITIVE,
        description="Operator-assigned risk level; unclassified external capabilities require approval",
    )


class McpServerRecord(BaseModel):
    """In-memory and persisted record tracking an MCP server's state and capabilities."""

    model_config = ConfigDict(extra="ignore")

    config: McpServerConfig
    status: McpServerStatus = McpServerStatus.DISCOVERED
    fingerprint: str = ""
    approved_fingerprint: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    advertised_tools: list[McpToolDefinition] = Field(default_factory=list)
    protocol_version: Optional[str] = None
    last_connected_at: Optional[str] = None
    last_error: Optional[str] = None
    ping_latency_ms: Optional[float] = None


class McpVaultItemSummary(BaseModel):
    """Metadata summary of a secret stored in the encrypted local vault."""

    key: str
    description: str = ""
    created_at: str
    has_value: bool = True  # Plaintext secret is never serialized to UI or API responses


class McpVaultWriteRequest(BaseModel):
    """Request payload to set or update a secret in the encrypted vault."""

    key: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        min_length=1,
        max_length=64,
        description="Key identifier for the secret",
    )
    secret_value: str = Field(..., min_length=1, description="Plaintext secret value to encrypt")
    description: str = Field(default="", max_length=200, description="Optional description of the secret")


class McpServerCreateRequest(BaseModel):
    """Request to register a new MCP server configuration."""

    id: str = Field(..., pattern=r"^[a-z0-9\-_]+$", min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    command: str = Field(...)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    working_dir: Optional[str] = None


class McpServerUpdateRequest(BaseModel):
    """Request to update an existing MCP server configuration."""

    name: Optional[str] = None
    description: Optional[str] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    env: Optional[dict[str, str]] = None
    working_dir: Optional[str] = None
    is_enabled: Optional[bool] = None


class McpInspectionReport(BaseModel):
    """Static inspection and risk assessment report for an MCP launch configuration."""

    server_id: str
    fingerprint: str
    risk_level: RiskLevel = RiskLevel.SENSITIVE
    warnings: list[str] = Field(default_factory=list)
    referenced_secrets: list[str] = Field(default_factory=list)
    missing_secrets: list[str] = Field(default_factory=list)
    is_valid: bool = True


class McpTestConnectionResult(BaseModel):
    """Result of safe non-executing MCP handshake probe."""

    server_id: str
    success: bool
    protocol_version: Optional[str] = None
    discovered_tools_count: int = 0
    tools: list[McpToolDefinition] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None


class McpOnboardApproveRequest(BaseModel):
    """Payload to authorize an MCP server configuration by binding its immutable fingerprint."""

    server_id: str
    fingerprint: str
    operator: str = "operator"
