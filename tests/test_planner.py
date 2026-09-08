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

    def test_ai_planner_parse_valid_json(self):
        from app.planner.planner import AIPlanner

        valid_json = """{
            "actions": [
                {
                    "post_id": "111",
                    "action": "like",
                    "reason": "cool startup",
                    "content": null,
                    "priority": 1,
                    "explore_thread": false,
                    "interest_score": 7
                }
            ]
        }"""
        plan = AIPlanner._parse_and_validate_response(valid_json)
        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) == 1
        assert plan.actions[0].post_id == "111"
        assert plan.actions[0].action == "like"

    def test_ai_planner_parse_truncated_json_recovery(self):
        from app.planner.planner import AIPlanner

        # Simulate truncation mid-stream (similar to EOF while parsing a string at line 97: "content": "100%)
        truncated_json = """{
  "actions": [
    {
      "post_id": "111",
      "action": "like",
      "reason": "cool startup",
      "content": null,
      "priority": 1,
      "explore_thread": false,
      "interest_score": 7
    },
    {
      "post_id": "222",
      "action": "comment",
      "reason": "relatable dev take",
      "content": "100%"""

        plan = AIPlanner._parse_and_validate_response(truncated_json)
        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) == 1
        assert plan.actions[0].post_id == "111"
        assert plan.actions[0].action == "like"

    def test_ai_planner_parse_markdown_wrapped_json(self):
        from app.planner.planner import AIPlanner

        md_json = """```json
{
  "actions": [
    {
      "post_id": "333",
      "action": "skip",
      "reason": "not relevant",
      "content": null,
      "priority": 1
    }
  ]
}
```"""
        plan = AIPlanner._parse_and_validate_response(md_json)
        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) == 1
        assert plan.actions[0].post_id == "333"


