"""Unit tests for Windows Job Object Sandbox Runner."""

import os
import pytest
from pathlib import Path

from backend.app.sandbox.models import SandboxRunStatus, TestCase
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner


@pytest.fixture
def sandbox_dir(tmp_path: Path) -> Path:
    sb_dir = tmp_path / "sandbox_test"
    sb_dir.mkdir(parents=True, exist_ok=True)
    return sb_dir


@pytest.fixture
def runner(sandbox_dir: Path) -> Win32JobObjectRunner:
    return Win32JobObjectRunner(base_sandbox_dir=sandbox_dir)


@pytest.mark.asyncio
async def test_runner_executes_passing_tests(runner: Win32JobObjectRunner):
    code = """
def compute_stats(numbers: list) -> dict:
    if not numbers:
        raise ValueError("Empty list")
    return {"count": len(numbers), "total": sum(numbers)}
"""
    test_cases = [
        TestCase(name="pos1", inputs={"numbers": [1, 2, 3]}, expected_output={"count": 3, "total": 6}, is_negative=False),
        TestCase(name="neg1", inputs={"numbers": []}, is_negative=True),
    ]

    result = await runner.run(
        tool_name="compute_stats",
        code=code,
        mode="test",
        test_cases=test_cases,
        timeout_seconds=5.0,
    )

    assert result.status == SandboxRunStatus.TESTS_PASSED
    assert result.exit_code == 0
    assert len(result.test_results) == 2
    assert result.test_results[0]["passed"] is True
    assert result.test_results[1]["passed"] is True
    assert result.peak_memory_bytes > 0
    assert result.execution_time_ms > 0


@pytest.mark.asyncio
async def test_runner_detects_failing_tests(runner: Win32JobObjectRunner):
    code = """
def bad_math(a: int, b: int) -> int:
    return a - b
"""
    test_cases = [
        TestCase(name="wrong_expectation", inputs={"a": 5, "b": 3}, expected_output=8, is_negative=False),
    ]

    result = await runner.run(
        tool_name="bad_math",
        code=code,
        mode="test",
        test_cases=test_cases,
        timeout_seconds=5.0,
    )

    assert result.status == SandboxRunStatus.TESTS_FAILED
    assert result.exit_code != 0
    assert result.test_results[0]["passed"] is False


@pytest.mark.asyncio
async def test_runner_execution_mode(runner: Win32JobObjectRunner):
    code = """
def parse_tags(raw: str) -> list:
    return [t.strip() for t in raw.split(",") if t.strip()]
"""
    result = await runner.run(
        tool_name="parse_tags",
        code=code,
        mode="run",
        runtime_arguments={"raw": "  alpha, beta , gamma,  "},
        timeout_seconds=5.0,
    )

    assert result.status == SandboxRunStatus.EXECUTION_SUCCESS
    assert result.output == ["alpha", "beta", "gamma"]


@pytest.mark.asyncio
async def test_runner_timeout_kill(runner: Win32JobObjectRunner):
    code = """
import time

def infinite_spinner():
    while True:
        time.sleep(0.1)
"""
    result = await runner.run(
        tool_name="infinite_spinner",
        code=code,
        mode="run",
        runtime_arguments={},
        timeout_seconds=1.0,
    )

    assert result.status == SandboxRunStatus.TIMEOUT
    assert result.exit_code == -99


@pytest.mark.asyncio
async def test_runner_environment_scrubbed(runner: Win32JobObjectRunner):
    os.environ["SUPER_SECRET_NEXORA_TOKEN"] = "CLASSIFIED_XYZ_123"

    code = """
import os

def check_secrets() -> dict:
    return {
        "has_secret": "SUPER_SECRET_NEXORA_TOKEN" in os.environ
    }
"""
    try:
        result = await runner.run(
            tool_name="check_secrets",
            code=code,
            mode="run",
            runtime_arguments={},
            timeout_seconds=5.0,
        )

        assert result.status == SandboxRunStatus.EXECUTION_SUCCESS
        assert result.output == {"has_secret": False}
    finally:
        del os.environ["SUPER_SECRET_NEXORA_TOKEN"]


@pytest.mark.asyncio
async def test_runner_cleans_up_workspace(runner: Win32JobObjectRunner, sandbox_dir: Path):
    code = "def echo_val(x: str) -> str: return x"
    result = await runner.run(
        tool_name="echo_val",
        code=code,
        mode="run",
        runtime_arguments={"x": "hello"},
        timeout_seconds=5.0,
    )

    assert result.status == SandboxRunStatus.EXECUTION_SUCCESS
    run_workspace = sandbox_dir / result.run_id
    assert not run_workspace.exists()
