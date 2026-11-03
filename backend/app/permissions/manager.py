import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.app.core.config import Settings
from backend.app.core.exceptions import ApprovalInvalidatedException
from backend.app.models.agent import ActionApproval, AgentTask, PlanStep, RiskLevel

logger = logging.getLogger("nexora.permissions")


class PermissionManager:
    """Evaluates tool risk tiers and manages action-scoped human-in-the-loop approvals."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.expiration_seconds = settings.APPROVAL_EXPIRATION_SECONDS

    @staticmethod
    def compute_argument_hash(arguments: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash of canonical arguments."""
        canonical_json = json.dumps(arguments, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def evaluate_permission(self, step: PlanStep, task: AgentTask) -> tuple[bool, ActionApproval | None]:
        """
        Evaluate whether the step can execute immediately or requires human approval.
        Returns: (is_authorized, pending_approval)
        """
        if step.risk_level == RiskLevel.SAFE:
            return True, None

        # SENSITIVE and CONTROLLED require explicit approval token
        arg_hash = self.compute_argument_hash(step.tool_call.arguments)
        now = datetime.now(timezone.utc)
        approval = ActionApproval(
            approval_id=f"appr_{uuid4().hex[:8]}",
            task_id=task.task_id,
            step_id=step.step_id,
            tool_name=step.tool_call.tool_name,
            argument_hash=arg_hash,
            expires_at=now + timedelta(seconds=self.expiration_seconds),
            created_at=now,
        )
        logger.info(
            "Created %s approval %s for task %s, step %d (%s)",
            step.risk_level.value,
            approval.approval_id,
            task.task_id,
            step.step_id,
            step.tool_call.tool_name,
        )
        return False, approval

    def verify_decision(
        self,
        task: AgentTask,
        step: PlanStep,
        approval_id: str,
        approved: bool,
    ) -> None:
        """
        Verify that approval decision is valid, unexpired, and arguments haven't changed.
        Raises ApprovalInvalidatedException if invalid.
        """
        pending = task.pending_approval
        if not pending:
            raise ApprovalInvalidatedException("No pending approval exists for this task.")

        if pending.approval_id != approval_id:
            raise ApprovalInvalidatedException(
                f"Approval ID mismatch: expected '{pending.approval_id}', got '{approval_id}'."
            )

        # 1. Check expiration (10 minutes)
        now = datetime.now(timezone.utc)
        if now > pending.expires_at:
            logger.warning("Approval %s has expired.", approval_id)
            raise ApprovalInvalidatedException("Approval token has expired. Execution denied.")

        # 2. Check argument integrity
        current_hash = self.compute_argument_hash(step.tool_call.arguments)
        if current_hash != pending.argument_hash:
            logger.error("Step arguments modified after approval was issued for %s!", approval_id)
            raise ApprovalInvalidatedException(
                "Tool call arguments were modified after approval was requested. Approval invalidated."
            )

        # 3. Check decision
        if not approved:
            logger.info("User explicitly rejected approval %s", approval_id)
            raise ApprovalInvalidatedException("Tool execution was rejected by user.")

        logger.info("Approval %s successfully verified for task %s", approval_id, task.task_id)
