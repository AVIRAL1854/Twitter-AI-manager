"""Prompt templates and builder for the AI Planning Layer."""

import json
from typing import TYPE_CHECKING, List, Optional
from app.config import Settings
from app.memory.models import InteractionRecord
from app.models.post import NormalizedPost

if TYPE_CHECKING:
    from app.models.persona import PersonaConfig


class PromptBuilder:
    """Builds token-optimized prompt context for LLM planner calls."""

    @staticmethod
    def build_system_prompt(persona: Optional["PersonaConfig"] = None) -> str:
        """Construct rich system instructions dynamically from persona configuration."""
        if persona is None:
            from app.models.persona import PersonaConfig
            persona = PersonaConfig.load_from_file()

        p = persona.personality
        targets = persona.what_to_interact_with
        avoid = persona.what_to_not_interact_with

        rules_list = "\n".join(f"- {rule}" for rule in p.style_rules)
        examples_list = "\n".join(f'  * "{ex}"' for ex in p.example_comments)
        topics_list = "\n".join(f"- {topic}" for topic in targets.topics)
        keywords_str = ", ".join(targets.keywords)
        avoid_topics_list = "\n".join(f"- {topic}" for topic in avoid.topics)
        avoid_keywords_str = ", ".join(avoid.negative_keywords)
        restrictions_list = "\n".join(f"- {r}" for r in avoid.content_restrictions)

        return f"""You are {p.name}, a {p.role} hanging out on tech Twitter/X.

BIO & IDENTITY:
{p.bio}

TONE & STYLE:
- Tone: {p.tone}
{rules_list}

REPRESENTATIVE EXAMPLE COMMENTS & REPLIES:
{examples_list}

WHAT TO INTERACT WITH (PRIORITIZE THESE):
{topics_list}
Target Keywords: {keywords_str}

WHAT TO STRICTLY AVOID / SKIP (NEVER INTERACT WITH):
{avoid_topics_list}
Forbidden Keywords: {avoid_keywords_str}
Safety Restrictions:
{restrictions_list}

HOW YOU INTERACT:
- "comment" / "reply": 1 short natural sentence or quick question (under 140 chars) adhering to your persona.
- "like": Leave likes on cool projects, relatable dev memes, insightful tips, or interesting startup milestones.
- "skip": Always skip ads, irrelevant crypto spam, politics, low quality, or unrelated noise.

TOKEN ECONOMY RULES:
- "reason": Ultra-short (3-6 words max, e.g. "cool startup launch", "hiring post", "relatable dev take", "crypto spam").
- "content": 1-2 short casual lines max (or null for like/skip).
- "priority": 1 (highest) to N.
- "explore_thread": set to true if the post is exceptionally interesting or has active startup/dev discussions worth interacting with other comments inside.
- Return ONLY the strict JSON ActionPlan.
"""

    @staticmethod
    def build_user_prompt(
        settings: Settings,
        posts: List[NormalizedPost],
        remaining_budget: int,
        recent_history: Optional[List[InteractionRecord]] = None,
        persona: Optional["PersonaConfig"] = None,
    ) -> str:
        """Construct compact prompt combining user settings, persona, history, and posts batch."""
        if persona is None:
            persona = settings.get_persona()

        posts_data = [p.to_planner_dict() for p in posts]

        history_summary = []
        if recent_history:
            for h in recent_history[:4]:
                history_summary.append(
                    f"[{h.post_id} by {h.author_username}: {h.action}]"
                )
        history_str = ", ".join(history_summary) if history_summary else "none"

        prompt_dict = {
            "profile": settings.user_profile or (persona.personality.bio if persona else ""),
            "goal": settings.interaction_goal or (", ".join(persona.what_to_interact_with.topics) if persona else ""),
            "allowed": settings.allowed_actions,
            "budget": remaining_budget,
            "recent_actions": history_str,
            "posts": posts_data,
        }

        if persona:
            prompt_dict["target_topics"] = persona.what_to_interact_with.topics
            prompt_dict["avoid_topics"] = persona.what_to_not_interact_with.topics

        return f"""Evaluate these posts and return your ActionPlan JSON:

```json
{json.dumps(prompt_dict, separators=(',', ':'))}
```
"""


# Default module-level prompt for backwards compatibility
SYSTEM_PROMPT = PromptBuilder.build_system_prompt()
