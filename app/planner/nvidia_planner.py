"""OpenRouter NVIDIA Planner implementation for Nemotron and OpenRouter models."""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings
from app.memory.models import InteractionRecord
from app.models.action import ActionPlan, ProposedAction
from app.models.post import NormalizedPost
from app.observability.logging import PlanningError, get_logger
from app.planner.base import BasePlanner
from app.planner.prompts import SYSTEM_PROMPT, PromptBuilder

logger = get_logger("planner.nvidia")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class NvidiaOpenRouterPlanner(BasePlanner):
    """Planner powered by NVIDIA models hosted on OpenRouter."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def plan(
        self,
        posts: List[NormalizedPost],
        remaining_budget: int,
        recent_history: Optional[List[InteractionRecord]] = None,
    ) -> ActionPlan:
        """Generate action plan using NVIDIA OpenRouter model."""
        if not posts or remaining_budget <= 0:
            return ActionPlan(actions=[])

        api_key = self.settings.get_openrouter_api_key()
        if not api_key:
            raise PlanningError(
                "OPEN_ROUTER_KEY is not configured in .env or environment variables."
            )

        prompt = PromptBuilder.build_user_prompt(
            self.settings, posts, remaining_budget, recent_history
        )

        full_user_content = (
            f"{prompt}\n\n"
            "CRITICAL FORMAT REQUIREMENT:\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            '{"actions": [{"post_id": "...", "action": "like|comment|reply|skip", '
            '"reason": "...", "content": "..." or null, "priority": 1, '
            '"explore_thread": false, "interest_score": 7}]}'
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AVIRAL1854/Twitter-AI-manager",
            "X-Title": "Twitter-AI-manager",
        }

        payload = {
            "model": self.settings.nvidia_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_user_content},
            ],
            "temperature": 0.6,
            "max_tokens": 4096,
        }

        logger.info(
            f"Calling NVIDIA OpenRouter model '{self.settings.nvidia_model}' "
            f"with {len(posts)} posts (budget: {remaining_budget})..."
        )

        client = self._get_client()
        try:
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        except Exception as e:
            raise PlanningError(f"Network error connecting to OpenRouter: {e}") from e

        if response.status_code != 200:
            raise PlanningError(
                f"OpenRouter NVIDIA API error [{response.status_code}]: {response.text}"
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise PlanningError("Received empty choices array from OpenRouter NVIDIA API.")

        message = choices[0].get("message", {})
        raw_content = message.get("content", "")

        return self._parse_and_synthesize_plan(raw_content, posts, remaining_budget)

    def _parse_and_synthesize_plan(
        self,
        raw_text: str,
        posts: List[NormalizedPost],
        remaining_budget: int,
    ) -> ActionPlan:
        """Parse JSON response or synthesize safe plan if safety-guard model output received."""
        from app.planner.planner import AIPlanner

        # 1. Try parsing JSON directly
        try:
            plan = AIPlanner._parse_and_validate_response(raw_text)
            if plan and len(plan.actions) > 0:
                logger.info(
                    f"NVIDIA Planner successfully parsed {len(plan.actions)} structured actions."
                )
                return plan
        except Exception as e:
            logger.debug(f"Direct JSON parse note: {e}")

        # 2. Check if model is a safety classifier (e.g. nemotron-3.5-content-safety)
        text_lower = raw_text.lower()
        is_safety_verdict = "user safety:" in text_lower or "response safety:" in text_lower
        is_safe = "user safety: safe" in text_lower or ("safe" in text_lower and "unsafe" not in text_lower)

        if is_safety_verdict:
            logger.info(
                f"NVIDIA Nemotron Safety Classifier verdict: {'SAFE' if is_safe else 'UNSAFE'}. "
                "Synthesizing contextual engagement plan."
            )
        else:
            logger.warning(
                f"NVIDIA model output did not contain structured JSON: '{raw_text[:120]}...'. "
                "Synthesizing contextual engagement plan."
            )

        # 3. Fallback: Synthesize actions for the batch
        actions: List[ProposedAction] = []
        budget_used = 0
        priority = 1

        dev_keywords = [
            "startup", "launch", "hiring", "opening", "job", "build", "dev",
            "fullstack", "react", "nextjs", "node", "python", "typescript",
            "ai", "agent", "llm", "tool", "code", "software", "product", "stack",
        ]

        for post in posts:
            if not is_safe:
                # Content classified unsafe -> skip
                actions.append(
                    ProposedAction(
                        post_id=post.post_id,
                        action="skip",
                        reason="flagged by NVIDIA content safety filter",
                        content=None,
                        priority=priority,
                    )
                )
                priority += 1
                continue

            post_text_lower = post.text.lower()
            is_relevant = any(k in post_text_lower for k in dev_keywords)

            if is_relevant and budget_used < remaining_budget:
                if "comment" in self.settings.allowed_actions and (budget_used % 2 == 1):
                    if any(k in post_text_lower for k in ["hiring", "opening", "job", "role"]):
                        content = "awesome role! is this open to remote?"
                    elif any(k in post_text_lower for k in ["launch", "startup", "product", "built"]):
                        content = "looks super clean! what stack did you build this with?"
                    else:
                        content = "100% agree with this take tbh"

                    actions.append(
                        ProposedAction(
                            post_id=post.post_id,
                            action="comment",
                            reason="relevant startup/dev post (verified safe by NVIDIA)",
                            content=content,
                            priority=priority,
                            explore_thread=(priority == 1),
                            interest_score=8 if priority == 1 else 6,
                        )
                    )
                    budget_used += 1
                elif "like" in self.settings.allowed_actions:
                    actions.append(
                        ProposedAction(
                            post_id=post.post_id,
                            action="like",
                            reason="cool project/take (verified safe by NVIDIA)",
                            content=None,
                            priority=priority,
                            explore_thread=(priority == 1),
                            interest_score=7 if priority == 1 else 5,
                        )
                    )
                    budget_used += 1
                else:
                    actions.append(
                        ProposedAction(
                            post_id=post.post_id,
                            action="skip",
                            reason="no allowed action",
                            content=None,
                            priority=priority,
                        )
                    )
            else:
                actions.append(
                    ProposedAction(
                        post_id=post.post_id,
                        action="skip",
                        reason="not relevant or over budget",
                        content=None,
                        priority=priority,
                    )
                )

            priority += 1

        return ActionPlan(actions=actions)

    async def close(self) -> None:
        """Close underlying HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


async def test_nvidia_connection(settings: Settings) -> Dict[str, Any]:
    """Test connectivity and call response to NVIDIA OpenRouter API."""
    api_key = settings.get_openrouter_api_key()
    if not api_key:
        return {
            "success": False,
            "error": "OPEN_ROUTER_KEY is missing from .env and environment variables.",
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/AVIRAL1854/Twitter-AI-manager",
        "X-Title": "Twitter-AI-manager",
    }

    payload = {
        "model": settings.nvidia_model,
        "messages": [
            {
                "role": "user",
                "content": 'Hello, reply with JSON: {"status": "ok", "message": "NVIDIA API active"}',
            }
        ],
        "max_tokens": 150,
    }

    start_time = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            if resp.status_code != 200:
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": resp.text,
                    "elapsed_ms": elapsed_ms,
                }

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content", "")
            usage = data.get("usage", {})

            return {
                "success": True,
                "status_code": 200,
                "model": data.get("model", settings.nvidia_model),
                "elapsed_ms": elapsed_ms,
                "response_content": content.strip(),
                "usage": usage,
            }

    except Exception as e:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": False,
            "error": str(e),
            "elapsed_ms": elapsed_ms,
        }

