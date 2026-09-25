"""Pydantic models and loader for user personality, target interactions, and avoid rules."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.observability.logging import get_logger

logger = get_logger("models.persona")


class PersonalityConfig(BaseModel):
    """Defines who the AI represents: name, background, tone, and style."""

    name: str = Field(
        default="Aviral",
        description="Name of the user/persona.",
    )
    role: str = Field(
        default="Full-Stack Developer & Indie Builder",
        description="Professional title or primary role.",
    )
    bio: str = Field(
        default=(
            "Full-stack developer with ~2 years of experience building modern web apps and AI tools. "
            "Creator of touchtorate.com. Passionate about early-stage startups, tech jobs, and connecting with fellow devs."
        ),
        description="Background narrative and personal bio.",
    )
    tone: str = Field(
        default="Casual, friendly, authentic, tech-savvy, slightly witty/Gen-Z, 100% human developer replying from phone or terminal.",
        description="Tone and voice style for comments and replies.",
    )
    style_rules: List[str] = Field(
        default_factory=lambda: [
            "Talk like a real developer texting or tweeting from a phone or terminal.",
            "Never sound like a corporate PR bot or ChatGPT.",
            "Never use corporate buzzwords like 'Fascinating perspective!', 'Insightful read!', 'Kudos on this remarkable milestone!'.",
            "Keep comments concise (1-2 short lines, under 150 chars).",
            "Ask curious tech questions or share brief relatable experiences.",
            "Sound 100% human, casual, and authentic.",
        ],
        description="Rules guiding sentence structure, length, and vocabulary.",
    )
    example_comments: List[str] = Field(
        default_factory=lambda: [
            "looks super clean, what stack did you build this with?",
            "ran into this exact nextjs bug yesterday haha",
            "congrats on the launch! loving the ui",
            "is this open source?",
            "awesome role, is this open to remote?",
            "underrated approach tbh",
        ],
        description="Few-shot examples demonstrating desired comment voice.",
    )


class TargetInteractionsConfig(BaseModel):
    """Defines what types of content, topics, and accounts the AI should interact with."""

    topics: List[str] = Field(
        default_factory=lambda: [
            "New startup launches, indie products, build in public, Show HN",
            "Developer tools, modern web tech (React, Next.js, TypeScript, Python, Node)",
            "Tech job openings, developer hiring, founder updates",
            "Relatable coding humor, dev memes, engineering hot takes",
            "AI agents, LLM apps, open source software",
        ],
        description="High-interest topics and niches to actively interact with.",
    )
    keywords: List[str] = Field(
        default_factory=lambda: [
            "launch",
            "built",
            "show hn",
            "indie hacker",
            "open source",
            "hiring",
            "job",
            "nextjs",
            "react",
            "python",
            "ai agent",
            "startup",
            "founder",
        ],
        description="Positive keywords signaling relevant content.",
    )
    preferred_actions: Dict[str, str] = Field(
        default_factory=lambda: {
            "cool_projects_and_launches": "comment",
            "hiring_and_job_openings": "comment",
            "dev_memes_and_relatable_takes": "like",
            "valuable_tech_tips_and_tutorials": "like",
            "thought_provoking_discussions": "comment",
        },
        description="Preferred action ('like' or 'comment') for different content types.",
    )


class AvoidInteractionsConfig(BaseModel):
    """Defines what the AI must NEVER interact with (topics, keywords, authors)."""

    topics: List[str] = Field(
        default_factory=lambda: [
            "Crypto pump-and-dump, memecoins, NFT airdrops, token presales",
            "Political arguments, geopolitical conflict, divisive culture wars, outrage bait",
            "NSFW, adult content, harassment, toxic flame wars",
            "Engagement farming, follow-for-follow schemes, generic motivational threads",
            "Unsolicited promotional spam, MLM, Forex trading signals",
        ],
        description="Categories and topics to strictly ignore or skip.",
    )
    negative_keywords: List[str] = Field(
        default_factory=lambda: [
            "crypto",
            "airdrop",
            "presale",
            "memecoin",
            "solana token",
            "pump",
            "f4f",
            "follow back",
            "follow for follow",
            "dm for promo",
            "giveaway",
            "retweet to win",
            "telegram channel",
        ],
        description="Strict blacklist keywords. Posts containing these will be deterministically skipped.",
    )
    blocked_accounts: List[str] = Field(
        default_factory=list,
        description="List of specific usernames (@handle) to never interact with.",
    )
    content_restrictions: List[str] = Field(
        default_factory=lambda: [
            "Never participate in political debates or flame wars.",
            "Never promote financial assets or cryptocurrencies.",
            "Never use offensive, toxic, or discriminatory language.",
            "Never give medical, legal, or financial advice.",
        ],
        description="Strict behavioral restrictions on drafted comment contents.",
    )


class PersonaConfig(BaseModel):
    """Top-level persona configuration combining personality, targets, and negative filters."""

    personality: PersonalityConfig = Field(default_factory=PersonalityConfig)
    what_to_interact_with: TargetInteractionsConfig = Field(default_factory=TargetInteractionsConfig)
    what_to_not_interact_with: AvoidInteractionsConfig = Field(default_factory=AvoidInteractionsConfig)

    @classmethod
    def default(cls) -> "PersonaConfig":
        """Generate default persona instance."""
        return cls()

    @classmethod
    def load_from_file(cls, file_path: str = "persona.json") -> "PersonaConfig":
        """Load and validate persona from a JSON file with graceful fallback."""
        target_path = Path(file_path).resolve()

        if not target_path.exists():
            logger.warning(
                f"Persona file not found at '{file_path}'. Using default persona configuration."
            )
            return cls.default()

        try:
            content = target_path.read_text(encoding="utf-8")
            # Strip JS/C-style comments if user added any (// ... or /* ... */)
            cleaned = re.sub(r"//.*?$|/\*.*?\*/", "", content, flags=re.MULTILINE | re.DOTALL)
            data = json.loads(cleaned)
            persona = cls.model_validate(data)
            logger.info(f"Loaded persona configuration from '{file_path}' (Persona: {persona.personality.name} - {persona.personality.role}).")
            return persona
        except Exception as e:
            logger.error(
                f"Failed to parse persona file '{file_path}': {e}. Falling back to default persona."
            )
            return cls.default()

    def save_to_file(self, file_path: str = "persona.json") -> None:
        """Save persona configuration to a formatted JSON file."""
        target_path = Path(file_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Saved persona configuration to '{file_path}'.")

