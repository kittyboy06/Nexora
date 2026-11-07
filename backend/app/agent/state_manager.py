import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.core.config import Settings
from backend.app.core.exceptions import (
    InvalidStateTransitionException,
    TaskNotFoundException,
)
from backend.app.models.agent import (
    ActionApproval,
    AgentTask,
    StepResult,
    TaskPlan,
    TaskStatus,
)

from backend.app.models.model_profile import RouteSelection
from backend.app.agent.fleet.models import Artifact, FleetPlan

logger = logging.getLogger("nexora.state_manager")

VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.SUBMITTED: {TaskStatus.PARSING, TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.CANCELLED},
    TaskStatus.PARSING: {TaskStatus.PLANNING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.PLANNING: {TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.EXECUTING: {TaskStatus.WAITING_APPROVAL, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.WAITING_APPROVAL: {TaskStatus.APPROVED, TaskStatus.REJECTED, TaskStatus.EXPIRED, TaskStatus.CANCELLED},
    TaskStatus.APPROVED: {TaskStatus.EXECUTING, TaskStatus.CANCELLED},
    TaskStatus.REJECTED: {TaskStatus.FAILED},
    TaskStatus.EXPIRED: {TaskStatus.FAILED},
}

ACTIVE_STATES: set[TaskStatus] = {
    TaskStatus.SUBMITTED,
    TaskStatus.PARSING,
    TaskStatus.PLANNING,
    TaskStatus.EXECUTING,
    TaskStatus.WAITING_APPROVAL,
    TaskStatus.APPROVED,
}


class StateManager:
    """Single authority for task state transitions and atomic persistence."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.data_dir = settings.get_task_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, AgentTask] = {}
        self._lock = asyncio.Lock()

    def _persist_atomic(self, task: AgentTask) -> None:
        """Write task snapshot atomically using a temp file."""
        task_file = self.data_dir / f"{task.task_id}.json"
        tmp_file = self.data_dir / f"{task.task_id}.json.tmp"
        try:
            tmp_file.write_text(task.model_dump_json(indent=2), encoding="utf-8")
            tmp_file.replace(task_file)
            logger.debug("Persisted task snapshot atomically: %s", task.task_id)
        except Exception as exc:
            logger.error("Failed to persist task snapshot for %s: %s", task.task_id, exc)

    async def create_task(self, prompt: str, model_profile_id: str | None = None) -> AgentTask:
        """Initialize and persist a new AgentTask in SUBMITTED state."""
        async with self._lock:
            task_id = f"task_{uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)
            task = AgentTask(
                task_id=task_id,
                prompt=prompt,
                model_profile_id=model_profile_id,
                status=TaskStatus.SUBMITTED,
                created_at=now,
                updated_at=now,
            )
            self._tasks[task_id] = task
            self._persist_atomic(task)
            logger.info("Task created: %s (status=%s)", task_id, task.status.value)
            return task

    async def get_task(self, task_id: str) -> AgentTask:
        """Retrieve task by ID from memory or disk snapshot."""
        async with self._lock:
            if task_id in self._tasks:
                return self._tasks[task_id]

            # Fallback to disk snapshot
            task_file = self.data_dir / f"{task_id}.json"
            if task_file.exists():
                try:
                    data = json.loads(task_file.read_text(encoding="utf-8"))
                    task = AgentTask(**data)
                    self._tasks[task_id] = task
                    return task
                except Exception as exc:
                    logger.error("Corrupted task snapshot %s: %s", task_id, exc)

            raise TaskNotFoundException(task_id)

    async def list_tasks(self) -> list[AgentTask]:
        """List all tasks known in memory and on disk."""
        async with self._lock:
            # Sync any files from disk into memory
            for f in self.data_dir.glob("task_*.json"):
                tid = f.stem
                if tid not in self._tasks:
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        self._tasks[tid] = AgentTask(**data)
                    except Exception as exc:
                        logger.warning("Could not read snapshot %s: %s", f.name, exc)
            return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    async def transition_state(
        self,
        task_id: str,
        target: TaskStatus,
        error_message: str | None = None,
    ) -> AgentTask:
        """Validate and apply a state transition."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                task = await self._load_task_from_disk(task_id)

            current = task.status
            # Allow INTERRUPTED from any active state
            is_valid = False
            if target == TaskStatus.INTERRUPTED and current in ACTIVE_STATES:
                is_valid = True
            elif current in VALID_TRANSITIONS and target in VALID_TRANSITIONS[current]:
                is_valid = True

            if not is_valid:
                logger.error("Illegal state transition attempted for %s: %s -> %s", task_id, current.value, target.value)
                raise InvalidStateTransitionException(
                    current_state=current.value,
                    target_state=target.value,
                    task_id=task_id,
                )

            task.status = target
            task.updated_at = datetime.now(timezone.utc)
            if error_message:
                task.error_message = error_message
            if target in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.INTERRUPTED}:
                task.completed_at = task.updated_at

            self._persist_atomic(task)
            logger.info("Task %s transitioned: %s -> %s", task_id, current.value, target.value)
            return task

    async def record_routing(self, task_id: str, routing: RouteSelection) -> AgentTask:
        """Store the routing decision in task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                task = await self._load_task_from_disk(task_id)
            task.routing = routing
            task.updated_at = datetime.now(timezone.utc)
            self._persist_atomic(task)
            return task

    async def update_plan(self, task_id: str, plan: TaskPlan) -> AgentTask:
        """Store the validated plan in task."""
        async with self._lock:
            task = self._tasks[task_id]
            task.plan = plan
            task.updated_at = datetime.now(timezone.utc)
            self._persist_atomic(task)
            return task

    async def set_pending_approval(self, task_id: str, approval: ActionApproval) -> AgentTask:
        """Set active approval token on task."""
        async with self._lock:
            task = self._tasks[task_id]
            task.pending_approval = approval
            task.updated_at = datetime.now(timezone.utc)
            self._persist_atomic(task)
            return task

    async def clear_pending_approval(self, task_id: str) -> AgentTask:
        """Clear active approval token upon decision."""
        async with self._lock:
            task = self._tasks[task_id]
            task.pending_approval = None
            task.updated_at = datetime.now(timezone.utc)
            self._persist_atomic(task)
            return task

    async def append_step_result(self, task_id: str, result: StepResult) -> AgentTask:
        """Record execution result into the task trace."""
        async with self._lock:
            task = self._tasks[task_id]
            task.execution_trace.append(result)
            task.updated_at = datetime.now(timezone.utc)
            self._persist_atomic(task)
            return task

    async def increment_iterations(self, task_id: str) -> int:
        """Increment and return the iterations count."""
        async with self._lock:
            task = self._tasks[task_id]
            task.iterations_used += 1
            task.updated_at = datetime.now(timezone.utc)
            self._persist_atomic(task)
            return task.iterations_used

    async def check_approval_expired(self, task_id: str) -> bool:
        """Check if pending approval has expired; transition if so."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.WAITING_APPROVAL or not task.pending_approval:
            return False

        now = datetime.now(timezone.utc)
        if now > task.pending_approval.expires_at:
            logger.warning("Approval %s for task %s has expired.", task.pending_approval.approval_id, task_id)
            await self.transition_state(task_id, TaskStatus.EXPIRED, error_message="Approval window of 10 minutes expired.")
            await self.transition_state(task_id, TaskStatus.FAILED, error_message="Approval expired without decision.")
            await self.clear_pending_approval(task_id)
            return True
        return False

    async def recover_on_startup(self) -> int:
        """Sweep data/tasks and mark any unfinalized tasks from prior runs as INTERRUPTED."""
        count = 0
        async with self._lock:
            for f in self.data_dir.glob("task_*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    task = AgentTask(**data)
                    if task.status in ACTIVE_STATES:
                        logger.warning("Startup recovery: marking interrupted task %s (was %s)", task.task_id, task.status.value)
                        task.status = TaskStatus.INTERRUPTED
                        task.error_message = "Task interrupted by application restart. Uncertain operations not resumed."
                        task.updated_at = datetime.now(timezone.utc)
                        task.completed_at = task.updated_at
                        self._persist_atomic(task)
                        count += 1
                    self._tasks[task.task_id] = task
                except Exception as exc:
                    logger.error("Failed to inspect snapshot %s during startup recovery: %s", f.name, exc)
        if count > 0:
            logger.info("Startup recovery sweep complete: %d tasks marked INTERRUPTED.", count)
        return count

    async def _load_task_from_disk(self, task_id: str) -> AgentTask:
        task_file = self.data_dir / f"{task_id}.json"
        if not task_file.exists():
            raise TaskNotFoundException(task_id)
        data = json.loads(task_file.read_text(encoding="utf-8"))
        task = AgentTask(**data)
        self._tasks[task_id] = task
        return task


    async def update_fleet_plan(self, task_id: str, fleet_plan: FleetPlan) -> AgentTask:
        """Update and persist the fleet plan for a task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                task = self._load_from_disk(task_id)
            if not task:
                raise TaskNotFoundException(task_id)

            updated = task.model_copy(
                update={"fleet_plan": fleet_plan, "updated_at": datetime.now(timezone.utc)}
            )
            self._tasks[task_id] = updated
            self._persist_atomic(updated)
            return updated

    async def record_artifact(self, task_id: str, artifact: Artifact) -> AgentTask:
        """Append an immutable artifact to task state and persist atomically."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                task = self._load_from_disk(task_id)
            if not task:
                raise TaskNotFoundException(task_id)

            artifacts = list(task.artifacts) + [artifact]
            updated = task.model_copy(
                update={"artifacts": artifacts, "updated_at": datetime.now(timezone.utc)}
            )
            self._tasks[task_id] = updated
            self._persist_atomic(updated)
            return updated
