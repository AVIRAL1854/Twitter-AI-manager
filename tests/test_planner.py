"""Unit tests for AI Planner and PromptBuilder."""

import json
import pytest
from app.models.action import ActionPlan, ProposedAction
from app.planner.planner import MockPlanner
from app.planner.prompts import PromptBuilder


class TestPlanner:
    """Test suite for planner components and prompt construction."""

    def test_prompt_builder_format(self, test_settings, sample_normalized_posts):
        prompt = PromptBuilder.build_user_prompt(
            settings=test_settings,
            posts=sample_normalized_posts,
            remaining_budget=3,
        )

        assert "Evaluate these posts" in prompt
        assert "profile" in prompt
        assert "post_101" in prompt
        assert "post_102" in prompt

    @pytest.mark.asyncio
    async def test_mock_planner_generates_valid_plan(self, test_settings, sample_normalized_posts):
        planner = MockPlanner(test_settings)
        plan = await planner.plan(
            posts=sample_normalized_posts,
            remaining_budget=2,
        )

        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) == len(sample_normalized_posts)

        # First post is tech -> should be like or comment
        assert plan.actions[0].post_id == "post_101"
        assert plan.actions[0].action in ("like", "comment")

        # Second post is about lunch -> should be skip
        assert plan.actions[1].post_id == "post_102"
        assert plan.actions[1].action == "skip"

    @pytest.mark.asyncio
    async def test_mock_planner_empty_or_zero_budget(self, test_settings, sample_normalized_posts):
        planner = MockPlanner(test_settings)
        plan = await planner.plan(posts=[], remaining_budget=5)
        assert len(plan.actions) == 0

        plan_zero = await planner.plan(posts=sample_normalized_posts, remaining_budget=0)
        assert len(plan_zero.actions) == 0

