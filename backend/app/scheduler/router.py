"""REST API router exposing management endpoints for NEXORA Scheduler."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.core.exceptions import TaskRunnerBusyException
from backend.app.scheduler.models import (
    RunStatus,
    Schedule,
    ScheduleCreate,
    ScheduleRun,
    ScheduleStatus,
    ScheduleUpdate,
)
from backend.app.scheduler.service import SchedulerService

logger = logging.getLogger("nexora.scheduler.router")

router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])


def get_scheduler_service(request: Request) -> SchedulerService:
    """FastAPI dependency resolving the active SchedulerService."""
    service = getattr(request.app.state, "scheduler_service", None)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service is not initialized.",
        )
    return service


@router.get("/schedules", response_model=List[Schedule])
async def list_schedules(
    status: Optional[ScheduleStatus] = Query(None, description="Optional filter by schedule status"),
    service: SchedulerService = Depends(get_scheduler_service),
) -> List[Schedule]:
    """List all configured schedules."""
    return service.list_schedules(status=status)


@router.post("/schedules", response_model=Schedule, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    service: SchedulerService = Depends(get_scheduler_service),
) -> Schedule:
    """Create a new recurring or one-shot schedule."""
    try:
        return service.create_schedule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/schedules/{schedule_id}", response_model=Schedule)
async def get_schedule(
    schedule_id: str,
    service: SchedulerService = Depends(get_scheduler_service),
) -> Schedule:
    """Get schedule details by ID."""
    schedule = service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule '{schedule_id}' not found.",
        )
    return schedule


@router.patch("/schedules/{schedule_id}", response_model=Schedule)
async def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    service: SchedulerService = Depends(get_scheduler_service),
) -> Schedule:
    """Update schedule prompt template, model profile, or recurrence configuration."""
    try:
        return service.update_schedule(schedule_id, payload)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/schedules/{schedule_id}/pause", response_model=Schedule)
async def pause_schedule(
    schedule_id: str,
    service: SchedulerService = Depends(get_scheduler_service),
) -> Schedule:
    """Pause an active schedule."""
    try:
        return service.pause_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/schedules/{schedule_id}/resume", response_model=Schedule)
async def resume_schedule(
    schedule_id: str,
    service: SchedulerService = Depends(get_scheduler_service),
) -> Schedule:
    """Resume a paused or invalidated schedule, recalculating its next run."""
    try:
        return service.resume_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    service: SchedulerService = Depends(get_scheduler_service),
) -> dict:
    """Delete a schedule and cascade delete all its run records."""
    deleted = service.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule '{schedule_id}' not found.",
        )
    return {"deleted": True, "schedule_id": schedule_id}


@router.post("/schedules/{schedule_id}/trigger", response_model=ScheduleRun)
async def trigger_schedule_manually(
    schedule_id: str,
    service: SchedulerService = Depends(get_scheduler_service),
) -> ScheduleRun:
    """Trigger an immediate out-of-band execution of a schedule."""
    try:
        return await service.trigger_manual_run(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TaskRunnerBusyException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/runs", response_model=List[ScheduleRun])
async def list_runs(
    schedule_id: Optional[str] = Query(None, description="Filter by schedule ID"),
    status: Optional[RunStatus] = Query(None, description="Filter by run status"),
    limit: int = Query(50, ge=1, le=500, description="Max runs to return"),
    service: SchedulerService = Depends(get_scheduler_service),
) -> List[ScheduleRun]:
    """Query recent execution history."""
    return service.list_runs(schedule_id=schedule_id, status=status, limit=limit)
