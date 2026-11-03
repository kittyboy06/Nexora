from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: dict | list | None = Field(default=None, description="Optional diagnostic details")


class ErrorResponse(BaseModel):
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
