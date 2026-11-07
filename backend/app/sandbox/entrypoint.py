"""Hardened entrypoint runner executed inside the sandbox child process."""

import importlib.util
import json
import os
import sys
import time
import traceback
from typing import Any


def load_tool_module(tool_path: str):
    """Dynamically load the generated tool module from disk."""
    spec = importlib.util.spec_from_file_location("generated_tool", tool_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {tool_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_tool"] = module
    spec.loader.exec_module(module)
    return module


def run_tests(tool_func: Any, test_cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute all positive and negative test cases against the tool function."""
    results = []
    all_passed = True

    for tc in test_cases:
        tc_name = tc.get("name", "unnamed_test")
        inputs = tc.get("inputs", {})
        expected_output = tc.get("expected_output")
        is_negative = tc.get("is_negative", False)

        start_t = time.perf_counter()
        tc_result = {
            "name": tc_name,
            "is_negative": is_negative,
            "passed": False,
            "duration_ms": 0.0,
            "error": None,
        }

        try:
            actual_output = tool_func(**inputs)
            tc_result["duration_ms"] = round((time.perf_counter() - start_t) * 1000, 3)

            if is_negative:
                # If negative test was expected to raise an exception or match error payload
                if expected_output is not None and actual_output == expected_output:
                    tc_result["passed"] = True
                else:
                    tc_result["passed"] = False
                    tc_result["error"] = (
                        f"Expected exception or error output, but function returned: {actual_output!r}"
                    )
                    all_passed = False
            else:
                # Positive test: check equality if expected_output is specified
                if expected_output is not None:
                    if actual_output == expected_output:
                        tc_result["passed"] = True
                    else:
                        tc_result["passed"] = False
                        tc_result["error"] = f"Expected {expected_output!r}, got {actual_output!r}"
                        all_passed = False
                else:
                    tc_result["passed"] = True

        except Exception as e:
            tc_result["duration_ms"] = round((time.perf_counter() - start_t) * 1000, 3)
            if is_negative:
                # Exception raised in a negative test case is considered passing!
                tc_result["passed"] = True
                tc_result["caught_exception"] = type(e).__name__
            else:
                tc_result["passed"] = False
                tc_result["error"] = f"{type(e).__name__}: {str(e)}"
                all_passed = False

        results.append(tc_result)

    return {
        "status": "TESTS_PASSED" if all_passed else "TESTS_FAILED",
        "test_results": results,
    }


def run_execution(tool_func: Any, runtime_arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute the tool function directly with user-supplied arguments."""
    try:
        output = tool_func(**runtime_arguments)
        return {
            "status": "EXECUTION_SUCCESS",
            "output": output,
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
        }


def main():
    """Entrypoint parsing input.json and writing output.json."""
    input_file = "input.json"
    output_file = "output.json"
    tool_file = "tool.py"

    if not os.path.exists(input_file):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "ERROR", "error": "input.json not found in working directory"}, f)
        sys.exit(1)

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "ERROR", "error": f"Failed to parse input.json: {e}"}, f)
        sys.exit(1)

    mode = payload.get("mode", "test")
    tool_name = payload.get("tool_name")

    if not os.path.exists(tool_file):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "ERROR", "error": f"{tool_file} not found"}, f)
        sys.exit(1)

    try:
        module = load_tool_module(tool_file)
    except Exception as e:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "status": "ERROR",
                "error": f"Failed to load {tool_file}: {e}",
                "traceback": traceback.format_exc(),
            }, f)
        sys.exit(1)

    # Locate the target function
    tool_func = getattr(module, tool_name, None)
    if tool_func is None or not callable(tool_func):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "status": "ERROR",
                "error": f"Function '{tool_name}' was not found or is not callable in {tool_file}",
            }, f)
        sys.exit(1)

    if mode == "test":
        test_cases = payload.get("test_cases", [])
        result = run_tests(tool_func, test_cases)
    elif mode == "run":
        runtime_arguments = payload.get("runtime_arguments", {})
        result = run_execution(tool_func, runtime_arguments)
    else:
        result = {"status": "ERROR", "error": f"Unknown mode: {mode}"}

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
    except Exception as e:
        # Fallback if result contains non-serializable objects
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "ERROR", "error": f"Failed to serialize output: {e}"}, f)
        sys.exit(1)

    if result.get("status") in ("TESTS_PASSED", "EXECUTION_SUCCESS"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
