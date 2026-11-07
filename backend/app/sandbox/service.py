"""Orchestration Service coordinating proposal validation, sandbox execution, and evidence storage."""

import time
import uuid
from typing import Any, Optional

from backend.app.sandbox.evidence import SandboxEvidenceStore
from backend.app.sandbox.models import (
    GeneratedToolProposal,
    SandboxRunResult,
    SandboxRunStatus,
    ToolValidationReport,
)
from backend.app.sandbox.runners.base import SandboxRunner
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner
from backend.app.sandbox.validator import AstSecurityValidator


class SandboxOrchestrationService:
    """Core orchestration service for generated tools validation, trial execution, and auditing."""

    def __init__(
        self,
        validator: Optional[AstSecurityValidator] = None,
        runner: Optional[SandboxRunner] = None,
        evidence_store: Optional[SandboxEvidenceStore] = None,
    ) -> None:
        self.validator = validator or AstSecurityValidator()
        self.runner = runner or Win32JobObjectRunner()
        self.evidence_store = evidence_store or SandboxEvidenceStore()

    def validate_proposal(self, proposal: GeneratedToolProposal) -> ToolValidationReport:
        """Run AST static security analysis on proposed code."""
        return self.validator.validate(proposal)

    async def run_trial(
        self,
        proposal: GeneratedToolProposal,
        mode: str = "test",
        runtime_arguments: Optional[dict[str, Any]] = None,
        task_id: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ) -> SandboxRunResult:
        """Execute a proposal in the sandbox after passing AST static analysis."""
        # 1. Static Security Gate
        report = self.validator.validate(proposal)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if not report.is_valid:
            run_id = f"run_rejected_{uuid.uuid4().hex[:10]}"
            error_msg = "AST Security Validation Failed:\n" + "\n".join(f"- {err}" for err in report.errors)
            result = SandboxRunResult(
                run_id=run_id,
                task_id=task_id or proposal.task_id,
                tool_name=proposal.name,
                status=SandboxRunStatus.ERROR,
                exit_code=1,
                execution_time_ms=0.0,
                peak_memory_bytes=0,
                test_results=[],
                output=None,
                stdout="",
                stderr=error_msg,
                source_sha256=report.source_sha256,
                timestamp=now_iso,
            )
            self.evidence_store.save_run_result(result)
            return result

        # 2. Execute within isolated sandbox
        result = await self.runner.run(
            tool_name=proposal.name,
            code=proposal.code,
            mode=mode,
            test_cases=proposal.test_cases,
            runtime_arguments=runtime_arguments,
            task_id=task_id or proposal.task_id,
            timeout_seconds=timeout_seconds,
        )

        # 3. Save evidence for audit and promotion verification
        self.evidence_store.save_run_result(result)
        return result

    def get_evidence(self, run_id: str) -> Optional[SandboxRunResult]:
        """Fetch audit evidence for a specific run."""
        return self.evidence_store.get_run_result(run_id)

    def list_evidence(self, limit: int = 50) -> list[SandboxRunResult]:
        """List recent sandbox execution evidence records."""
        return self.evidence_store.list_run_results(limit=limit)
