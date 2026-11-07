"""Unit tests for McpVaultService, models, and opaque reference resolution."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.app.mcp.models import (
    McpServerConfig,
    McpServerStatus,
    McpToolDefinition,
    McpVaultItemSummary,
)
from backend.app.mcp.vault import McpVaultKeyNotFoundError, McpVaultService
from backend.app.models.agent import RiskLevel


@pytest.fixture
def vault(tmp_path: Path) -> McpVaultService:
    """Provide an isolated vault service instance backed by temp directory."""
    return McpVaultService(base_dir=tmp_path / "mcp")


def test_mcp_models_validation():
    """Verify schema constraints on McpServerConfig and McpToolDefinition."""
    # Valid config
    config = McpServerConfig(
        id="sqlite-server",
        name="SQLite Server",
        command="python",
        args=["-m", "mcp_server_sqlite"],
        env={"DB_PATH": "data/app.db"},
    )
    assert config.id == "sqlite-server"
    assert config.transport == "stdio"
    assert config.is_approved is False

    # Invalid ID with uppercase / spaces
    with pytest.raises(ValidationError):
        McpServerConfig(
            id="SQLite Server!",
            name="SQLite",
            command="python",
        )

    # Valid tool definition
    tool = McpToolDefinition(
        name="read_query",
        description="Execute a SELECT query",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        risk_level=RiskLevel.SAFE,
    )
    assert tool.name == "read_query"
    assert tool.risk_level == RiskLevel.SAFE


def test_vault_encryption_roundtrip(vault: McpVaultService):
    """Verify secrets are encrypted on disk and decrypted in memory."""
    vault.set_secret("github_token", "ghp_secret_access_token_12345", description="GitHub PAT")

    # Raw disk inspection: ciphertext must not contain plaintext
    raw_bytes = vault.vault_file.read_bytes()
    assert b"ghp_secret_access_token_12345" not in raw_bytes
    assert b"github_token" not in raw_bytes  # Keys are also inside encrypted payload

    # Decrypted retrieval in-memory
    val = vault.get_secret("github_token")
    assert val == "ghp_secret_access_token_12345"

    # Non-existent key
    assert vault.get_secret("unknown_key") is None


def test_vault_list_secrets(vault: McpVaultService):
    """Verify secret listing returns metadata summaries without leaking secrets."""
    vault.set_secret("api_key_1", "secret_val_1", description="Service 1")
    vault.set_secret("api_key_2", "secret_val_2", description="Service 2")

    summaries = vault.list_secrets()
    assert len(summaries) == 2
    keys = [s.key for s in summaries]
    assert "api_key_1" in keys
    assert "api_key_2" in keys
    for s in summaries:
        assert isinstance(s, McpVaultItemSummary)
        assert s.has_value is True
        # Plaintext is not exposed on summary
        assert not hasattr(s, "secret_value")


def test_vault_delete_secret(vault: McpVaultService):
    """Verify deleting a secret removes it from encrypted storage."""
    vault.set_secret("temp_token", "val_xyz")
    assert vault.get_secret("temp_token") == "val_xyz"

    assert vault.delete_secret("temp_token") is True
    assert vault.get_secret("temp_token") is None
    assert vault.delete_secret("temp_token") is False


def test_vault_resolve_environment_success(vault: McpVaultService):
    """Verify resolving environment mappings with 'ref:vault/<key>'."""
    vault.set_secret("pg_password", "super_secret_db_pass_99")

    raw_env = {
        "HOST": "localhost",
        "PORT": "5432",
        "PGPASSWORD": "ref:vault/pg_password",
    }

    resolved = vault.resolve_environment(raw_env)
    assert resolved["HOST"] == "localhost"
    assert resolved["PORT"] == "5432"
    assert resolved["PGPASSWORD"] == "super_secret_db_pass_99"


def test_vault_resolve_environment_missing_key_raises(vault: McpVaultService):
    """Verify missing secret references raise McpVaultKeyNotFoundError."""
    raw_env = {
        "BRAVE_KEY": "ref:vault/non_existent_key",
    }

    with pytest.raises(McpVaultKeyNotFoundError) as exc_info:
        vault.resolve_environment(raw_env)

    assert "non_existent_key" in str(exc_info.value)
