"""Domain models for Phase 13: Scheduler and Background Work."""

import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    """Trigger modality for a schedule."""
    CRON = "CRON"
    INTERVAL = "INTERVAL"
    ONE_SHOT = "ONE_SHOT"


class ScheduleStatus(str, Enum):
    """Lifecycle status of a schedule."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    PAUSED_INVALIDATED = "PAUSED_INVALIDATED"
    COMPLETED = "COMPLETED"


class MissedRunPolicy(str, Enum):
    """Policy for reconciling missed occurrences during downtime."""
    SKIP_NOTIFY = "SKIP_NOTIFY"
    RUN_ONCE_CATCHUP = "RUN_ONCE_CATCHUP"


class ConcurrencyPolicy(str, Enum):
    """Policy when task execution capacity is saturated."""
    SKIP_BUSY = "SKIP_BUSY"
    RETRY_GRACE = "RETRY_GRACE"


class RunStatus(str, Enum):
    """Execution status of an individual schedule run."""
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED_BUSY = "BLOCKED_BUSY"
    EXPIRED_APPROVAL = "EXPIRED_APPROVAL"
    INTERRUPTED = "INTERRUPTED"


def compute_template_hash(prompt_template: str, model_profile_id: Optional[str] = None) -> str:
    """Compute deterministic SHA-256 hash for drift detection."""
    content = f"{prompt_template.strip()}|{(model_profile_id or '').strip()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class ScheduleCreate(BaseModel):
    """Request payload to create a new schedule."""
    name: str = Field(..., min_length=1, max_length=120)
    prompt_template: str = Field(..., min_length=1)
    model_profile_id: Optional[str] = None
    trigger_type: TriggerType
    trigger_expression: str = Field(..., min_length=1)
    timezone: str = "UTC"
    missed_run_policy: MissedRunPolicy = MissedRunPolicy.SKIP_NOTIFY
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.SKIP_BUSY
    max_instances: int = Field(default=1, ge=1, le=1)  # Single-tenant capacity
    retry_grace_seconds: int = Field(default=300, ge=0, le=86400)


class ScheduleUpdate(BaseModel):
    """Request payload to modify an existing schedule."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    prompt_template: Optional[str] = Field(None, min_length=1)
    model_profile_id: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    trigger_expression: Optional[str] = Field(None, min_length=1)
    timezone: Optional[str] = None
    missed_run_policy: Optional[MissedRunPolicy] = None
    concurrency_policy: Optional[ConcurrencyPolicy] = None
    retry_grace_seconds: Optional[int] = Field(None, ge=0, le=86400)


class Schedule(BaseModel):
    """Full domain model for a schedule definition."""
    id: str
    name: str
    prompt_template: str
    model_profile_id: Optional[str] = None
    trigger_type: TriggerType
    trigger_expression: str
    timezone: str
    status: ScheduleStatus
    missed_run_policy: MissedRunPolicy
    concurrency_policy: ConcurrencyPolicy
    max_instances: int = 1
    retry_grace_seconds: int = 300
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    template_hash: str
    created_at: datetime
    updated_at: datetime


class ScheduleRun(BaseModel):
    """Record of an individual scheduled execution."""
    run_id: str
    schedule_id: str
    task_id: Optional[str] = None
    run_key: str
    status: RunStatus
    scheduled_for: datetime
    dispatched_at: datetime
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
