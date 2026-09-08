"""AI Planner interface and implementations using Google GenAI and Mock fallbacks."""

import json
from abc import ABC, abstractmethod
from typing import List, Optional

from app.config import Settings
from app.memory.models import InteractionRecord
from app.models.action import ActionPlan, ProposedAction
from app.models.post import NormalizedPost
from app.observability.logging import PlanningError, get_logger
from app.planner.base import BasePlanner
from app.planner.chatgpt_web import ChatGPTWebPlanner
from app.planner.prompts import SYSTEM_PROMPT, PromptBuilder

logger = get_logger("planner.ai")

__all__ = ["AIPlanner", "BasePlanner", "ChatGPTWebPlanner", "MockPlanner"]


class AIPlanner(BasePlanner):
    """Gemini-powered planner using the google-genai SDK with structured output."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            api_key = self.settings.gemini_api_key
            if not api_key:
                import os
                api_key = os.environ.get("GEMINI_API_KEY")

            if not api_key:
                raise PlanningError(
                    "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in environment or use MockPlanner."
                )
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def plan(
        self,
        posts: List[NormalizedPost],
        remaining_budget: int,
        recent_history: Optional[List[InteractionRecord]] = None,
    ) -> ActionPlan:
        if not posts:
            return ActionPlan(actions=[])

        prompt = PromptBuilder.build_user_prompt(
            self.settings, posts, remaining_budget, recent_history
        )

        try:
            from google.genai import types

            client = self._get_client()
            logger.info(
                f"Calling AI Planner with {len(posts)} posts (remaining budget: {remaining_budget})..."
            )

            response = await client.aio.models.generate_content(
                model=self.settings.llm_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=ActionPlan,
                    max_output_tokens=self.settings.llm_max_output_tokens,
                    temperature=0.6,
                ),
            )

            if not response.text:
                raise PlanningError("Received empty response from Gemini Planner.")

            # Parse structured output with resilient repair for truncated responses
            plan = self._parse_and_validate_response(response.text)
            logger.info(f"AI Planner proposed {len(plan.actions)} actions.")
            return plan

        except Exception as e:
            if isinstance(e, PlanningError):
                raise
            raise PlanningError(f"AI Planner failed during execution: {e}") from e

    @staticmethod
    def _parse_and_validate_response(raw_text: str) -> ActionPlan:
        """Parse Gemini output into ActionPlan with graceful recovery for truncated JSON."""
        text = raw_text.strip()

        # 1. Direct standard validation
        try:
            return ActionPlan.model_validate_json(text)
        except Exception as e:
            logger.warning(
                f"Direct JSON validation failed ({e}). Attempting recovery for truncated JSON output..."
            )

        # 2. Extract markdown code blocks if wrapped
        if "```" in text:
            import re

            code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            for block in reversed(code_blocks):
                try:
                    return ActionPlan.model_validate_json(block.strip())
                except Exception:
                    pass

        # 3. Truncated recovery: salvage all completed action objects before the cut-off
        try:
            import json
            import re

            actions_match = re.search(r'"actions"\s*:\s*\[', text)
            if actions_match:
                actions_start = actions_match.end()
                completed_actions: List[dict] = []
                idx = actions_start

                while idx < len(text):
                    obj_start = text.find("{", idx)
                    if obj_start == -1:
                        break

                    depth = 0
                    in_string = False
                    escape = False
                    obj_end = -1

                    for i in range(obj_start, len(text)):
                        c = text[i]
                        if escape:
                            escape = False
                            continue
                        if c == "\\":
                            escape = True
                            continue
                        if c == '"':
                            in_string = not in_string
                            continue
                        if not in_string:
                            if c == "{":
                                depth += 1
                            elif c == "}":
                                depth -= 1
                                if depth == 0:
                                    obj_end = i
                                    break

                    if obj_end != -1:
                        candidate_str = text[obj_start : obj_end + 1]
                        try:
                            action_dict = json.loads(candidate_str)
                            if "post_id" in action_dict or "id" in action_dict:
                                completed_actions.append(action_dict)
                        except Exception:
                            pass
                        idx = obj_end + 1
                    else:
                        # Incomplete/truncated object at the cut-off point
                        break

                if completed_actions:
                    logger.warning(
                        f"Successfully recovered {len(completed_actions)} completed actions from truncated JSON output."
                    )
                    repaired_json = json.dumps({"actions": completed_actions})
                    return ActionPlan.model_validate_json(repaired_json)

        except Exception as repair_err:
            logger.debug(f"JSON repair error: {repair_err}")

        # If recovery could not salvage any actions, re-raise original validation
        return ActionPlan.model_validate_json(text)


class MockPlanner(BasePlanner):
    """Deterministic mock planner for testing, dry runs, and offline execution."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def plan(
        self,
        posts: List[NormalizedPost],
        remaining_budget: int,
        recent_history: Optional[List[InteractionRecord]] = None,
    ) -> ActionPlan:
        if not posts or remaining_budget <= 0:
            return ActionPlan(actions=[])

        actions: List[ProposedAction] = []
        budget_used = 0
        priority = 1

        dev_keywords = [
            "startup", "launch", "hiring", "opening", "job", "build", "dev",
            "fullstack", "react", "nextjs", "node", "python", "typescript",
            "ai", "agent", "llm", "tool", "code", "software", "product", "stack"
        ]

        for post in posts:
            text_lower = post.text.lower()
            is_relevant = any(k in text_lower for k in dev_keywords)

            if is_relevant and budget_used < remaining_budget:
                if "comment" in self.settings.allowed_actions and (budget_used % 2 == 1):
                    # Casual natural comment matching post type
                    if any(k in text_lower for k in ["hiring", "opening", "job", "role"]):
                        content = "awesome role! is this open to remote?"
                    elif any(k in text_lower for k in ["launch", "startup", "product", "built"]):
                        content = "looks super clean! what stack did you build this with?"
                    else:
                        content = "100% agree with this take tbh"

                    actions.append(
                        ProposedAction(
                            post_id=post.post_id,
                            action="comment",
                            reason="relevant startup/dev post",
                            content=content,
                            priority=priority,
                            explore_thread=(priority == 1),
                        )
                    )
                    budget_used += 1
                elif "like" in self.settings.allowed_actions:
                    actions.append(
                        ProposedAction(
                            post_id=post.post_id,
                            action="like",
                            reason="cool project/take",
                            content=None,
                            priority=priority,
                            explore_thread=(priority == 1),
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

        logger.debug(f"MockPlanner generated plan with {len(actions)} actions.")
        return ActionPlan(actions=actions)

