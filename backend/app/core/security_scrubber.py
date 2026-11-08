"""Global secret scrubbing boundary for transcripts, logs, and work items."""

from __future__ import annotations

from backend.app.memory.security import MemorySecurityGate


def scrub_secrets(text: str) -> str:
    """Scrub sensitive credentials, tokens, and keys from any text."""
    if not text:
        return ""
    return MemorySecurityGate.scrub_secrets(text)
