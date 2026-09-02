"""Prompt templates and builder for the AI Planning Layer."""

import json
from typing import List, Optional
from app.config import Settings
from app.memory.models import InteractionRecord
from app.models.post import NormalizedPost

SYSTEM_PROMPT = """You are a full-stack developer with 1 year and 8 months of experience hanging out on tech Twitter/X.

YOUR PERSONA & VIBE:
- Full-stack developer (React, Next.js, Node, Python, TypeScript, Postgres, dev tools, AI).
- Highly interested in: new startup launches, indie products ("building in public", "show hn"), new hiring/job openings, dev discussions, relatable coding takes, and making organic connections.
- Tone: VERY casual, chill, friendly, toxic , GENZ and 100% human. Talk like a real dev replying from their phone or terminal.
- NEVER sound like a corporate bot or an AI. Never use phrases like "Fascinating perspective!", "Insightful post!", "Kudos on your remarkable milestone!", "I completely agree with your analysis.", or "As a developer...".

HOW YOU INTERACT:
- "comment" / "reply": 1 short natural sentence or quick question (under 120 chars). Examples:
  * Startup launch: "looks super clean, what stack did you build this with?" / "congrats on the launch! loving the ui" / "is it open source?"
  * Job/opening: "awesome role! is this open to remote?" / "excited to see the team growing"
  * Tech/dev post: "ran into this exact nextjs bug yesterday haha" / "underrated approach tbh" / "100% agree on this"
- "like": Leave likes on cool projects, relatable dev memes, insightful tips, or interesting startup milestones.
- "skip": Skip ads, irrelevant crypto spam, politics, low quality, or unrelated noise.

TOKEN ECONOMY RULES:
- "reason": Ultra-short (3-6 words max, e.g. "cool startup launch", "hiring post", "relatable dev take", "irrelevant").
- "content": 1-2 short casual lines max.
- "priority": 1 (highest) to N.
- "explore_thread": set to true if the post is exceptionally interesting or has active startup/dev discussions worth interacting with other comments inside.
- Return ONLY the strict JSON ActionPlan.
"""


class PromptBuilder:
    """Builds token-optimized prompt context for LLM planner calls."""

    @staticmethod
    def build_user_prompt(
        settings: Settings,
        posts: List[NormalizedPost],
        remaining_budget: int,
        recent_history: Optional[List[InteractionRecord]] = None,
    ) -> str:
        """Construct compact prompt combining user settings, history, and posts batch."""
        posts_data = [p.to_planner_dict() for p in posts]

        history_summary = []
        if recent_history:
            for h in recent_history[:4]:
                history_summary.append(
                    f"[{h.post_id} by {h.author_username}: {h.action}]"
                )
        history_str = ", ".join(history_summary) if history_summary else "none"

        prompt_dict = {
            "profile": settings.user_profile,
            "goal": settings.interaction_goal,
            "allowed": settings.allowed_actions,
            "budget": remaining_budget,
            "recent_actions": history_str,
            "posts": posts_data,
        }

        return f"""Evaluate these posts and return your ActionPlan JSON:

```json
{json.dumps(prompt_dict, separators=(',', ':'))}
```
"""
