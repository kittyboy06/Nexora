from fastapi import APIRouter, BackgroundTasks, Depends, status

from backend.app.api.dependencies import get_state_manager, get_task_manager
from backend.app.agent.state_manager import StateManager
from backend.app.agent.task_manager import TaskManager
from backend.app.models.agent import (
    AgentTask,
    ApprovalDecisionRequest,
    TaskCreateRequest,
    TaskResponse,
)

router = APIRouter(prefix="/agent/tasks", tags=["Agent"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create and execute agent task")
async def create_task(
    payload: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
    """
    Submit a high-level user goal. Initiates planning and autonomous execution
    in the background. Enforces maximum 1 active task limit.
    """
    task = await manager.create_and_start_task(payload.prompt, background_tasks)
    return TaskResponse(task=task)


@router.get("", response_model=list[AgentTask], summary="List all agent tasks")
async def list_tasks(
    state_manager: StateManager = Depends(get_state_manager),
) -> list[AgentTask]:
    """Return all known tasks and their historical execution states."""
    return await state_manager.list_tasks()


@router.get("/{task_id}", response_model=TaskResponse, summary="Get task details and trace")
async def get_task(
    task_id: str,
    state_manager: StateManager = Depends(get_state_manager),
) -> TaskResponse:
    """Retrieve full task status, generated plan, and execution trace."""
    # Check for approval expiry if waiting
    await state_manager.check_approval_expired(task_id)
    task = await state_manager.get_task(task_id)
    return TaskResponse(task=task)


@router.post("/{task_id}/approve", response_model=TaskResponse, summary="Submit human authorization decision")
async def approve_task_step(
    task_id: str,
    decision: ApprovalDecisionRequest,
    background_tasks: BackgroundTasks,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
    """
    Authorize or reject a sensitive tool action currently in WAITING_APPROVAL status.
    If approved, resumes execution in the background.
    """
    task = await manager.submit_approval(
        task_id=task_id,
        approval_id=decision.approval_id,
        approved=decision.approved,
        background_tasks=background_tasks,
    )
    return TaskResponse(task=task)


@router.post("/{task_id}/cancel", response_model=TaskResponse, summary="Cancel an active task")
async def cancel_task(
    task_id: str,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
    """Cancel a submitted or running task."""
    task = await manager.cancel_task(task_id)
    return TaskResponse(task=task)
