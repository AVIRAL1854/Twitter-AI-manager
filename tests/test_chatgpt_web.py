"""Unit tests for ChatGPTWebPlanner extraction and response parsing."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.models.action import ActionPlan
from app.planner.chatgpt_web import ChatGPTWebPlanner


class TestChatGPTWebPlanner:
    """Test suite for ChatGPT Web automation planner parsing and logic."""

    def test_extract_json_from_markdown_block(self):
        planner = ChatGPTWebPlanner(Settings())
        markdown_text = """Here is the structured action plan based on your request:

```json
{
  "actions": [
    {
      "post_id": "p1",
      "action": "like",
      "reason": "cool startup launch",
      "content": null,
      "priority": 1
    },
    {
      "post_id": "p2",
      "action": "comment",
      "reason": "hiring role",
      "content": "awesome role! is this open to remote?",
      "priority": 2
    }
  ]
}
```

Hope this helps!"""

        plan = planner._extract_json_from_text(markdown_text)
        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) == 2
        assert plan.actions[0].post_id == "p1"
        assert plan.actions[0].action == "like"
        assert plan.actions[1].action == "comment"
        assert plan.actions[1].content == "awesome role! is this open to remote?"

    def test_extract_json_from_raw_text(self):
        planner = ChatGPTWebPlanner(Settings())
        raw_text = """{"actions": [{"post_id": "p100", "action": "skip", "reason": "irrelevant", "content": null, "priority": 1}]}"""

        plan = planner._extract_json_from_text(raw_text)
        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) == 1
        assert plan.actions[0].post_id == "p100"
        assert plan.actions[0].action == "skip"

    def test_extract_json_with_echoed_profile_and_goal(self):
        planner = ChatGPTWebPlanner(Settings())
        raw_text = """```json
{
  "profile": "Full-stack developer with 1 year and 8 months of experience...",
  "goal": "Engage casually and organically...",
  "actions": [
    {
      "post_id": "2094792644522397705",
      "action": "comment",
      "reason": "building in public",
      "content": "building in public hits different when you actually ship lol",
      "priority": 1
    },
    {
      "post_id": "2094695120247673057",
      "action": "like",
      "reason": "relatable dev joke",
      "content": null,
      "priority": 2
    }
  ]
}
```"""
        plan = planner._extract_json_from_text(raw_text)
        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) == 2
        assert plan.actions[0].post_id == "2094792644522397705"
        assert plan.actions[0].action == "comment"
        assert plan.actions[1].action == "like"

    @pytest.mark.asyncio
    async def test_plan_empty_posts_returns_empty(self):
        planner = ChatGPTWebPlanner(Settings())
        plan = await planner.plan(posts=[], remaining_budget=5)
        assert len(plan.actions) == 0

    @pytest.mark.asyncio
    async def test_plan_zero_budget_returns_empty(self, sample_normalized_posts):
        planner = ChatGPTWebPlanner(Settings())
        plan = await planner.plan(posts=sample_normalized_posts, remaining_budget=0)
        assert len(plan.actions) == 0

    def test_is_user_prompt_content_detection(self):
        planner = ChatGPTWebPlanner(Settings())
        prompt_copy = """Evaluate these posts and return your ActionPlan JSON:
{"profile": "Full-stack dev", "goal": "Engage"}
CRITICAL INSTRUCTIONS:
- Do NOT repeat or echo
- Example output format: {"actions": [{"post_id": "123", "action": "like"}]}
"""
        assert planner._is_user_prompt_content(prompt_copy) is True

        valid_response = """{"actions": [{"post_id": "999", "action": "like", "reason": "cool startup", "content": null, "priority": 1}]}"""
        assert planner._is_user_prompt_content(valid_response) is False


