"""Security gate, deterministic secret scrubbing, and integrity hashing for Memory."""

import hashlib
import re
from typing import Optional, Tuple

from backend.app.memory.models import MemoryCategory, SensitivityLevel

# Pre-compiled high-precision secret detection regexes
SECRET_PATTERNS = [
    # GitHub Tokens
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    # OpenAI & Standard API Keys
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    # Google AI / GCP API keys
    re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    # Generic Bearer Tokens
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-_.~+/]{20,}"),
    # PEM Private Keys
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # Explicit Password & Secret Assignments
    re.compile(r"(?i)\b(password|secret|api_key|token|access_key)\s*[:=]\s*['\"][^\s'\"]{6,}['\"]"),
]


class MemorySecurityException(ValueError):
    """Raised when proposed memory violates security rules."""
    pass


class MemorySecurityGate:
    """Enforces zero-secret storage and deterministic integrity hashing."""

    @staticmethod
    def scrub_secrets(text: str) -> str:
        """Replace all recognized credential, token, and secret patterns with [REDACTED_SECRET]."""
        scrubbed = text
        for pattern in SECRET_PATTERNS:
            scrubbed = pattern.sub("[REDACTED_SECRET]", scrubbed)
        return scrubbed

    @staticmethod
    def contains_secret(text: str) -> Tuple[bool, Optional[str]]:
        """Check if text contains any recognized secret, token, or password pattern."""
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                # Return redacted preview of violation
                matched_snippet = match.group(0)
                redacted_snippet = matched_snippet[:4] + "..." + matched_snippet[-3:] if len(matched_snippet) > 8 else "***"
                return True, f"Detected potential credential pattern ({redacted_snippet})"
        return False, None

    @staticmethod
    def compute_version_hash(key: str, value: str, sensitivity: SensitivityLevel | str) -> str:
        """Compute deterministic SHA-256 integrity hash for a memory record."""
        sens_str = sensitivity.value if isinstance(sensitivity, SensitivityLevel) else str(sensitivity)
        payload = f"{key.strip()}:::{value.strip()}:::{sens_str}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def verify_integrity(key: str, value: str, sensitivity: SensitivityLevel | str, version_hash: str) -> bool:
        """Verify record content matches the recorded cryptographic version hash."""
        expected_hash = MemorySecurityGate.compute_version_hash(key, value, sensitivity)
        return expected_hash == version_hash

    @staticmethod
    def evaluate_sensitivity(category: MemoryCategory, key: str, value: str) -> SensitivityLevel:
        """Evaluate appropriate sensitivity tier based on category and content."""
        lower_key = key.lower()
        lower_val = value.lower()

        # Sensitive system or security-adjacent keywords
        high_risk_words = {"auth", "credential", "security", "permission", "admin", "private", "cert", "tunnel"}
        if any(w in lower_key or w in lower_val for w in high_risk_words):
            return SensitivityLevel.HIGH

        # Preferences are generally low sensitivity
        if category == MemoryCategory.USER_PREFERENCE:
            return SensitivityLevel.LOW

        # Project facts default to Medium
        return SensitivityLevel.MEDIUM
