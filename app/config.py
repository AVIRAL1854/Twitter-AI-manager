"""Configuration settings for the X Interaction Agent."""

from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.models.action import ActionType


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Target & Discovery
    target_page: str = Field(
        default="https://x.com/home",
        description="Target X page/feed URL to scrape and interact with.",
    )
    posts_per_batch: int = Field(
        default=15,
        description="Maximum posts to process in one planning batch.",
    )
    max_scroll_attempts: int = Field(
        default=10,
        description="Maximum scroll attempts to find new posts before stopping.",
    )

    # Interaction & Budget Limits
    max_interactions: int = Field(
        default=10,
        description="Maximum successful interactions allowed for this run.",
    )
    allowed_actions: List[ActionType] = Field(
        default_factory=lambda: ["like", "comment", "reply"],
        description="Permitted interaction actions.",
    )
    deep_dive_enabled: bool = Field(
        default=True,
        description="Whether to explore and interact with comments inside interesting posts.",
    )
    max_inner_interactions: int = Field(
        default=10,
        description="Maximum interactions to perform inside a single post's comments thread.",
    )

    # Runtime & Resilience
    max_retries: int = Field(
        default=2,
        description="Maximum retry attempts per failed post interaction.",
    )
    run_timeout_seconds: int = Field(
        default=1800,
        description="Total allowed execution time before timeout stop.",
    )
    headless: bool = Field(
        default=False,
        description="Whether to run Playwright in headless mode.",
    )
    user_data_dir: str = Field(
        default="./browser_data/x_profile",
        description="Directory for persistent browser context and cookies.",
    )
    database_path: str = Field(
        default="./data/interactions.db",
        description="Path to SQLite persistent database file.",
    )
    chatgpt_user_data_dir: str = Field(
        default="./browser_data/chatgpt_profile",
        description="Directory for persistent ChatGPT browser session profile.",
    )

    # AI Planner Settings
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Gemini API Key for AI decision making.",
    )
    llm_model: str = Field(
        default="gemini-2.5-flash-lite",
        # default="gemini-3.6-flash",
        description="LLM model name to use for planning.",
    )

    # User Profile & Strategy
    user_profile: str = Field(
        default=(
            "Full-stack developer with 1 year and 8 months of experience. "
            "Works with React, Next.js, Node.js, Python, TypeScript, and modern web tech. "
            "Passionate about early-stage startups, indie products, tech job openings, and connecting casually with fellow devs."
        ),
        description="Persona and background info given to planner.",
    )
    interaction_goal: str = Field(
        default=(
            "Engage casually and organically with new startups, dev launches, tech openings, and developer takes. "
            "Drop short, friendly comments, leave random likes on cool projects, and build genuine connections."
        ),
        description="Core goal directing the AI planner.",
    )
    content_restrictions: List[str] = Field(
        default_factory=lambda: [
            "Sound 100% human, casual, and authentic (no AI or corporate buzzwords).",
            "Keep replies very short (1-2 lines, under 120 characters).",
            "No generic bot praise like 'Great post' or 'Fascinating perspective'.",
            "No offensive, toxic, or controversial statements.",
        ],
        description="Strict restrictions applied to generated comments and replies.",
    )

    def ensure_directories(self) -> None:
        """Create necessary directories for browser profile and database."""
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.chatgpt_user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)


# Default singleton instance
settings = Settings()

