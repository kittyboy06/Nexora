"""Unit tests for AST Static Security Analyzer."""

import pytest
from backend.app.sandbox.models import GeneratedToolProposal, TestCase
from backend.app.sandbox.validator import AstSecurityValidator


@pytest.fixture
def validator() -> AstSecurityValidator:
    return AstSecurityValidator()


def create_proposal(
    name: str = "calculate_summary",
    code: str = "def calculate_summary(data: list) -> dict:\n    return {'count': len(data), 'sum': sum(data)}\n",
    test_cases: list[TestCase] = None,
) -> GeneratedToolProposal:
    if test_cases is None:
        test_cases = [
            TestCase(name="valid_list", inputs={"data": [1, 2, 3]}, expected_output={"count": 3, "sum": 6}),
            TestCase(name="empty_list", inputs={"data": []}, expected_output={"count": 0, "sum": 0}, is_negative=True),
        ]
    return GeneratedToolProposal(
        name=name,
        description="Calculates summary statistics",
        code=code,
        input_schema={"type": "object", "properties": {"data": {"type": "array"}}},
        output_schema={"type": "object"},
        test_cases=test_cases,
    )


def test_validator_valid_proposal(validator: AstSecurityValidator):
    valid_code = """
import math
import json
import re
from datetime import datetime
from urllib.parse import quote

def calculate_summary(data: list) -> dict:
    cleaned = [x for x in data if isinstance(x, (int, float))]
    return {
        "count": len(cleaned),
        "mean": math.fsum(cleaned) / len(cleaned) if cleaned else 0.0,
        "encoded": quote("summary_ready")
    }
"""
    proposal = create_proposal(code=valid_code)
    report = validator.validate(proposal)
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert len(report.source_sha256) == 64


def test_validator_rejects_unapproved_imports(validator: AstSecurityValidator):
    bad_codes = [
        "import os\ndef calculate_summary(): pass",
        "import sys\ndef calculate_summary(): pass",
        "import subprocess\ndef calculate_summary(): pass",
        "from socket import socket\ndef calculate_summary(): pass",
        "from ctypes import CDLL\ndef calculate_summary(): pass",
        "import urllib.request\ndef calculate_summary(): pass",
        "from urllib.request import urlopen\ndef calculate_summary(): pass",
    ]
    for code in bad_codes:
        proposal = create_proposal(code=code)
        report = validator.validate(proposal)
        assert report.is_valid is False
        assert any("approved allowlist" in err or "unapproved submodule" in err for err in report.errors)


def test_validator_rejects_forbidden_builtins(validator: AstSecurityValidator):
    forbidden_calls = [
        "def calculate_summary(): eval('1 + 1')",
        "def calculate_summary(): exec('import os')",
        "def calculate_summary(): __import__('os')",
        "def calculate_summary(): globals()",
        "def calculate_summary(): locals()",
        "def calculate_summary(): open('test.txt', 'w')",
        "def calculate_summary(): getattr([], '__doc__')",
    ]
    for code in forbidden_calls:
        proposal = create_proposal(code=code)
        report = validator.validate(proposal)
        assert report.is_valid is False
        assert any("forbidden identifier" in err for err in report.errors)


def test_validator_rejects_dunder_escapes(validator: AstSecurityValidator):
    dunder_escapes = [
        "def calculate_summary(): return ().__class__.__bases__[0].__subclasses__()",
        "def calculate_summary(): return ().__class__.__mro__",
        "def calculate_summary(fn): return fn.__code__",
        "def calculate_summary(fn): return fn.__globals__",
    ]
    for code in dunder_escapes:
        proposal = create_proposal(code=code)
        report = validator.validate(proposal)
        assert report.is_valid is False
        assert any("introspection dunder attribute" in err for err in report.errors)


def test_validator_rejects_syntax_errors(validator: AstSecurityValidator):
    bad_syntax = "def calculate_summary(:\n    return {"
    proposal = create_proposal(code=bad_syntax)
    report = validator.validate(proposal)
    assert report.is_valid is False
    assert any("syntax error" in err.lower() for err in report.errors)


def test_validator_rejects_missing_entrypoint(validator: AstSecurityValidator):
    mismatched_code = "def different_function(data):\n    return len(data)\n"
    proposal = create_proposal(name="calculate_summary", code=mismatched_code)
    report = validator.validate(proposal)
    assert report.is_valid is False
    assert any("does not define the target entrypoint" in err for err in report.errors)


def test_validator_requires_positive_and_negative_test_cases(validator: AstSecurityValidator):
    # Missing negative test
    proposal_no_neg = create_proposal(test_cases=[
        TestCase(name="pos1", inputs={"data": [1]}, expected_output=1, is_negative=False),
        TestCase(name="pos2", inputs={"data": [2]}, expected_output=2, is_negative=False),
    ])
    report_no_neg = validator.validate(proposal_no_neg)
    assert report_no_neg.is_valid is False
    assert any("missing at least one negative test case" in err for err in report_no_neg.errors)

    # Missing positive test
    proposal_no_pos = create_proposal(test_cases=[
        TestCase(name="neg1", inputs={"data": []}, expected_output=None, is_negative=True),
    ])
    report_no_pos = validator.validate(proposal_no_pos)
    assert report_no_pos.is_valid is False
    assert any("missing at least one positive test case" in err for err in report_no_pos.errors)

    # Empty test cases
    proposal_empty = create_proposal(test_cases=[])
    report_empty = validator.validate(proposal_empty)
    assert report_empty.is_valid is False


def test_validator_size_and_depth_limits(validator: AstSecurityValidator):
    # Oversized lines
    huge_code = "def calculate_summary():\n" + ("    x = 1\n" * 1050)
    proposal_lines = create_proposal(code=huge_code)
    report_lines = validator.validate(proposal_lines)
    assert report_lines.is_valid is False
    assert any("line limit" in err for err in report_lines.errors)

    # Deep AST nesting (>25)
    deep_expr = "1"
    for _ in range(30):
        deep_expr = f"({deep_expr} + 1)"
    deep_code = f"def calculate_summary():\n    return {deep_expr}\n"
    proposal_deep = create_proposal(code=deep_code)
    report_deep = validator.validate(proposal_deep)
    assert report_deep.is_valid is False
    assert any("nesting depth exceeded" in err for err in report_deep.errors)
