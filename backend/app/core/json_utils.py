"""Robust JSON extraction utilities for diverse local LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any


def clean_llm_text(text: str) -> str:
    """Strip reasoning/thought tags (<think>...</think>) from model outputs."""
    if not text:
        return ""
    # Strip <think>...</think> blocks (case-insensitive, multiline)
    cleaned = re.sub(r"(?is)<think>.*?</think>", "", text)
    # Also handle unclosed <think> if the model got cut off or omitted closing tag
    if "<think>" in cleaned.lower():
        cleaned = re.sub(r"(?is)<think>.*", "", cleaned)
    return cleaned.strip()


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """
    Extract and parse a JSON dictionary from arbitrary LLM output.
    
    Handles:
    - Pure JSON strings
    - Markdown fenced blocks (```json ... ``` or ``` ... ```)
    - Reasoning model outputs (<think> tags from DeepSeek R1, etc.)
    - Conversational text preceding or trailing the JSON
    - Trailing commas before closing braces/brackets
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Cannot extract JSON from empty text")

    text = clean_llm_text(raw_text)

    # 1. Try direct parsing first
    try:
        val = json.loads(text)
        if isinstance(val, dict):
            return val
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code fences ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
    matches = fence_pattern.findall(text)
    for block in matches:
        candidate = block.strip()
        try:
            val = json.loads(candidate)
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            # Try cleaning trailing commas
            cleaned_candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                val = json.loads(cleaned_candidate)
                if isinstance(val, dict):
                    return val
            except json.JSONDecodeError:
                pass

    # 3. Search for outermost { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1].strip()
        try:
            val = json.loads(candidate)
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            cleaned_candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                val = json.loads(cleaned_candidate)
                if isinstance(val, dict):
                    return val
            except json.JSONDecodeError:
                pass

    # 4. Fallback: try raw json.loads on cleaned text
    try:
        val = json.loads(text)
        if isinstance(val, dict):
            return val
        raise ValueError(f"Extracted JSON is {type(val).__name__}, expected dict")
    except Exception as exc:
        raise ValueError(f"Could not parse valid JSON object from LLM response: {exc}") from exc
