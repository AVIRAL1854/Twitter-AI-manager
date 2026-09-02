"""Post models representing raw, parsed, and normalized posts."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class Author(BaseModel):
    """Author metadata for a post."""

    name: str = ""
    username: str  # e.g. "@username" or "username"


class PostMetadata(BaseModel):
    """Engagement metrics for a post."""

    likes: int = 0
    replies: int = 0
    reposts: int = 0
    views: Optional[int] = None


class RawPostData(BaseModel):
    """Raw post data directly scraped from DOM elements."""

    post_id: Optional[str] = None
    url: Optional[str] = None
    author_name: Optional[str] = None
    author_username: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[str] = None
    likes_str: Optional[str] = None
    replies_str: Optional[str] = None
    reposts_str: Optional[str] = None
    is_reply: bool = False
    is_repost: bool = False


class NormalizedPost(BaseModel):
    """Clean, normalized, and validated post object ready for planning."""

    post_id: str
    url: str
    author: Author
    text: str
    timestamp: Optional[str] = None
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    is_reply: bool = False
    is_repost: bool = False
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def author_handle(self) -> str:
        """Ensure username is prefixed with @."""
        return f"@{self.author.username.lstrip('@')}"

    def to_planner_dict(self) -> dict:
        """Compact dictionary representation formatted to minimize AI Planner token usage."""
        return {
            "id": self.post_id,
            "by": self.author_handle,
            "text": self.text[:280].strip(),
        }

