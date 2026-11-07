from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.model_profile import RouteSelection
from backend.app.agent.fleet.models import Artifact, FleetPlan


class TaskStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    PARSING = "PARSING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CONTROLLED = "CONTROLLED"
    SENSITIVE = "SENSITIVE"


class RetryClassification(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    UNCERTAIN = "UNCERTAIN"


class ToolCall(BaseModel):
    tool_name: str = Field(..., description="Name of the registered tool to execute")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")


class PlanStep(BaseModel):
    step_id: int = Field(..., ge=1, le=10, description="Sequential step identifier (1-10)")
    description: str = Field(..., description="Human-readable description of what this step does")
    tool_call: ToolCall = Field(..., description="Tool invocation details")
    dependencies: list[int] = Field(default_factory=list, description="Step IDs that must complete before this step")
    risk_level: RiskLevel = Field(default=RiskLevel.SAFE, description="Security/permission classification")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Current execution status of this step")
    retries_attempted: int = Field(default=0, ge=0, le=2, description="Number of retries attempted for this step")


class TaskPlan(BaseModel):
    plan_id: str = Field(..., description="Unique plan identifier")
    goal: str = Field(..., description="High-level goal of this plan")
    steps: list[PlanStep] = Field(..., min_length=1, max_length=10, description="Ordered plan steps")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActionApproval(BaseModel):
    approval_id: str = Field(..., description="Unique approval request ID")
    task_id: str = Field(..., description="Associated task ID")
    step_id: int = Field(..., description="Step requiring authorization")
    tool_name: str = Field(..., description="Tool name requiring authorization")
    argument_hash: str = Field(..., description="SHA-256 hash of canonical arguments")
    expires_at: datetime = Field(..., description="Expiration timestamp (default 10 minutes)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StepResult(BaseModel):
    step_id: int = Field(..., description="Step ID that was executed")
    tool_name: str = Field(..., description="Name of the tool executed")
    status: StepStatus = Field(..., description="Final status of this step execution")
    output: Any | None = Field(default=None, description="Output payload produced by the tool")
    error: str | None = Field(default=None, description="Error message if execution failed")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    retry_classification: RetryClassification | None = Field(default=None, description="Retry classification if failed")


class AgentTask(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    prompt: str = Field(..., description="Original user prompt or instruction")
    model_profile_id: str | None = Field(default=None, description="Optional specialist profile override")
    status: TaskStatus = Field(default=TaskStatus.SUBMITTED, description="Current task lifecycle status")
    routing: RouteSelection | None = Field(default=None, description="Hybrid routing decision, profile, model, and escalation metadata")
    plan: TaskPlan | None = Field(default=None, description="Validated task plan")
    fleet_plan: FleetPlan | None = Field(default=None, description="Optional dynamic agent fleet DAG plan")
    artifacts: list[Artifact] = Field(default_factory=list, description="Immutable evidence records produced by fleet nodes")
    execution_trace: list[StepResult] = Field(default_factory=list, description="Ordered step execution results")
    pending_approval: ActionApproval | None = Field(default=None, description="Pending approval token if paused")
    iterations_used: int = Field(default=0, le=15, description="Count of tool executions attempted")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    error_message: str | None = Field(default=None, description="Detailed explanation if task failed")


# API Schemas
class TaskCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4096, description="User goal or task instruction")
    model_profile_id: str | None = Field(default=None, min_length=1, max_length=100, description="Optional manual specialist profile override")
    execution_mode: str | None = Field(default="auto", description="Execution mode: auto, single, fleet")


class TaskResponse(BaseModel):
    task: AgentTask = Field(..., description="Task details and execution status")


class ApprovalDecisionRequest(BaseModel):
    approval_id: str = Field(..., description="ID of the approval token being decided")
    approved: bool = Field(..., description="True to authorize execution, False to reject")
