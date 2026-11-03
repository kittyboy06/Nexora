from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    status: Literal["ok"] = Field(default="ok", description="Operational health status of the FastAPI server")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
