"""Unit tests for persistent SQLite interaction memory repository."""

import pytest
from app.memory.models import InteractionRecord
from app.memory.repository import InteractionRepository


@pytest.mark.asyncio
class TestInteractionRepository:
    """Test suite for SQLite repository operations."""

    async def test_save_and_check_interaction(self, test_repo):
        post_id = "post_999"
        assert await test_repo.is_post_interacted(post_id) is False

        # Save successful interaction
        record = InteractionRecord(
            run_id="run_1",
            post_id=post_id,
            post_url=f"https://x.com/status/{post_id}",
            author_username="@user",
            action="like",
            status="success",
        )
        await test_repo.save_interaction(record)

        assert await test_repo.is_post_interacted(post_id) is True

    async def test_filter_interacted_batch(self, test_repo):
        # Save two interactions
        await test_repo.save_interaction(
            InteractionRecord(
                run_id="run_1",
                post_id="p1",
                post_url="https://x.com/status/p1",
                author_username="@u1",
                action="like",
                status="success",
            )
        )
        await test_repo.save_interaction(
            InteractionRecord(
                run_id="run_1",
                post_id="p2",
                post_url="https://x.com/status/p2",
                author_username="@u2",
                action="comment",
                content="test",
                status="failed",  # failed interaction should not block re-attempt
            )
        )

        batch = ["p1", "p2", "p3"]
        interacted = await test_repo.filter_interacted_post_ids(batch)

        assert "p1" in interacted
        assert "p2" not in interacted  # because p2 status was 'failed'
        assert "p3" not in interacted

    async def test_get_recent_and_run_history(self, test_repo):
        run_id = "run_abc"
        for i in range(5):
            await test_repo.save_interaction(
                InteractionRecord(
                    run_id=run_id,
                    post_id=f"post_{i}",
                    post_url=f"https://x.com/status/post_{i}",
                    author_username=f"@user_{i}",
                    action="like",
                    status="success",
                )
            )

        recent = await test_repo.get_recent_interactions(limit=3)
        assert len(recent) == 3

        run_history = await test_repo.get_run_history(run_id)
        assert len(run_history) == 5

