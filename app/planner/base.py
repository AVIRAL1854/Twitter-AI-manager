"""Base abstract class for all AI planners."""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.memory.models import InteractionRecord
from app.models.action import ActionPlan
from app.models.post import NormalizedPost


class BasePlanner(ABC):
    """Abstract interface for planning layer."""

    @abstractmethod
    async def plan(
        self,
        posts: List[NormalizedPost],
        remaining_budget: int,
        recent_history: Optional[List[InteractionRecord]] = None,
    ) -> ActionPlan:
        """Generate an ActionPlan for the provided batch of posts."""
        pass

