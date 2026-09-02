"""Run service orchestrating the full discover -> extract -> normalize -> plan -> validate -> execute -> remember pipeline."""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.browser.executor import ActionExecutor
from app.browser.navigator import BrowserNavigator
from app.browser.scraper import BrowserScraper
from app.browser.session import BrowserSessionManager
from app.config import Settings
from app.extraction.deduplicator import PostDeduplicator
from app.memory.models import InteractionRecord
from app.memory.repository import InteractionRepository
from app.models.action import ValidatedAction
from app.models.post import NormalizedPost
from app.models.result import ExecutionResult
from app.models.run_state import RunMetrics, RunState
from app.observability.logging import get_logger
from app.planner.planner import AIPlanner, BasePlanner, MockPlanner
from app.validation.action_validator import ActionValidator

logger = get_logger("services.run")


class RunService:
    """Orchestrates an end-to-end X interaction session."""

    def __init__(
        self,
        settings: Settings,
        planner: Optional[BasePlanner] = None,
        repository: Optional[InteractionRepository] = None,
        dry_run: bool = False,
    ):
        self.settings = settings
        self.dry_run = dry_run
        self.run_id = str(uuid.uuid4())

        self.repository = repository or InteractionRepository(settings.database_path)
        self.deduplicator = PostDeduplicator()
        self.validator = ActionValidator(settings)
        self.planner = planner or (
            MockPlanner(settings)
            if not settings.gemini_api_key
            else AIPlanner(settings)
        )

        self.run_state = RunState(
            run_id=self.run_id,
            metrics=RunMetrics(interactions_remaining=settings.max_interactions),
        )

    async def run(self) -> RunState:
        """Execute the complete interaction workflow."""
        start_time = time.monotonic()
        logger.info(f"=== Starting Run [{self.run_id[:8]}] (Max Interactions: {self.settings.max_interactions}, Dry Run: {self.dry_run}) ===")

        # Ensure folders and initialize DB
        self.settings.ensure_directories()
        await self.repository.initialize()

        session_mgr = BrowserSessionManager(self.settings)

        try:
            async with session_mgr as page:
                navigator = BrowserNavigator(page)
                scraper = BrowserScraper(page)
                executor = ActionExecutor(page)

                # 1. Navigate to target page
                await navigator.navigate_to(self.settings.target_page)
                has_posts = await navigator.wait_for_posts(timeout_ms=10000)
                if not has_posts:
                    logger.warning("No tweet posts appeared after initial page load. Checking login status...")
                    is_logged_in = await navigator.check_login_state()
                    if not is_logged_in:
                        logger.warning(
                            "User may need to log in to X. Run with persistent profile and headless=False to log in manually once."
                        )

                consecutive_empty_scrolls = 0

                # 2. Main Runtime Loop
                while True:
                    # Check stop conditions: timeout
                    elapsed_seconds = time.monotonic() - start_time
                    if elapsed_seconds > self.settings.run_timeout_seconds:
                        logger.info("Run timeout reached. Stopping.")
                        self.run_state.status = "timeout"
                        break

                    # Check stop conditions: budget
                    remaining_budget = (
                        self.settings.max_interactions
                        - self.run_state.metrics.actions_succeeded
                    )
                    self.run_state.metrics.interactions_remaining = max(0, remaining_budget)
                    if remaining_budget <= 0:
                        logger.info(
                            f"Interaction budget exhausted ({self.run_state.metrics.actions_succeeded}/{self.settings.max_interactions} actions completed). Stopping."
                        )
                        self.run_state.status = "budget_exhausted"
                        break

                    # Check stop conditions: scroll limit
                    if self.run_state.metrics.scroll_count >= self.settings.max_scroll_attempts:
                        logger.info(
                            f"Max scroll attempts ({self.settings.max_scroll_attempts}) reached. Stopping."
                        )
                        self.run_state.status = "max_scroll_reached"
                        break

                    # Step A: Scrape visible posts
                    scraped_posts = await scraper.scrape_visible_posts(
                        limit=self.settings.posts_per_batch
                    )
                    self.run_state.metrics.posts_discovered += len(scraped_posts)

                    # Step B: Normalize & Deduplicate against session seen
                    new_posts = self.deduplicator.deduplicate(scraped_posts)

                    # Step C: Filter out posts already in DB history
                    post_ids = [p.post_id for p in new_posts]
                    interacted_ids = await self.repository.filter_interacted_post_ids(post_ids)
                    eligible_posts = [p for p in new_posts if p.post_id not in interacted_ids]

                    self.run_state.metrics.posts_eligible += len(eligible_posts)
                    logger.info(
                        f"Batch Discovery: {len(scraped_posts)} scraped, {len(new_posts)} new, {len(eligible_posts)} eligible."
                    )

                    if eligible_posts:
                        consecutive_empty_scrolls = 0
                        batch_to_plan = eligible_posts[: self.settings.posts_per_batch]
                        self.run_state.metrics.posts_sent_to_planner += len(batch_to_plan)

                        # Step D: Load recent interaction history for context
                        recent_history = await self.repository.get_recent_interactions(limit=10)

                        # Step E: AI Planner
                        action_plan = await self.planner.plan(
                            posts=batch_to_plan,
                            remaining_budget=remaining_budget,
                            recent_history=recent_history,
                        )
                        self.run_state.metrics.actions_proposed += len(action_plan.actions)

                        # Step F: Validation Layer
                        approved_actions = self.validator.validate_plan(
                            plan=action_plan,
                            known_posts=batch_to_plan,
                            interacted_post_ids=interacted_ids,
                            remaining_budget=remaining_budget,
                        )
                        self.run_state.metrics.actions_approved += len(approved_actions)

                        # Step G: Execution Layer & Persistent Memory
                        for approved_action in approved_actions:
                            if (
                                self.run_state.metrics.actions_succeeded
                                >= self.settings.max_interactions
                            ):
                                logger.info("Max interaction budget reached mid-batch. Halting execution.")
                                break

                            self.run_state.metrics.actions_executed += 1

                            if self.dry_run:
                                logger.info(
                                    f"[DRY-RUN] Simulating {approved_action.action} on post {approved_action.post_id}"
                                )
                                result = ExecutionResult(
                                    post_id=approved_action.post_id,
                                    action=approved_action.action,
                                    status="success",
                                )
                            else:
                                result = await executor.execute(approved_action)

                            # Record in DB
                            record = InteractionRecord(
                                run_id=self.run_id,
                                post_id=approved_action.post_id,
                                post_url=approved_action.post_url,
                                author_username=approved_action.author_username,
                                action=approved_action.action,
                                content=approved_action.content,
                                status=result.status,
                                error=result.error,
                            )
                            await self.repository.save_interaction(record)

                            if result.is_success:
                                self.run_state.metrics.actions_succeeded += 1
                            else:
                                self.run_state.metrics.actions_failed += 1

                            # Check for Deep Dive into post thread comments
                            if (
                                approved_action.explore_thread
                                and self.settings.deep_dive_enabled
                                and self.run_state.metrics.actions_succeeded < self.settings.max_interactions
                            ):
                                parent_post = next((p for p in batch_to_plan if p.post_id == approved_action.post_id), None)
                                if parent_post:
                                    await self._execute_deep_dive(
                                        parent_action=approved_action,
                                        parent_post=parent_post,
                                        navigator=navigator,
                                        scraper=scraper,
                                        executor=executor,
                                    )

                            # Brief pause between browser interactions
                            await asyncio.sleep(1.5)
                    else:
                        consecutive_empty_scrolls += 1
                        logger.debug(f"Consecutive empty scrolls: {consecutive_empty_scrolls}")
                        if consecutive_empty_scrolls >= 3:
                            logger.info("No new posts discovered after 3 consecutive scrolls. Stopping.")
                            self.run_state.status = "no_posts_found"
                            break

                    # Step H: Scroll to discover more posts
                    await navigator.scroll_down(step_px=800, delay_seconds=2.5)
                    self.run_state.metrics.scroll_count += 1

            if self.run_state.status == "initialized":
                self.run_state.status = "completed"

        except Exception as e:
            logger.error(f"Fatal error during run execution: {e}")
            self.run_state.status = "error"
            self.run_state.error = str(e)

        finally:
            self.run_state.end_time = datetime.now(timezone.utc)
            self.run_state.metrics.run_duration_seconds = time.monotonic() - start_time
            logger.info(
                f"=== Run Finished [{self.run_id[:8]}] - Status: {self.run_state.status.upper()} | "
                f"Succeeded: {self.run_state.metrics.actions_succeeded}/{self.settings.max_interactions} | "
                f"Deep Dives: {self.run_state.metrics.deep_dives_performed} ({self.run_state.metrics.inner_interactions_executed} inner interactions) | "
                f"Duration: {self.run_state.metrics.run_duration_seconds:.1f}s ==="
            )

        return self.run_state

    async def _execute_deep_dive(
        self,
        parent_action: ValidatedAction,
        parent_post: NormalizedPost,
        navigator: BrowserNavigator,
        scraper: BrowserScraper,
        executor: ActionExecutor,
    ) -> None:
        """Deep dive inside a high-interest post to explore and interact with comments in its thread."""
        remaining_global = self.settings.max_interactions - self.run_state.metrics.actions_succeeded
        if remaining_global <= 0:
            return

        inner_budget = min(self.settings.max_inner_interactions, remaining_global)
        if inner_budget <= 0:
            return

        logger.info(
            f"[Deep Dive] Exploring thread comments for post {parent_post.post_id} "
            f"(Inner limit: {self.settings.max_inner_interactions}, Available: {inner_budget})..."
        )
        self.run_state.metrics.deep_dives_performed += 1

        try:
            if not self.dry_run:
                # Navigate into the post URL
                await navigator.navigate_to(parent_post.url)
                await navigator.wait_for_posts(timeout_ms=10000)

            # Scrape thread comments
            if self.dry_run:
                from app.models.post import Author
                thread_posts = [
                    NormalizedPost(
                        post_id=f"reply_{parent_post.post_id}_{i}",
                        url=f"https://x.com/user{i}/status/reply_{parent_post.post_id}_{i}",
                        author=Author(name=f"Dev {i}", username=f"dev_{i}"),
                        text=f"Interesting perspective on {parent_post.text[:30]}",
                        is_reply=True,
                    )
                    for i in range(1, 4)
                ]
            else:
                thread_posts = await scraper.scrape_visible_posts(limit=15)

            # Filter out the parent post itself
            reply_posts = [p for p in thread_posts if p.post_id != parent_post.post_id]
            new_replies = self.deduplicator.deduplicate(reply_posts)

            reply_ids = [p.post_id for p in new_replies]
            interacted_reply_ids = await self.repository.filter_interacted_post_ids(reply_ids)
            eligible_replies = [p for p in new_replies if p.post_id not in interacted_reply_ids]

            logger.info(
                f"[Deep Dive] Found {len(eligible_replies)} eligible thread comments in post {parent_post.post_id}."
            )

            if eligible_replies:
                recent_history = await self.repository.get_recent_interactions(limit=6)

                # Plan interactions for thread comments
                inner_plan = await self.planner.plan(
                    posts=eligible_replies[:inner_budget],
                    remaining_budget=inner_budget,
                    recent_history=recent_history,
                )

                # Validate inner plan
                approved_inner = self.validator.validate_plan(
                    plan=inner_plan,
                    known_posts=eligible_replies,
                    interacted_post_ids=interacted_reply_ids,
                    remaining_budget=inner_budget,
                )

                # Execute inner interactions
                inner_executed = 0
                for inner_action in approved_inner:
                    if (
                        self.run_state.metrics.actions_succeeded
                        >= self.settings.max_interactions
                        or inner_executed >= self.settings.max_inner_interactions
                    ):
                        logger.info(
                            f"[Deep Dive] Inner interaction limit ({self.settings.max_inner_interactions}) or budget reached."
                        )
                        break

                    self.run_state.metrics.actions_executed += 1
                    inner_executed += 1

                    if self.dry_run:
                        logger.info(
                            f"[DRY-RUN Deep Dive] Simulating {inner_action.action} on comment {inner_action.post_id}"
                        )
                        result = ExecutionResult(
                            post_id=inner_action.post_id,
                            action=inner_action.action,
                            status="success",
                        )
                    else:
                        result = await executor.execute(inner_action)

                    record = InteractionRecord(
                        run_id=self.run_id,
                        post_id=inner_action.post_id,
                        post_url=inner_action.post_url,
                        author_username=inner_action.author_username,
                        action=inner_action.action,
                        content=inner_action.content,
                        status=result.status,
                        error=result.error,
                    )
                    await self.repository.save_interaction(record)

                    if result.is_success:
                        self.run_state.metrics.actions_succeeded += 1
                        self.run_state.metrics.inner_interactions_executed += 1
                    else:
                        self.run_state.metrics.actions_failed += 1

                    await asyncio.sleep(1.5)

                logger.info(
                    f"[Deep Dive] Completed {inner_executed} thread interactions inside post {parent_post.post_id}."
                )

        except Exception as e:
            logger.warning(f"[Deep Dive] Thread exploration encountered error: {e}")

        finally:
            # Crucial: return back to the main feed / target page
            if not self.dry_run:
                logger.info("Returning back to main feed after deep dive...")
                await navigator.navigate_to(self.settings.target_page)
                await navigator.wait_for_posts(timeout_ms=10000)
