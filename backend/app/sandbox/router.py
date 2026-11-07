"""FastAPI Router for Phase 10 Generated Tools and Sandbox Platform."""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.sandbox.models import (
    GeneratedToolProposal,
    GeneratedToolRecord,
    SandboxRunResult,
    ToolPromotionRequest,
    ToolUpdateRequest,
    ToolValidationReport,
    TrialRunRequest,
)

logger = logging.getLogger("nexora.sandbox.router")

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.post("/validate", response_model=ToolValidationReport)
async def validate_tool_proposal(
    proposal: GeneratedToolProposal,
    request: Request,
) -> ToolValidationReport:
    """Run deterministic AST static security analysis on a proposed tool."""
    service = getattr(request.app.state, "sandbox_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Sandbox service is not initialized")
    return service.validate_proposal(proposal)


@router.post("/trial", response_model=SandboxRunResult)
async def run_sandbox_trial(
    req: TrialRunRequest,
    request: Request,
) -> SandboxRunResult:
    """Execute a proposed tool trial inside the isolated Windows Job Object sandbox."""
    service = getattr(request.app.state, "sandbox_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Sandbox service is not initialized")

    return await service.run_trial(
        proposal=req.proposal,
        mode=req.mode,
        runtime_arguments=req.runtime_arguments,
    )


@router.get("/evidence", response_model=list[SandboxRunResult])
async def list_sandbox_evidence(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
) -> list[SandboxRunResult]:
    """Retrieve past sandbox execution evidence and telemetry records."""
    service = getattr(request.app.state, "sandbox_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Sandbox service is not initialized")
    return service.list_evidence(limit=limit)


@router.get("/evidence/{run_id}", response_model=SandboxRunResult)
async def get_sandbox_evidence(
    run_id: str,
    request: Request,
) -> SandboxRunResult:
    """Fetch specific sandbox run evidence by unique run ID."""
    service = getattr(request.app.state, "sandbox_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Sandbox service is not initialized")

    evidence = service.get_evidence(run_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Evidence for run '{run_id}' not found")
    return evidence


@router.get("/tools", response_model=list[GeneratedToolRecord])
async def list_generated_tools(
    request: Request,
) -> list[GeneratedToolRecord]:
    """List all registered generated tools with their active versions."""
    gen_reg = getattr(request.app.state, "generated_tool_registry", None)
    if not gen_reg:
        raise HTTPException(status_code=503, detail="Generated tool registry is not initialized")
    return gen_reg.list_tools()


@router.get("/tools/{tool_name}", response_model=GeneratedToolRecord)
async def get_generated_tool(
    tool_name: str,
    request: Request,
    version: str | None = None,
) -> GeneratedToolRecord:
    """Fetch details of a generated tool by name and optional version."""
    gen_reg = getattr(request.app.state, "generated_tool_registry", None)
    if not gen_reg:
        raise HTTPException(status_code=503, detail="Generated tool registry is not initialized")

    record = gen_reg.get_tool(tool_name, version=version)
    if not record:
        raise HTTPException(status_code=404, detail=f"Generated tool '{tool_name}' not found")
    return record


@router.get("/tools/{tool_name}/versions", response_model=list[str])
async def list_generated_tool_versions(
    tool_name: str,
    request: Request,
) -> list[str]:
    """List all available versions for a generated tool."""
    gen_reg = getattr(request.app.state, "generated_tool_registry", None)
    if not gen_reg:
        raise HTTPException(status_code=503, detail="Generated tool registry is not initialized")
    return gen_reg.list_versions(tool_name)


@router.post("/tools/promote", response_model=GeneratedToolRecord)
async def promote_tool(
    req: ToolPromotionRequest,
    request: Request,
) -> GeneratedToolRecord:
    """Promote a validated proposal with proven sandbox trial evidence to the active catalog."""
    service = getattr(request.app.state, "sandbox_service", None)
    gen_reg = getattr(request.app.state, "generated_tool_registry", None)
    bridge_mgr = getattr(request.app.state, "generated_tool_bridge", None)

    if not service or not gen_reg or not bridge_mgr:
        raise HTTPException(status_code=503, detail="Sandbox platform components not fully initialized")

    evidence = service.get_evidence(req.evidence_run_id)
    if not evidence:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence run ID '{req.evidence_run_id}' not found. Cannot promote without proven trial run.",
        )

    try:
        record = gen_reg.promote(
            proposal=req.proposal,
            evidence=evidence,
            reviewer=req.reviewer,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Mount in ToolRegistry
    bridge_mgr.register_tool(record)
    logger.info("Promoted and mounted generated tool: gen__%s", record.manifest.name)
    return record


@router.post("/tools/{tool_name}/update", response_model=GeneratedToolRecord)
async def update_generated_tool(
    tool_name: str,
    req: ToolUpdateRequest,
    request: Request,
) -> GeneratedToolRecord:
    """Update enabled state or rollback active version of a generated tool."""
    gen_reg = getattr(request.app.state, "generated_tool_registry", None)
    bridge_mgr = getattr(request.app.state, "generated_tool_bridge", None)

    if not gen_reg or not bridge_mgr:
        raise HTTPException(status_code=503, detail="Generated tool registry is not initialized")

    record = gen_reg.get_tool(tool_name)
    if not record:
        raise HTTPException(status_code=404, detail=f"Generated tool '{tool_name}' not found")

    if req.is_enabled is not None:
        gen_reg.set_enabled(tool_name, req.is_enabled)
        if req.is_enabled:
            updated_rec = gen_reg.get_tool(tool_name)
            if updated_rec:
                bridge_mgr.register_tool(updated_rec)
        else:
            bridge_mgr.unregister_tool(tool_name)

    if req.target_version is not None:
        success = gen_reg.rollback(tool_name, req.target_version)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Version '{req.target_version}' does not exist for tool '{tool_name}'",
            )
        updated_rec = gen_reg.get_tool(tool_name)
        if updated_rec and updated_rec.is_enabled:
            bridge_mgr.register_tool(updated_rec)

    updated_record = gen_reg.get_tool(tool_name)
    if not updated_record:
        raise HTTPException(status_code=500, detail="Failed to fetch updated record")
    return updated_record


@router.delete("/tools/{tool_name}")
async def delete_generated_tool(
    tool_name: str,
    request: Request,
) -> dict[str, Any]:
    """Delete a generated tool and unmount it from the active ToolRegistry."""
    gen_reg = getattr(request.app.state, "generated_tool_registry", None)
    bridge_mgr = getattr(request.app.state, "generated_tool_bridge", None)

    if not gen_reg or not bridge_mgr:
        raise HTTPException(status_code=503, detail="Generated tool registry is not initialized")

    bridge_mgr.unregister_tool(tool_name)
    deleted = gen_reg.delete_tool(tool_name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Generated tool '{tool_name}' not found")

    return {"deleted": True, "tool_name": tool_name}
