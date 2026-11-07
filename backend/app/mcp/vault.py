"""Encrypted Local Vault Service for Opaque MCP Credentials."""

import base64
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import platform
from typing import Optional
import uuid

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from backend.app.core.config import get_settings
from backend.app.mcp.models import McpVaultItemSummary

logger = logging.getLogger("nexora.mcp.vault")


class McpVaultKeyNotFoundError(Exception):
    """Raised when an opaque secret reference cannot be resolved from the vault."""
    pass


class McpVaultService:
    """Manages encrypted key-value storage for API keys and tokens with opaque reference resolution."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        master_key: Optional[bytes] = None,
    ):
        self.base_dir = base_dir or get_settings().get_mcp_data_dir()
        self.vault_file = self.base_dir / "vault.bin"
        self.salt_file = self.base_dir / ".vault_salt"
        self._ensure_storage()

        if master_key:
            self._fernet = Fernet(master_key)
        else:
            derived_key = self._derive_machine_key()
            self._fernet = Fernet(derived_key)

    def _ensure_storage(self) -> None:
        """Create base directory if missing."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_or_create_salt(self) -> bytes:
        """Retrieve or initialize persistent local cryptographic salt."""
        if self.salt_file.exists():
            try:
                return self.salt_file.read_bytes()
            except Exception:
                pass
        # Generate and persist a 16-byte random salt
        salt = base64.b64encode(uuid.uuid4().bytes + str(uuid.getnode()).encode()[:8])[:16]
        try:
            self.salt_file.write_bytes(salt)
        except Exception as e:
            logger.warning("Could not persist vault salt file: %s", e)
        return salt

    def _derive_machine_key(self) -> bytes:
        """Derive a deterministic machine-bound AES key for Fernet."""
        salt = self._get_or_create_salt()
        machine_ident = f"nexora-{uuid.getnode()}-{platform.node()}".encode("utf-8")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        key = kdf.derive(machine_ident)
        return base64.urlsafe_b64encode(key)

    def _load_data(self) -> dict:
        """Read and decrypt vault ciphertext into dictionary."""
        if not self.vault_file.exists():
            return {"secrets": {}, "metadata": {}}

        try:
            ciphertext = self.vault_file.read_bytes()
            if not ciphertext:
                return {"secrets": {}, "metadata": {}}
            plaintext = self._fernet.decrypt(ciphertext)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to decrypt vault file: %s", e)
            return {"secrets": {}, "metadata": {}}

    def _save_data(self, data: dict) -> None:
        """Encrypt and write dictionary payload to vault file."""
        serialized = json.dumps(data).encode("utf-8")
        ciphertext = self._fernet.encrypt(serialized)
        self.vault_file.write_bytes(ciphertext)

    def set_secret(self, key: str, secret_value: str, description: str = "") -> None:
        """Store or update an encrypted secret."""
        if not key or not secret_value:
            raise ValueError("Secret key and value cannot be empty.")

        data = self._load_data()
        data["secrets"][key] = secret_value
        data["metadata"][key] = {
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_data(data)
        logger.info("Encrypted secret '%s' saved to vault.", key)

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve decrypted secret value strictly in-memory."""
        data = self._load_data()
        return data["secrets"].get(key)

    def delete_secret(self, key: str) -> bool:
        """Remove a secret from the encrypted vault."""
        data = self._load_data()
        if key in data["secrets"]:
            del data["secrets"][key]
            data["metadata"].pop(key, None)
            self._save_data(data)
            logger.info("Secret '%s' deleted from vault.", key)
            return True
        return False

    def list_secrets(self) -> list[McpVaultItemSummary]:
        """List metadata summaries of stored secrets without exposing plaintext."""
        data = self._load_data()
        summaries: list[McpVaultItemSummary] = []
        for key, meta in data.get("metadata", {}).items():
            summaries.append(
                McpVaultItemSummary(
                    key=key,
                    description=meta.get("description", ""),
                    created_at=meta.get("created_at", ""),
                    has_value=True,
                )
            )
        return sorted(summaries, key=lambda s: s.key)

    def resolve_environment(self, env_mappings: dict[str, str]) -> dict[str, str]:
        """Resolve all 'ref:vault/<key>' entries into plaintext environment variables.

        Raises McpVaultKeyNotFoundError if any referenced key is missing.
        """
        resolved: dict[str, str] = {}
        for var_name, var_value in env_mappings.items():
            if isinstance(var_value, str) and var_value.startswith("ref:vault/"):
                secret_key = var_value[len("ref:vault/"):]
                secret_val = self.get_secret(secret_key)
                if secret_val is None:
                    raise McpVaultKeyNotFoundError(
                        f"Required secret key '{secret_key}' (for env '{var_name}') "
                        f"was not found in the encrypted vault."
                    )
                resolved[var_name] = secret_val
            else:
                resolved[var_name] = str(var_value)
        return resolved
