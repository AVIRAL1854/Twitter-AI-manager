"""Action models defining proposed, planned, and validated actions."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

ActionType = Literal["like", "comment", "reply", "skip"]


class ProposedAction(BaseModel):
    """Action proposed by the AI Planner for a single post."""

    post_id: str
    action: ActionType
    reason: str
    content: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=10)
    interest_score: Optional[int] = Field(
        default=None, description="Relevance score from 1 (low) to 10 (extremely interesting)."
    )
    explore_thread: bool = Field(
        default=False, description="Whether to dive inside this post to explore and interact with comments."
    )


class ActionPlan(BaseModel):
    """Structured plan returned by the AI Planning Layer."""

    actions: list[ProposedAction] = Field(default_factory=list)


class ValidatedAction(BaseModel):
    """Action strictly approved by the Validation Layer for execution."""

    post_id: str
    action: ActionType
    reason: str
    content: Optional[str] = None
    priority: int
    post_url: str
    author_username: str
    parent_post_id: Optional[str] = None
    explore_thread: bool = False

