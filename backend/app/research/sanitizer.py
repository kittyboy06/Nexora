"""Sanitization and Anti-Prompt-Injection Quotation Boundaries for Phase 9."""

import re
from pathlib import Path


# Delimiters and tokens that hostile web content might use to trick the LLM
FORBIDDEN_TAGS_PATTERN = re.compile(
    r"</?(?:untrusted_web_evidence|system|antigravity|USER_REQUEST|CONTEXT_SUMMARY)[^>]*>",
    re.IGNORECASE,
)

UNSAFE_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_web_content(content: str, max_chars: int = 100_000) -> str:
    """
    Sanitize raw extracted text from an untrusted webpage:
    1. Escapes delimiter tags that could break out of quotation containers.
    2. Enforces maximum character bounds.
    """
    if not content:
        return ""

    # Neutralize any tags that mimic system prompt framing or quotation closing
    sanitized = FORBIDDEN_TAGS_PATTERN.sub(lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), content)

    # Bounded truncation
    if len(sanitized) > max_chars:
        sanitized = sanitized[:max_chars] + f"\n\n[... content truncated at {max_chars:,} characters by research policy ...]"

    return sanitized


def wrap_untrusted_evidence(
    content: str,
    url: str,
    title: str = "",
    content_hash: str = "",
    max_chars: int = 100_000,
) -> str:
    """
    Encapsulates untrusted webpage content in strict XML quotation boundaries.
    Communicates to LLM that enclosed text is external source data and cannot issue system commands.
    """
    cleaned = sanitize_web_content(content, max_chars=max_chars)
    safe_title = (title or "").replace('"', '&quot;').replace("<", "&lt;").replace(">", "&gt;")
    safe_url = (url or "").replace('"', '&quot;').replace("<", "&lt;").replace(">", "&gt;")

    return (
        f'<untrusted_web_evidence source="{safe_url}" title="{safe_title}" hash="{content_hash}">\n'
        f"{cleaned}\n"
        f"</untrusted_web_evidence>"
    )


def sanitize_quarantine_filename(raw_filename: str, fallback_ext: str = ".bin") -> str:
    """
    Sanitize remote or user-provided filename to prevent directory traversal and invalid Windows characters.
    """
    if not raw_filename or not raw_filename.strip():
        return f"download{fallback_ext}"

    # Extract basename to strip ../ or C:\
    base = Path(raw_filename.strip()).name

    # Replace forbidden Windows / filesystem characters with underscore
    sanitized = UNSAFE_CHARS_PATTERN.sub("_", base).strip(" .")

    if not sanitized:
        sanitized = f"download{fallback_ext}"

    # Keep length bounded
    if len(sanitized) > 120:
        p = Path(sanitized)
        ext = p.suffix
        stem = p.stem[: 120 - len(ext)]
        sanitized = f"{stem}{ext}"

    return sanitized
