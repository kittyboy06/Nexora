"""Unit tests for robust JSON extraction across various LLM outputs."""

import pytest
from app.core.json_utils import clean_llm_text, extract_json_object


def test_clean_llm_text_removes_think_tags():
    raw = "<think>Let me reason about this plan.\nFirst step is X.</think>Actual response."
    assert clean_llm_text(raw) == "Actual response."


def test_clean_llm_text_case_insensitive():
    raw = "<THINK>Thinking...</THINK>Response here."
    assert clean_llm_text(raw) == "Response here."


def test_extract_json_object_direct():
    raw = '{"plan_id": "p1", "steps": []}'
    result = extract_json_object(raw)
    assert result == {"plan_id": "p1", "steps": []}


def test_extract_json_object_markdown_fence():
    raw = """Here is the plan:
```json
{
  "task_kind": "code",
  "confidence": 0.95
}
```
Let me know if this works!"""
    result = extract_json_object(raw)
    assert result == {"task_kind": "code", "confidence": 0.95}


def test_extract_json_object_generic_fence():
    raw = """```
{
  "key": "value"
}
```"""
    result = extract_json_object(raw)
    assert result == {"key": "value"}


def test_extract_json_object_deepseek_r1_style():
    raw = """<think>
The user wants to analyze a dataset.
This is a reasoning task.
Confidence should be high, around 0.9.
</think>
```json
{
  "task_kind": "reasoning",
  "confidence": 0.9
}
```"""
    result = extract_json_object(raw)
    assert result == {"task_kind": "reasoning", "confidence": 0.9}


def test_extract_json_object_conversational_no_fence():
    raw = "Sure thing! Here is the JSON: {\"action\": \"retry\", \"parameter_adjustments\": {}} - hope that helps!"
    result = extract_json_object(raw)
    assert result == {"action": "retry", "parameter_adjustments": {}}


def test_extract_json_object_trailing_commas():
    raw = """{
  "task_kind": "code",
  "confidence": 0.8,
}"""
    result = extract_json_object(raw)
    assert result == {"task_kind": "code", "confidence": 0.8}


def test_extract_json_object_empty_raises():
    with pytest.raises(ValueError, match="Cannot extract JSON from empty text"):
        extract_json_object("")


def test_extract_json_object_invalid_raises():
    with pytest.raises(ValueError, match="Could not parse valid JSON object"):
        extract_json_object("There is no json here at all.")
