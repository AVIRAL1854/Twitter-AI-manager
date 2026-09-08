"""Unit tests for NvidiaOpenRouterPlanner and test_nvidia_connection."""

import pytest
from unittest.mock import patch
import httpx

from app.config import Settings
from app.models.action import ActionPlan
from app.observability.logging import PlanningError
from app.planner.nvidia_planner import NvidiaOpenRouterPlanner
from app.planner.nvidia_planner import test_nvidia_connection as check_nvidia_connection


class TestNvidiaPlanner:
    """Test suite for NVIDIA OpenRouter planner and connectivity tests."""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_planning_error(self, sample_normalized_posts):
        settings = Settings()
        settings.open_router_key = None
        planner = NvidiaOpenRouterPlanner(settings)

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(PlanningError, match="OPEN_ROUTER_KEY is not configured"):
                await planner.plan(sample_normalized_posts, remaining_budget=2)

    @pytest.mark.asyncio
    async def test_empty_posts_returns_empty_plan(self):
        settings = Settings()
        settings.open_router_key = "test_key"
        planner = NvidiaOpenRouterPlanner(settings)
        plan = await planner.plan(posts=[], remaining_budget=5)
        assert len(plan.actions) == 0

    @pytest.mark.asyncio
    async def test_plan_with_structured_json_response(self, sample_normalized_posts):
        settings = Settings()
        settings.open_router_key = "test_key"
        planner = NvidiaOpenRouterPlanner(settings)

        mock_response_json = {
            "choices": [
                {
                    "message": {
                        "content": '{"actions": [{"post_id": "post_101", "action": "like", "reason": "great startup", "content": null, "priority": 1, "explore_thread": false, "interest_score": 8}]}'
                    }
                }
            ]
        }

        mock_resp = httpx.Response(200, json=mock_response_json)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            plan = await planner.plan(sample_normalized_posts, remaining_budget=2)
            assert isinstance(plan, ActionPlan)
            assert len(plan.actions) == 1
            assert plan.actions[0].post_id == "post_101"
            assert plan.actions[0].action == "like"

        await planner.close()

    @pytest.mark.asyncio
    async def test_plan_with_safety_classifier_verdict(self, sample_normalized_posts):
        settings = Settings()
        settings.open_router_key = "test_key"
        planner = NvidiaOpenRouterPlanner(settings)

        mock_response_json = {
            "choices": [
                {
                    "message": {
                        "content": "User Safety: safe\nResponse Safety: safe"
                    }
                }
            ]
        }

        mock_resp = httpx.Response(200, json=mock_response_json)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            plan = await planner.plan(sample_normalized_posts, remaining_budget=2)
            assert isinstance(plan, ActionPlan)
            assert len(plan.actions) == len(sample_normalized_posts)
            # Post 1 is tech keyword post -> like or comment
            assert plan.actions[0].action in ("like", "comment")

        await planner.close()

    @pytest.mark.asyncio
    async def test_nvidia_connection_checker(self):
        settings = Settings()
        settings.open_router_key = "test_key"

        mock_response_json = {
            "model": "nvidia/nemotron-3.5-content-safety:free",
            "choices": [
                {
                    "message": {
                        "content": "User Safety: safe"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }
        }

        mock_resp = httpx.Response(200, json=mock_response_json)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            result = await check_nvidia_connection(settings)
            assert result["success"] is True
            assert result["status_code"] == 200
            assert result["model"] == "nvidia/nemotron-3.5-content-safety:free"
            assert result["response_content"] == "User Safety: safe"

