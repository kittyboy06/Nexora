"""AST Static Security Analyzer for Phase 10 Generated Tools."""

import ast
import hashlib
from typing import Optional, Set

from backend.app.sandbox.models import GeneratedToolProposal, ToolValidationReport

# Strict Allowlist of Standard Modules permitted for generated tools
ALLOWED_ROOT_MODULES: Set[str] = {
    "math",
    "re",
    "json",
    "csv",
    "datetime",
    "collections",
    "itertools",
    "hashlib",
    "string",
    "typing",
    "pydantic",
    "random",
    "uuid",
    "base64",
    "dataclasses",
    "decimal",
    "fractions",
    "bisect",
    "heapq",
}

# Submodules specifically allowed if the parent isn't completely open
ALLOWED_QUALIFIED_MODULES: Set[str] = {
    "urllib.parse",
}

# Explicitly forbidden built-in functions / identifiers that could escape the sandbox
FORBIDDEN_BUILTIN_NAMES: Set[str] = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "input",
    "breakpoint",
    "open",
    "memoryview",
}

# Forbidden dunder attributes commonly used in Python sandbox escape chains
FORBIDDEN_ATTRIBUTES: Set[str] = {
    "__subclasses__",
    "__bases__",
    "__base__",
    "__mro__",
    "__globals__",
    "__builtins__",
    "__code__",
    "__class__",
    "__dict__",
    "__closure__",
    "__func__",
}

MAX_CODE_SIZE_BYTES: int = 50 * 1024  # 50 KB
MAX_CODE_LINES: int = 1000
MAX_AST_DEPTH: int = 25


class AstSecurityVisitor(ast.NodeVisitor):
    """AST Visitor that traverses the syntax tree and identifies security violations."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.defined_functions: set[str] = set()
        self.current_depth: int = 0
        self.max_depth_seen: int = 0

    def generic_visit(self, node: ast.AST) -> None:
        self.current_depth += 1
        if self.current_depth > self.max_depth_seen:
            self.max_depth_seen = self.current_depth

        if self.current_depth > MAX_AST_DEPTH:
            self.errors.append(f"AST nesting depth exceeded safety limit ({MAX_AST_DEPTH})")
            # Do not recurse further to avoid recursion limits
            self.current_depth -= 1
            return

        super().generic_visit(node)
        self.current_depth -= 1

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod_name = alias.name
            root = mod_name.split(".")[0]
            if mod_name in ALLOWED_QUALIFIED_MODULES or root in ALLOWED_ROOT_MODULES:
                if root == "urllib" and mod_name != "urllib.parse":
                    self.errors.append(
                        f"Import of unapproved submodule '{mod_name}' is forbidden (only 'urllib.parse' is allowed)"
                    )
            else:
                self.errors.append(f"Import of module '{mod_name}' is not in the approved allowlist")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod_name = node.module or ""
        root = mod_name.split(".")[0]
        if mod_name in ALLOWED_QUALIFIED_MODULES or root in ALLOWED_ROOT_MODULES:
            if root == "urllib" and mod_name != "urllib.parse":
                self.errors.append(
                    f"Import from unapproved submodule '{mod_name}' is forbidden (only 'urllib.parse' is allowed)"
                )
        else:
            self.errors.append(f"Import from module '{mod_name}' is not in the approved allowlist")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_BUILTIN_NAMES:
            self.errors.append(f"Usage of forbidden identifier or built-in function '{node.id}' is blocked")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_ATTRIBUTES:
            self.errors.append(f"Access to introspection dunder attribute '{node.attr}' is blocked")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.defined_functions.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.defined_functions.add(node.name)
        self.generic_visit(node)


class AstSecurityValidator:
    """Deterministic AST validator enforcing static code security standards."""

    def __init__(self) -> None:
        pass

    def validate(self, proposal: GeneratedToolProposal) -> ToolValidationReport:
        """Analyze proposal code and manifest for security, complexity, and contract validity."""
        errors: list[str] = []
        warnings: list[str] = []

        code = proposal.code
        raw_bytes = code.encode("utf-8")
        source_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # 1. Size and line limits
        if len(raw_bytes) > MAX_CODE_SIZE_BYTES:
            errors.append(
                f"Source code exceeds maximum size limit ({len(raw_bytes)} bytes > {MAX_CODE_SIZE_BYTES} bytes)"
            )

        lines = code.splitlines()
        if len(lines) > MAX_CODE_LINES:
            errors.append(f"Source code exceeds maximum line limit ({len(lines)} lines > {MAX_CODE_LINES} lines)")

        # 2. Syntax parsing
        try:
            tree = ast.parse(code, filename=f"{proposal.name}.py")
        except SyntaxError as e:
            errors.append(f"Python syntax error at line {e.lineno}, col {e.offset}: {e.msg}")
            return ToolValidationReport(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                source_sha256=source_sha256,
            )

        # 3. AST security visitor traversal
        visitor = AstSecurityVisitor()
        visitor.visit(tree)
        errors.extend(visitor.errors)
        warnings.extend(visitor.warnings)

        # 4. Entrypoint function validation
        if proposal.name not in visitor.defined_functions:
            errors.append(
                f"Generated code does not define the target entrypoint function '{proposal.name}'"
            )

        # 5. Test cases contract verification
        if not proposal.test_cases:
            errors.append("Proposal must include at least one positive and one negative test case")
        else:
            has_positive = any(not tc.is_negative for tc in proposal.test_cases)
            has_negative = any(tc.is_negative for tc in proposal.test_cases)

            if not has_positive:
                errors.append("Proposal is missing at least one positive test case")
            if not has_negative:
                errors.append("Proposal is missing at least one negative test case (error/edge verification)")

        return ToolValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            source_sha256=source_sha256,
        )
