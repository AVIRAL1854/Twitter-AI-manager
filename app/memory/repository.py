"""Async SQLite repository for persistent interaction history."""

from pathlib import Path
from typing import List, Optional, Set
import aiosqlite

from app.memory.models import InteractionRecord
from app.observability.logging import PersistenceError, get_logger

logger = get_logger("memory.repository")

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    post_url TEXT NOT NULL,
    author_username TEXT NOT NULL,
    action TEXT NOT NULL,
    content TEXT,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_interactions_post_id ON interactions(post_id);
CREATE INDEX IF NOT EXISTS idx_interactions_run_id ON interactions(run_id);
CREATE INDEX IF NOT EXISTS idx_interactions_author ON interactions(author_username);
CREATE INDEX IF NOT EXISTS idx_interactions_status ON interactions(status);
"""


class InteractionRepository:
    """Repository managing persistent interaction memory in SQLite."""

    def __init__(self, db_path: str = "./data/interactions.db"):
        self.db_path = db_path
        self._ensure_db_dir()

    def _ensure_db_dir(self) -> None:
        """Create parent directory for database file."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        """Initialize database schema and indexes."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(CREATE_TABLES_SQL)
                await db.commit()
            logger.debug(f"Initialized SQLite database at {self.db_path}")
        except Exception as e:
            raise PersistenceError(f"Failed to initialize database at {self.db_path}: {e}") from e

    async def is_post_interacted(self, post_id: str) -> bool:
        """Check if a post has already been interacted with (excluding skipped)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT 1 FROM interactions WHERE post_id = ? AND status = 'success' LIMIT 1",
                    (post_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    return row is not None
        except Exception as e:
            raise PersistenceError(f"Failed checking interaction status for post {post_id}: {e}") from e

    async def filter_interacted_post_ids(self, post_ids: List[str]) -> Set[str]:
        """Return the subset of post_ids that already have a successful interaction."""
        if not post_ids:
            return set()
        try:
            placeholders = ",".join("?" * len(post_ids))
            query = f"""
                SELECT DISTINCT post_id FROM interactions 
                WHERE post_id IN ({placeholders}) AND status = 'success'
            """
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(query, post_ids) as cursor:
                    rows = await cursor.fetchall()
                    return {row[0] for row in rows}
        except Exception as e:
            raise PersistenceError(f"Failed checking batch interaction history: {e}") from e

    async def save_interaction(self, record: InteractionRecord) -> None:
        """Save an interaction result to the database."""
        try:
            insert_sql = """
                INSERT OR REPLACE INTO interactions (
                    interaction_id, run_id, post_id, post_url, author_username,
                    action, content, status, timestamp, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(insert_sql, record.to_row())
                await db.commit()
            logger.debug(
                f"Saved interaction record: {record.action} on post {record.post_id} ({record.status})"
            )
        except Exception as e:
            raise PersistenceError(
                f"Failed saving interaction record for post {record.post_id}: {e}"
            ) from e

    async def get_recent_interactions(self, limit: int = 20) -> List[InteractionRecord]:
        """Retrieve recent interaction records for planner context."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM interactions ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [InteractionRecord.from_row(row) for row in rows]
        except Exception as e:
            raise PersistenceError(f"Failed loading recent interactions: {e}") from e

    async def get_run_history(self, run_id: str) -> List[InteractionRecord]:
        """Retrieve all interaction records for a specific run."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM interactions WHERE run_id = ? ORDER BY timestamp ASC",
                    (run_id,),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [InteractionRecord.from_row(row) for row in rows]
        except Exception as e:
            raise PersistenceError(f"Failed loading history for run {run_id}: {e}") from e

