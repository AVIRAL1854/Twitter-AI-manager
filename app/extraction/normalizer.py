"""Post normalizer cleaning whitespace, standardizing formats, and validating post models."""

import re
from typing import Optional
from app.models.post import Author, NormalizedPost, RawPostData
from app.observability.logging import get_logger

logger = get_logger("extraction.normalizer")

COUNT_REGEX = re.compile(r"([\d,]+(?:\.\d+)?)\s*([KMBkmb])?")


class PostNormalizer:
    """Normalizes raw extracted post data into structured, clean NormalizedPost objects."""

    @classmethod
    def parse_count(cls, count_str: Optional[str]) -> int:
        """Parse metric strings like '1.2K', '3.4M', '42 Likes' into integer."""
        if not count_str:
            return 0

        # Remove extra text from aria labels like "42 Likes. Like" or "1,200 Retweets"
        match = COUNT_REGEX.search(count_str)
        if not match:
            return 0

        num_str = match.group(1).replace(",", "")
        multiplier_str = match.group(2)

        try:
            val = float(num_str)
            if multiplier_str:
                unit = multiplier_str.upper()
                if unit == "K":
                    val *= 1_000
                elif unit == "M":
                    val *= 1_000_000
                elif unit == "B":
                    val *= 1_000_000_000
            return int(val)
        except (ValueError, TypeError):
            return 0

    @classmethod
    def clean_text(cls, text: Optional[str]) -> str:
        """Clean excessive whitespace and normalize line breaks."""
        if not text:
            return ""
        # Normalize carriage returns and excessive whitespace
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Replace 3 or more consecutive newlines with 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip outer whitespace
        return text.strip()

    @classmethod
    def normalize_username(cls, username: Optional[str]) -> str:
        """Standardize username handle to @handle."""
        if not username:
            return "@unknown"
        username = username.strip()
        if not username.startswith("@"):
            username = f"@{username}"
        return username

    @classmethod
    def normalize(cls, raw: RawPostData) -> Optional[NormalizedPost]:
        """Convert RawPostData into NormalizedPost, or return None if invalid."""
        if not raw.post_id or not raw.post_id.strip():
            logger.debug("Skipping post with missing post_id.")
            return None

        clean_text = cls.clean_text(raw.text)
        if not clean_text:
            logger.debug(f"Skipping post {raw.post_id} due to empty text content.")
            return None

        author_username = cls.normalize_username(raw.author_username)
        author_name = cls.clean_text(raw.author_name) or author_username

        url = raw.url or f"https://x.com/i/status/{raw.post_id}"

        likes = cls.parse_count(raw.likes_str)
        replies = cls.parse_count(raw.replies_str)
        reposts = cls.parse_count(raw.reposts_str)

        return NormalizedPost(
            post_id=raw.post_id.strip(),
            url=url,
            author=Author(name=author_name, username=author_username),
            text=clean_text,
            timestamp=raw.timestamp,
            likes=likes,
            replies=replies,
            reposts=reposts,
            is_reply=raw.is_reply,
            is_repost=raw.is_repost,
        )

