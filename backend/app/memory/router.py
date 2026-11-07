"""FastAPI Router for Phase 11 Memory and Persistence Platform."""

import logging
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request, Response

from backend.app.memory.models import (
    MemoryAuditEntry,
    MemoryBackupInfo,
    MemoryCategory,
    MemoryProposal,
    MemoryRecord,
    MemoryStatus,
    MemoryUpdateRequest,
)
from backend.app.memory.security import MemorySecurityException

logger = logging.getLogger("nexora.memory.router")

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/records", response_model=list[MemoryRecord])
async def list_memories(
    request: Request,
    category: Optional[MemoryCategory] = None,
    status: Optional[MemoryStatus] = None,
    query: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
) -> list[MemoryRecord]:
    """List or search durable memory records."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")
    return service.list_memories(category=category, status=status, query=query, limit=limit)


@router.post("/records", response_model=MemoryRecord)
async def create_memory(
    proposal: MemoryProposal,
    request: Request,
    auto_approve: bool = False,
) -> MemoryRecord:
    """Propose or record a new memory."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    try:
        return service.propose_memory(proposal, auto_approve=auto_approve, actor="operator")
    except MemorySecurityException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/records/{memory_id}", response_model=MemoryRecord)
async def get_memory(
    memory_id: str,
    request: Request,
) -> MemoryRecord:
    """Fetch details of a specific memory record."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    record = service.get_memory(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Memory record '{memory_id}' not found")
    return record


@router.patch("/records/{memory_id}", response_model=MemoryRecord)
async def update_memory(
    memory_id: str,
    updates: MemoryUpdateRequest,
    request: Request,
) -> MemoryRecord:
    """Update an existing memory record."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    try:
        updated = service.update_memory(memory_id, updates, actor="operator")
    except MemorySecurityException as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not updated:
        raise HTTPException(status_code=404, detail=f"Memory record '{memory_id}' not found")
    return updated


@router.post("/records/{memory_id}/approve", response_model=MemoryRecord)
async def approve_memory(
    memory_id: str,
    request: Request,
) -> MemoryRecord:
    """Approve a pending memory record."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    record = service.approve_memory(memory_id, reviewer="operator")
    if not record:
        raise HTTPException(status_code=404, detail=f"Memory record '{memory_id}' not found")
    return record


@router.post("/records/{memory_id}/revoke")
async def revoke_memory(
    memory_id: str,
    request: Request,
    reason: str = "Revoked by operator",
) -> dict[str, Any]:
    """Revoke a memory record, removing it from model recall."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    success = service.revoke_memory(memory_id, actor="operator", reason=reason)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory record '{memory_id}' not found")
    return {"revoked": True, "id": memory_id}


@router.delete("/records/{memory_id}")
async def delete_memory(
    memory_id: str,
    request: Request,
) -> dict[str, Any]:
    """Permanently delete a memory record."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    success = service.delete_memory(memory_id, actor="operator")
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory record '{memory_id}' not found")
    return {"deleted": True, "id": memory_id}


@router.get("/audit", response_model=list[MemoryAuditEntry])
async def list_audit(
    request: Request,
    memory_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
) -> list[MemoryAuditEntry]:
    """Fetch memory audit timeline."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")
    return service.store.list_audit_entries(memory_id=memory_id, limit=limit)


@router.get("/export")
async def export_memories(
    request: Request,
    format: str = Query("json", pattern="^(json|csv)$"),
) -> Response:
    """Export all active memories formatted as JSON or CSV."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    content = service.export_memories(format=format)
    media_type = "text/csv" if format == "csv" else "application/json"
    filename = f"nexora_memories_export.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/backup", response_model=MemoryBackupInfo)
async def create_backup(
    request: Request,
) -> MemoryBackupInfo:
    """Trigger a point-in-time online SQLite backup."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")
    return service.create_backup()


@router.get("/backups", response_model=list[MemoryBackupInfo])
async def list_backups(
    request: Request,
) -> list[MemoryBackupInfo]:
    """List existing backups."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")
    return service.list_backups()


@router.post("/restore")
async def restore_backup(
    request: Request,
    backup_path: str = Query(..., description="Full path to verified backup file"),
) -> dict[str, Any]:
    """Restore database from a verified backup."""
    service = getattr(request.app.state, "memory_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Memory service is not initialized")

    try:
        service.restore_backup(backup_path)
        return {"restored": True, "backup_path": backup_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Restore failed: {e}")
