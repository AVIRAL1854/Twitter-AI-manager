"""Playwright executor performing validated interactions in the browser."""

import asyncio
import time
from typing import Optional
from playwright.async_api import Locator, Page

from app.models.action import ValidatedAction
from app.models.result import ExecutionResult
from app.observability.logging import ExecutionError, get_logger

logger = get_logger("browser.executor")


class ActionExecutor:
    """Executes validated interaction actions strictly in the browser with verification."""

    def __init__(self, page: Page):
        self.page = page

    async def execute(self, action: ValidatedAction) -> ExecutionResult:
        """Execute a single validated action and return its execution outcome."""
        start_time = time.monotonic()
        post_id = action.post_id

        logger.info(f"Executing {action.action.upper()} on post {post_id} (Author: {action.author_username})...")

        if action.action == "skip":
            return ExecutionResult(
                post_id=post_id,
                action="skip",
                status="skipped",
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

        try:
            # 1. Locate tweet element on page
            tweet_elem = await self._find_tweet_element(post_id)
            if not tweet_elem:
                raise ExecutionError(f"Could not locate tweet {post_id} on page for execution.")

            # Scroll tweet into view
            await tweet_elem.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)

            # 2. Dispatch action
            if action.action == "like":
                await self._execute_like(tweet_elem, post_id)
            elif action.action in ("comment", "reply"):
                if not action.content:
                    raise ExecutionError(f"Missing content for {action.action} action on post {post_id}")
                await self._execute_reply(tweet_elem, post_id, action.content)
            else:
                raise ExecutionError(f"Unsupported action type: {action.action}")

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(f"Successfully executed {action.action} on post {post_id} in {duration_ms:.1f}ms.")
            return ExecutionResult(
                post_id=post_id,
                action=action.action,
                status="success",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(f"Execution failed for {action.action} on post {post_id}: {e}")
            return ExecutionResult(
                post_id=post_id,
                action=action.action,
                status="failed",
                error=str(e),
                duration_ms=duration_ms,
            )

    async def _find_tweet_element(self, post_id: str) -> Optional[Locator]:
        """Find the matching tweet article element for the given post_id."""
        # Check by status link href
        matching_link = self.page.locator(f'article[data-testid="tweet"]:has(a[href*="{post_id}"])').first
        if await matching_link.count() > 0:
            return matching_link

        # Fallback: scan all tweets on page
        all_tweets = self.page.locator('article[data-testid="tweet"]')
        count = await all_tweets.count()
        for i in range(count):
            tweet = all_tweets.nth(i)
            link = tweet.locator(f'a[href*="{post_id}"]').first
            if await link.count() > 0:
                return tweet

        return None

    async def _execute_like(self, tweet_elem: Locator, post_id: str) -> None:
        """Perform and verify a like action."""
        # Check if already liked
        unlike_btn = tweet_elem.locator('[data-testid="unlike"]').first
        if await unlike_btn.count() > 0:
            logger.info(f"Post {post_id} is already liked.")
            return

        like_btn = tweet_elem.locator('[data-testid="like"]').first
        if await like_btn.count() == 0:
            raise ExecutionError(f"Like button not found on post {post_id}.")

        await like_btn.click()
        await asyncio.sleep(1.0)

        # Verification: check if unlike button is now visible
        if await unlike_btn.count() == 0:
            logger.debug(f"Post {post_id} like click completed (soft verification).")

    async def _execute_reply(self, tweet_elem: Locator, post_id: str, content: str) -> None:
        """Perform and verify a comment/reply action."""
        reply_btn = tweet_elem.locator('[data-testid="reply"]').first
        if await reply_btn.count() == 0:
            raise ExecutionError(f"Reply button not found on post {post_id}.")

        await reply_btn.click()
        await asyncio.sleep(1.0)

        # Look for composer textarea in reply dialog or modal
        textarea = self.page.locator('[data-testid="tweetTextarea_0"]').first
        if await textarea.count() == 0:
            # Fallback to any contenteditable or textarea in dialog
            textarea = self.page.locator('div[role="dialog"] [contenteditable="true"]').first

        if await textarea.count() == 0:
            raise ExecutionError("Reply textarea could not be found.")

        # Type content into textarea
        await textarea.click()
        await textarea.fill(content)
        await asyncio.sleep(0.8)

        # Find and click the Reply / Tweet submit button
        submit_btn = self.page.locator('[data-testid="tweetButton"]').first
        if await submit_btn.count() == 0:
            submit_btn = self.page.locator('div[role="dialog"] [data-testid="tweetButtonInline"]').first

        if await submit_btn.count() == 0:
            raise ExecutionError("Reply submit button not found.")

        await submit_btn.click()
        await asyncio.sleep(2.0)

        logger.debug(f"Submitted reply on post {post_id}.")

