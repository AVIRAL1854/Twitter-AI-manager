"""Run state and metrics tracking models."""

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field

RunStatus = Literal[
    "initialized",
    "running",
    "completed",
    "budget_exhausted",
    "timeout",
    "max_scroll_reached",
    "no_posts_found",
    "error",
    "stopped",
]


class RunMetrics(BaseModel):
    """Execution metrics gathered during a run."""

    posts_discovered: int = 0
    posts_eligible: int = 0
    posts_sent_to_planner: int = 0
    actions_proposed: int = 0
    actions_approved: int = 0
    actions_executed: int = 0
    actions_succeeded: int = 0
    actions_failed: int = 0
    deep_dives_performed: int = 0
    inner_interactions_executed: int = 0
    interactions_remaining: int = 0
    scroll_count: int = 0
    run_duration_seconds: float = 0.0


class RunState(BaseModel):
    """Overall state of a specific execution run."""

    run_id: str
    status: RunStatus = "initialized"
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    error: Optional[str] = None

