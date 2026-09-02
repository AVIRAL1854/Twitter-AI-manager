"""Unit tests for post normalization, parsing, and deduplication."""

import pytest
from app.extraction.deduplicator import PostDeduplicator
from app.extraction.normalizer import PostNormalizer
from app.models.post import Author, NormalizedPost, RawPostData


class TestPostNormalizer:
    """Test suite for PostNormalizer methods."""

    def test_parse_count_various_formats(self):
        assert PostNormalizer.parse_count("0") == 0
        assert PostNormalizer.parse_count("42") == 42
        assert PostNormalizer.parse_count("1,500") == 1500
        assert PostNormalizer.parse_count("1.2K") == 1200
        assert PostNormalizer.parse_count("3.5M") == 3500000
        assert PostNormalizer.parse_count("2B") == 2000000000
        assert PostNormalizer.parse_count("42 Likes. Like") == 42
        assert PostNormalizer.parse_count("1.2K Retweets") == 1200
        assert PostNormalizer.parse_count(None) == 0
        assert PostNormalizer.parse_count("") == 0
        assert PostNormalizer.parse_count("invalid") == 0

    def test_clean_text(self):
        assert PostNormalizer.clean_text("   hello world   ") == "hello world"
        assert PostNormalizer.clean_text("line 1\r\nline 2") == "line 1\nline 2"
        assert PostNormalizer.clean_text("line 1\n\n\n\nline 2") == "line 1\n\nline 2"
        assert PostNormalizer.clean_text(None) == ""
        assert PostNormalizer.clean_text("") == ""

    def test_normalize_username(self):
        assert PostNormalizer.normalize_username("builder") == "@builder"
        assert PostNormalizer.normalize_username("@builder") == "@builder"
        assert PostNormalizer.normalize_username("  @builder  ") == "@builder"
        assert PostNormalizer.normalize_username(None) == "@unknown"
        assert PostNormalizer.normalize_username("") == "@unknown"

    def test_normalize_valid_raw_post(self):
        raw = RawPostData(
            post_id="123456789",
            url="https://x.com/alice/status/123456789",
            author_name="Alice Tech",
            author_username="alice_tech",
            text="Building AI agents with Python and Playwright!",
            timestamp="2026-09-01T12:00:00Z",
            likes_str="1.5K Likes",
            replies_str="45",
            reposts_str="120",
            is_reply=False,
            is_repost=False,
        )
        post = PostNormalizer.normalize(raw)
        assert post is not None
        assert post.post_id == "123456789"
        assert post.url == "https://x.com/alice/status/123456789"
        assert post.author.name == "Alice Tech"
        assert post.author.username == "@alice_tech"
        assert post.author_handle == "@alice_tech"
        assert post.text == "Building AI agents with Python and Playwright!"
        assert post.likes == 1500
        assert post.replies == 45
        assert post.reposts == 120
        assert post.is_reply is False

    def test_normalize_missing_post_id(self):
        raw = RawPostData(
            post_id=None,
            author_username="alice",
            text="Some tweet text",
        )
        assert PostNormalizer.normalize(raw) is None

    def test_normalize_empty_text(self):
        raw = RawPostData(
            post_id="12345",
            author_username="alice",
            text="   ",
        )
        assert PostNormalizer.normalize(raw) is None


class TestPostDeduplicator:
    """Test suite for PostDeduplicator."""

    def test_batch_and_session_deduplication(self, sample_normalized_posts):
        dedup = PostDeduplicator()
        assert dedup.seen_count == 0

        # First batch has 3 unique posts + 1 duplicate of post_101
        batch_1 = sample_normalized_posts + [sample_normalized_posts[0]]
        result_1 = dedup.deduplicate(batch_1)
        assert len(result_1) == 3
        assert dedup.seen_count == 3
        assert dedup.is_seen("post_101") is True

        # Second batch receives post_101 again and a new post_104
        post_104 = NormalizedPost(
            post_id="post_104",
            url="https://x.com/new/status/104",
            author=Author(name="New User", username="@new_user"),
            text="Another exciting post!",
        )
        batch_2 = [sample_normalized_posts[0], post_104]
        result_2 = dedup.deduplicate(batch_2)
        assert len(result_2) == 1
        assert result_2[0].post_id == "post_104"
        assert dedup.seen_count == 4

        # Reset
        dedup.reset()
        assert dedup.seen_count == 0

