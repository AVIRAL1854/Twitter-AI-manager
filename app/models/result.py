"""Execution result models representing browser action outcomes."""

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field
from app.models.action import ActionType

ExecutionStatus = Literal["success", "failed", "skipped"]


class ExecutionResult(BaseModel):
    """Result of executing an approved interaction action in the browser."""

    post_id: str
    action: ActionType
    status: ExecutionStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    duration_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        """Return True if execution succeeded."""
        return self.status == "success"

