"""Serializable specialist profiles for local model selection."""

from enum import Enum
from pydantic import BaseModel, Field


class TaskKind(str, Enum):
    CODE = "code"
    RESEARCH = "research"
    REASONING = "reasoning"
    GENERAL = "general"


class ModelProfile(BaseModel):
    profile_id: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=200)
    specialties: list[TaskKind] = Field(default_factory=list)
    system_instruction: str = ""
    role: str = "worker"
    enabled: bool = True


class ModelProfileCatalogue(BaseModel):
    profiles: list[ModelProfile] = Field(default_factory=list)


class ModelProfileStatus(ModelProfile):
    installed: bool


class ModelProfileListResponse(BaseModel):
    profiles: list[ModelProfileStatus]
    count: int


class RouteSelection(BaseModel):
    profile_id: str
    model: str
    task_kind: TaskKind
    reason: str
    escalated: bool = False
