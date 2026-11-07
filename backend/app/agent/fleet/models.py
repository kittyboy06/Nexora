"""Domain Models for Dynamic Agent Fleet and DAG Orchestration."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class FleetNodeState(str, Enum):
    """Lifecycle state of a node within the fleet DAG."""

    QUEUED = "QUEUED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Artifact(BaseModel):
    """Immutable, schema-validated output record produced by a specialist node."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    node_id: str
    producer_role: str
    schema_version: str = "1.0"
    content: dict[str, Any] | str
    content_hash: str
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        node_id: str,
        producer_role: str,
        content: dict[str, Any] | str,
        evidence_refs: list[str] | None = None,
        schema_version: str = "1.0",
    ) -> "Artifact":
        """Factory creating an immutable artifact with calculated SHA-256 hash."""
        if isinstance(content, dict):
            serialized = json.dumps(content, sort_keys=True, separators=(",", ":"))
        else:
            serialized = str(content)
        content_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return cls(
            node_id=node_id,
            producer_role=producer_role,
            schema_version=schema_version,
            content=content,
            content_hash=content_hash,
            evidence_refs=evidence_refs or [],
        )


class FleetNode(BaseModel):
    """Specialist subtask node in the fleet dependency DAG."""

    node_id: str
    role: str
    objective: str
    dependencies: list[str] = Field(default_factory=list)
    input_artifact_refs: list[str] = Field(default_factory=list)
    capability_allowlist: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    token_budget: int = 2048
    state: FleetNodeState = FleetNodeState.QUEUED
    result_artifact_id: str | None = None
    error: str | None = None


class FleetPlan(BaseModel):
    """Validated directed acyclic graph defining a multi-agent task execution plan."""

    fleet_id: str = Field(default_factory=lambda: f"fleet_{uuid.uuid4().hex[:12]}")
    parent_task_id: str
    goal: str
    nodes: dict[str, FleetNode] = Field(default_factory=dict)
    max_nodes: int = 5
    version: str = "1.0"

    def get_node(self, node_id: str) -> FleetNode | None:
        """Retrieve node by ID."""
        return self.nodes.get(node_id)


class FleetResult(BaseModel):
    """Aggregated final outcome of a FleetPlan execution."""

    fleet_id: str
    parent_task_id: str
    node_outcomes: dict[str, FleetNodeState] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    summary: str = ""
    is_verified: bool = False
    error: str | None = None
