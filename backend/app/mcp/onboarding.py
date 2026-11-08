"""MCP Server Onboarding Service, Manifest Fingerprinting, and Safe Handshake Discovery."""

import asyncio
from datetime import datetime, timezone
import logging
import re
import time
from typing import Optional

from backend.app.core.config import get_settings
from backend.app.mcp.models import (
    McpInspectionReport,
    McpServerConfig,
    McpServerRecord,
    McpServerStatus,
    McpTestConnectionResult,
    McpToolDefinition,
    compute_manifest_fingerprint,
)
from backend.app.mcp.protocol import McpProtocolHandler
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.transport import StdioTransport
from backend.app.mcp.vault import McpVaultService
from backend.app.models.agent import RiskLevel

logger = logging.getLogger("nexora.mcp.onboarding")

HIGH_RISK_PATTERNS = [
    re.compile(r"-(?:enc|encodedcommand)\b", re.IGNORECASE),
    re.compile(r"\b(?:iex|invoke-expression|downloadstring)\b", re.IGNORECASE),
    re.compile(r"\b(?:nc|ncat|netcat)\b", re.IGNORECASE),
    re.compile(r"\b(?:eval|exec)\s*\(", re.IGNORECASE),
    re.compile(r"[;&|`$]", re.IGNORECASE),
]


class McpOnboardingService:
    """Provides security inspection, non-executing handshake verification, and cryptographic approval."""

    def __init__(
        self,
        registry: Optional[McpServerRegistry] = None,
        vault: Optional[McpVaultService] = None,
    ):
        self.registry = registry or McpServerRegistry()
        self.vault = vault or McpVaultService()

    def inspect_manifest(self, config: McpServerConfig) -> McpInspectionReport:
        """Statically inspect an MCP server manifest for security risks and missing secrets."""
        fingerprint = compute_manifest_fingerprint(
            command=config.command,
            args=config.args,
            env=config.env,
            working_dir=config.working_dir,
        )

        warnings: list[str] = []
        risk_level = RiskLevel.SENSITIVE

        # 1. Inspect command and arguments for high-risk flags or injection patterns
        full_invocation = f"{config.command} {' '.join(config.args)}"
        for pattern in HIGH_RISK_PATTERNS:
            if pattern.search(full_invocation):
                warnings.append(f"Suspicious argument or injection pattern detected: '{pattern.pattern}'")
                risk_level = RiskLevel.SENSITIVE

        # Check for unapproved script execution
        cmd_lower = config.command.lower()
        if "cmd.exe" in cmd_lower or "powershell" in cmd_lower or "bash" in cmd_lower or "sh" in cmd_lower:
            warnings.append("Shell wrappers (cmd/powershell/bash) detected. Native executable launch preferred.")
            risk_level = RiskLevel.SENSITIVE

        # 2. Check vault secret references
        referenced_secrets: list[str] = []
        missing_secrets: list[str] = []
        for env_val in config.env.values():
            if env_val.startswith("ref:vault/"):
                sec_key = env_val[len("ref:vault/"):].strip()
                referenced_secrets.append(sec_key)
                if not self.vault.has_secret(sec_key):
                    missing_secrets.append(sec_key)

        if missing_secrets:
            warnings.append(f"Missing vault secrets: {', '.join(missing_secrets)}")

        is_valid = len(missing_secrets) == 0 and not any("Suspicious" in w for w in warnings)

        return McpInspectionReport(
            server_id=config.id,
            fingerprint=fingerprint,
            risk_level=risk_level,
            warnings=warnings,
            referenced_secrets=referenced_secrets,
            missing_secrets=missing_secrets,
            is_valid=is_valid,
        )

    async def test_connection(
        self,
        config: McpServerConfig,
        timeout_seconds: float = 8.0,
    ) -> McpTestConnectionResult:
        """Safely connect to server via stdio, execute protocol handshake, discover tools, and immediately shut down."""
        protocol = McpProtocolHandler()
        start_time = time.time()
        transport: Optional[StdioTransport] = None

        try:
            # Resolve env (missing secrets get empty placeholder for handshake)
            resolved_env = {}
            for k, v in config.env.items():
                if v.startswith("ref:vault/"):
                    sec_key = v[len("ref:vault/"):].strip()
                    secret_val = self.vault.get_secret(sec_key)
                    resolved_env[k] = secret_val or ""
                else:
                    resolved_env[k] = v

            transport = StdioTransport(
                command=config.command,
                args=config.args,
                env=resolved_env,
                working_dir=config.working_dir,
            )

            await asyncio.wait_for(transport.connect(), timeout=timeout_seconds)

            # Step 1: Handshake initialize
            init_id, init_msg = protocol.build_initialize(
                client_name="Nexora-Onboard-Probe",
                client_version=get_settings().APP_VERSION,
            )
            await transport.send_message(init_msg)
            init_resp = await asyncio.wait_for(transport.receive_message(), timeout=timeout_seconds / 2)
            init_result = protocol.parse_response(init_resp, expected_id=init_id)
            proto_version = init_result.get("protocolVersion", "unknown")

            # Step 2: Handshake initialized notification
            await transport.send_message(protocol.build_initialized())

            # Step 3: Tool discovery (tools/list)
            tools_id, tools_msg = protocol.build_tools_list()
            await transport.send_message(tools_msg)
            tools_resp = await asyncio.wait_for(transport.receive_message(), timeout=timeout_seconds / 2)
            tools_result = protocol.parse_response(tools_resp, expected_id=tools_id)

            discovered_tools: list[McpToolDefinition] = []
            for t in tools_result.get("tools", []):
                discovered_tools.append(
                    McpToolDefinition(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {}),
                    )
                )

            latency_ms = (time.time() - start_time) * 1000.0

            return McpTestConnectionResult(
                server_id=config.id,
                success=True,
                protocol_version=proto_version,
                discovered_tools_count=len(discovered_tools),
                tools=discovered_tools,
                latency_ms=round(latency_ms, 2),
                error_message=None,
            )
        except Exception as e:
            logger.warning("MCP connection test failed for '%s': %s", config.id, e)
            return McpTestConnectionResult(
                server_id=config.id,
                success=False,
                error_message=str(e),
            )
        finally:
            # Crucial: Always cleanly shut down the child process immediately after probe
            if transport:
                try:
                    await transport.disconnect()
                except Exception:
                    pass

    def approve_manifest(
        self,
        server_id: str,
        operator: str = "operator",
    ) -> Optional[McpServerRecord]:
        """Approve an MCP server configuration by binding its immutable fingerprint."""
        record = self.registry.get_server(server_id)
        if not record:
            return None

        fp = compute_manifest_fingerprint(
            command=record.config.command,
            args=record.config.args,
            env=record.config.env,
            working_dir=record.config.working_dir,
        )

        record.fingerprint = fp
        record.approved_fingerprint = fp
        record.approved_at = datetime.now(timezone.utc).isoformat()
        record.approved_by = operator
        record.config.is_approved = True
        record.status = McpServerStatus.APPROVED

        self.registry._save_to_disk()
        logger.info("Server '%s' approved with fingerprint %s by %s", server_id, fp[:12], operator)
        return record
