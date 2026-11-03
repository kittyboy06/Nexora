from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ModelItem(BaseModel):
    name: str = Field(..., description="Full model name and tag")
    size_bytes: int | None = Field(default=None, description="Size in bytes on disk")
    modified_at: str | None = Field(default=None, description="ISO timestamp of last modification")
    digest: str | None = Field(default=None, description="SHA256 digest")


class ModelListResponse(BaseModel):
    models: list[ModelItem] = Field(default_factory=list, description="Installed models")
    count: int = Field(..., description="Total installed model count")


class OllamaStatusResponse(BaseModel):
    reachable: bool = Field(..., description="Whether local Ollama daemon is reachable")
    model_available: bool = Field(..., description="Whether the configured model is installed locally")
    configured_model: str = Field(..., description="Name of the configured default model")
    installed_models: list[str] = Field(default_factory=list, description="List of installed model names")
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
