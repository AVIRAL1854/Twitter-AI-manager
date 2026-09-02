"""Shared pytest fixtures."""

import os
import tempfile
import pytest
from app.config import Settings
from app.memory.repository import InteractionRepository
from app.models.post import Author, NormalizedPost, RawPostData


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary SQLite database file path."""
    return str(tmp_path / "test_interactions.db")


@pytest.fixture
def test_settings(temp_db_path):
    """Provide standard test settings."""
    return Settings(
        target_page="https://x.com/home",
        max_interactions=5,
        allowed_actions=["like", "comment", "reply"],
        posts_per_batch=10,
        max_scroll_attempts=3,
        run_timeout_seconds=30,
        database_path=temp_db_path,
        user_data_dir=str(temp_db_path + "_profile"),
        headless=True,
    )


@pytest.fixture
async def test_repo(temp_db_path):
    """Provide an initialized InteractionRepository instance."""
    repo = InteractionRepository(temp_db_path)
    await repo.initialize()
    return repo


@pytest.fixture
def sample_normalized_posts():
    """Provide a list of sample normalized posts."""
    return [
        NormalizedPost(
            post_id="post_101",
            url="https://x.com/tech_builder/status/101",
            author=Author(name="Tech Builder", username="@tech_builder"),
            text="Autonomous AI agents are transforming how we write and test software. Built a new prototype today!",
            likes=150,
            replies=12,
            reposts=8,
        ),
        NormalizedPost(
            post_id="post_102",
            url="https://x.com/dev_guru/status/102",
            author=Author(name="Dev Guru", username="@dev_guru"),
            text="Just had lunch. Nice weather outside.",
            likes=5,
            replies=0,
            reposts=0,
        ),
        NormalizedPost(
            post_id="post_103",
            url="https://x.com/ai_researcher/status/103",
            author=Author(name="AI Researcher", username="@ai_researcher"),
            text="Our new paper on multi-agent consensus mechanisms for LLMs is finally out! Read here.",
            likes=420,
            replies=35,
            reposts=80,
        ),
    ]

