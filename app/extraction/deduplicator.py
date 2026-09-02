"""Post deduplication tracking seen post IDs across batches and run session."""

from typing import List, Set
from app.models.post import NormalizedPost
from app.observability.logging import get_logger

logger = get_logger("extraction.deduplicator")


class PostDeduplicator:
    """Manages deduplication of posts within a batch and across runtime session."""

    def __init__(self) -> None:
        self._seen_post_ids: Set[str] = set()

    @property
    def seen_count(self) -> int:
        """Total unique posts seen during session."""
        return len(self._seen_post_ids)

    def is_seen(self, post_id: str) -> bool:
        """Check if post_id was previously seen in this session."""
        return post_id in self._seen_post_ids

    def mark_seen(self, post_id: str) -> None:
        """Mark a post_id as seen."""
        self._seen_post_ids.add(post_id)

    def deduplicate(self, posts: List[NormalizedPost]) -> List[NormalizedPost]:
        """Filter out duplicates from a list of posts, retaining only new unique posts."""
        unique_posts: List[NormalizedPost] = []
        batch_seen: Set[str] = set()

        for post in posts:
            if post.post_id in self._seen_post_ids or post.post_id in batch_seen:
                continue

            batch_seen.add(post.post_id)
            self._seen_post_ids.add(post.post_id)
            unique_posts.append(post)

        if len(posts) != len(unique_posts):
            logger.debug(
                f"Deduplicated {len(posts)} posts -> {len(unique_posts)} unique new posts."
            )

        return unique_posts

    def reset(self) -> None:
        """Reset seen cache."""
        self._seen_post_ids.clear()

