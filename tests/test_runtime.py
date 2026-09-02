"""End-to-end runtime integration tests for RunService orchestration."""

import pytest
from unittest.mock import AsyncMock, patch
from app.config import Settings
from app.memory.repository import InteractionRepository
from app.models.post import Author, NormalizedPost
from app.planner.planner import MockPlanner
from app.services.run_service import RunService


@pytest.mark.asyncio
class TestRunServiceIntegration:
    """Integration test suite for the complete RunService execution loop."""

    @patch("app.browser.session.BrowserSessionManager.start")
    @patch("app.browser.session.BrowserSessionManager.close")
    @patch("app.browser.navigator.BrowserNavigator.navigate_to")
    @patch("app.browser.navigator.BrowserNavigator.wait_for_posts")
    @patch("app.browser.navigator.BrowserNavigator.scroll_down")
    @patch("app.browser.scraper.BrowserScraper.scrape_visible_posts")
    async def test_full_run_budget_exhaustion(
        self,
        mock_scrape,
        mock_scroll,
        mock_wait_posts,
        mock_nav,
        mock_close,
        mock_start,
        test_settings,
        test_repo,
        sample_normalized_posts,
    ):
        mock_page = AsyncMock()
        mock_start.return_value = mock_page
        mock_wait_posts.return_value = True

        # Provide posts on first scrape call, then empty on subsequent
        mock_scrape.side_effect = [
            sample_normalized_posts,
            [],
            [],
            [],
            [],
        ]

        test_settings.max_interactions = 2
        planner = MockPlanner(test_settings)

        service = RunService(
            settings=test_settings,
            planner=planner,
            repository=test_repo,
            dry_run=True,
        )

        state = await service.run()

        # Check metrics and state
        assert state.status in ("budget_exhausted", "completed", "no_posts_found")
        assert state.metrics.actions_executed <= test_settings.max_interactions

        # Verify items were saved in DB repository
        history = await test_repo.get_run_history(service.run_id)
        assert len(history) == state.metrics.actions_executed
        assert all(h.status == "success" for h in history)

    @pytest.mark.asyncio
    @patch("app.browser.session.BrowserSessionManager.start")
    @patch("app.browser.session.BrowserSessionManager.close")
    @patch("app.browser.navigator.BrowserNavigator.navigate_to")
    @patch("app.browser.navigator.BrowserNavigator.wait_for_posts")
    @patch("app.browser.navigator.BrowserNavigator.scroll_down")
    @patch("app.browser.scraper.BrowserScraper.scrape_visible_posts")
    async def test_run_stops_on_no_posts_found(
        self,
        mock_scrape,
        mock_scroll,
        mock_wait_posts,
        mock_nav,
        mock_close,
        mock_start,
        test_settings,
        test_repo,
    ):
        mock_page = AsyncMock()
        mock_start.return_value = mock_page
        mock_wait_posts.return_value = False
        mock_scrape.return_value = []

        service = RunService(
            settings=test_settings,
            planner=MockPlanner(test_settings),
            repository=test_repo,
            dry_run=True,
        )

        state = await service.run()

        assert state.status == "no_posts_found"
        assert state.metrics.actions_executed == 0

    @pytest.mark.asyncio
    @patch("app.browser.session.BrowserSessionManager.start")
    @patch("app.browser.session.BrowserSessionManager.close")
    @patch("app.browser.navigator.BrowserNavigator.navigate_to")
    @patch("app.browser.navigator.BrowserNavigator.wait_for_posts")
    @patch("app.browser.navigator.BrowserNavigator.scroll_down")
    @patch("app.browser.scraper.BrowserScraper.scrape_visible_posts")
    async def test_deep_dive_inner_interactions(
        self,
        mock_scrape,
        mock_scroll,
        mock_wait_posts,
        mock_nav,
        mock_close,
        mock_start,
        test_settings,
        test_repo,
    ):
        mock_page = AsyncMock()
        mock_start.return_value = mock_page
        mock_wait_posts.return_value = True

        # Outer post with launch/startup keyword
        outer_post = NormalizedPost(
            post_id="post_startup_100",
            url="https://x.com/founder/status/post_startup_100",
            author=Author(name="Founder", username="founder"),
            text="Just launched our new developer AI startup product!",
        )

        mock_scrape.side_effect = [
            [outer_post],
            [],
            [],
            [],
        ]

        test_settings.max_interactions = 5
        test_settings.deep_dive_enabled = True
        test_settings.max_inner_interactions = 2

        service = RunService(
            settings=test_settings,
            planner=MockPlanner(test_settings),
            repository=test_repo,
            dry_run=True,
        )

        state = await service.run()

        assert state.metrics.deep_dives_performed >= 1
        assert state.metrics.actions_succeeded <= test_settings.max_interactions

