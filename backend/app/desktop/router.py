"""FastAPI Router exposing Desktop Vision and Interaction capabilities."""

import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.desktop.guard import ShieldedWindowException
from backend.app.desktop.models import (
    DesktopActionRequest,
    DesktopActionResult,
    ScreenshotEvidence,
    TargetWindowBinding,
    UIElementNode,
    WindowSummary,
)

logger = logging.getLogger("nexora.desktop.router")
router = APIRouter(prefix="/api/desktop", tags=["desktop"])


class BindWindowRequest(BaseModel):
    hwnd: int = Field(..., description="Target window HWND to bind")


class EmergencyStopRequest(BaseModel):
    reason: Optional[str] = Field(default="Operator emergency stop", description="Reason for stopping automation")


@router.get("/windows", response_model=list[WindowSummary])
async def list_windows(
    request: Request,
    query: Optional[str] = None,
    include_shielded: bool = False,
) -> list[WindowSummary]:
    """List open desktop application windows."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")
    return service.list_windows(query=query, include_shielded=include_shielded)


@router.post("/bind", response_model=TargetWindowBinding)
async def bind_window(
    bind_req: BindWindowRequest,
    request: Request,
) -> TargetWindowBinding:
    """Bind a specific window as the active automation target."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")

    try:
        return service.bind_window(bind_req.hwnd)
    except ShieldedWindowException as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/binding", response_model=Optional[TargetWindowBinding])
async def get_active_binding(request: Request) -> Optional[TargetWindowBinding]:
    """Retrieve the current active target window binding, if any."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")
    return service.get_active_binding()


@router.post("/release")
async def release_binding(request: Request) -> dict[str, bool]:
    """Release the active target window binding."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")
    service.release_binding()
    return {"released": True}


@router.get("/tree", response_model=UIElementNode)
async def inspect_tree(
    request: Request,
    hwnd: Optional[int] = None,
    max_depth: int = Query(4, ge=1, le=8),
) -> UIElementNode:
    """Inspect the accessibility UI Automation tree of a target window."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")

    try:
        return service.inspect_tree(hwnd=hwnd, max_depth=max_depth)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/capture", response_model=ScreenshotEvidence)
async def capture_window(
    request: Request,
    hwnd: Optional[int] = None,
    task_id: str = "default_task",
) -> ScreenshotEvidence:
    """Capture a window-bounded, redacted screenshot of the target window."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")

    try:
        return service.capture_window(hwnd=hwnd, task_id=task_id)
    except ShieldedWindowException as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/actions", response_model=DesktopActionResult)
async def execute_action(
    action_req: DesktopActionRequest,
    request: Request,
    task_id: str = "default_task",
) -> DesktopActionResult:
    """Execute a typed, bounded desktop action against the active target window."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")

    return service.execute_action(action_req, task_id=task_id)


@router.post("/emergency-stop")
async def emergency_stop(
    request: Request,
    stop_req: Optional[EmergencyStopRequest] = None,
) -> dict[str, str]:
    """Instantly engage the emergency stop, halting all desktop automation."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")

    reason = stop_req.reason if stop_req else "Operator emergency stop"
    service.trigger_emergency_stop(reason=reason)
    return {"status": "STOPPED", "reason": reason}


@router.post("/emergency-stop/reset")
async def reset_emergency_stop(request: Request) -> dict[str, str]:
    """Reset the emergency stop state once safe."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")

    service.reset_emergency_stop(authorized=True)
    return {"status": "ACTIVE"}


@router.get("/evidence", response_model=list[ScreenshotEvidence])
async def list_evidence(
    request: Request,
    task_id: Optional[str] = None,
) -> list[ScreenshotEvidence]:
    """List captured screenshot evidence records."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")
    return service.list_evidence(task_id=task_id)


@router.get("/evidence/{image_id}/file")
async def get_evidence_file(
    image_id: str,
    request: Request,
) -> FileResponse:
    """Serve the raw PNG image file for a given screenshot evidence ID."""
    service = getattr(request.app.state, "desktop_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Desktop service is not initialized")

    ev = service.get_evidence(image_id)
    if not ev or not Path(ev.file_path).exists():
        raise HTTPException(status_code=404, detail=f"Screenshot file for {image_id} not found")

    return FileResponse(ev.file_path, media_type="image/png")
