"""Database models for persistent interaction memory."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class InteractionRecord(BaseModel):
    """Database record of an interaction outcome."""

    interaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    post_id: str
    post_url: str
    author_username: str
    action: str  # like, comment, reply, skip
    content: Optional[str] = None
    status: str  # success, failed, skipped
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    def to_row(self) -> tuple:
        """Convert record to SQLite row tuple."""
        return (
            self.interaction_id,
            self.run_id,
            self.post_id,
            self.post_url,
            self.author_username,
            self.action,
            self.content,
            self.status,
            self.timestamp.isoformat(),
            self.error,
        )

    @classmethod
    def from_row(cls, row: tuple) -> "InteractionRecord":
        """Construct record from SQLite row tuple."""
        return cls(
            interaction_id=row[0],
            run_id=row[1],
            post_id=row[2],
            post_url=row[3],
            author_username=row[4],
            action=row[5],
            content=row[6],
            status=row[7],
            timestamp=datetime.fromisoformat(row[8]),
            error=row[9],
        )

