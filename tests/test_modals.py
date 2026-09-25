"""Unit tests for X Views modal dismissal and ignoring sidebar widgets."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.browser.executor import ActionExecutor
from app.browser.modals import dismiss_views_modal


class TestViewsModal:
    """Test suite for detecting and dismissing ONLY the 'Views' sheet, ignoring other widgets."""

    @pytest.mark.asyncio
    async def test_dismiss_views_modal_via_cross_button(self):
        page = MagicMock()

        # Composer not present
        composer_loc = MagicMock()
        composer_loc.count = AsyncMock(return_value=0)

        # Views dialog with text "Times this post was seen"
        views_dialog = MagicMock()
        views_dialog.count = AsyncMock(return_value=1)
        views_dialog.is_visible = AsyncMock(return_value=True)

        # Cross button inside views dialog
        close_btn = MagicMock()
        close_btn.count = AsyncMock(return_value=1)
        close_btn.is_visible = AsyncMock(return_value=True)
        close_btn.click = AsyncMock()
        close_btn.first = close_btn

        views_dialog.locator = MagicMock(return_value=close_btn)

        # Empty fallback locator
        empty_loc = MagicMock()
        empty_loc.count = AsyncMock(return_value=0)
        empty_loc.is_visible = AsyncMock(return_value=False)
        empty_loc.first = empty_loc

        # Filter router: if filtering for "Times this post was seen", return views_dialog
        filter_mock = MagicMock()
        def filter_side_effect(**kwargs):
            if kwargs.get("has_text") == "Times this post was seen":
                res = MagicMock()
                res.first = views_dialog
                return res
            res = MagicMock()
            res.first = empty_loc
            return res

        filter_mock.filter.side_effect = filter_side_effect

        def locator_router(selector):
            if selector == '[data-testid="tweetTextarea_0"]':
                return composer_loc
            if "role=\"dialog\"" in selector:
                return filter_mock
            return empty_loc

        page.locator.side_effect = locator_router

        dismissed = await dismiss_views_modal(page)

        assert dismissed is True
        close_btn.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_strictly_ignore_todays_news_card(self):
        """Ensure 'Today's News' sidebar card is NEVER dismissed."""
        page = MagicMock()

        composer_loc = MagicMock()
        composer_loc.count = AsyncMock(return_value=0)

        empty_dialog = MagicMock()
        empty_dialog.count = AsyncMock(return_value=0)
        empty_dialog.is_visible = AsyncMock(return_value=False)
        empty_dialog.first = empty_dialog

        filter_mock = MagicMock()
        filter_mock.filter.return_value = filter_mock
        filter_mock.first = empty_dialog

        def locator_router(selector):
            if selector == '[data-testid="tweetTextarea_0"]':
                return composer_loc
            if "role=\"dialog\"" in selector:
                return filter_mock
            return empty_dialog

        page.locator.side_effect = locator_router

        dismissed = await dismiss_views_modal(page)

        # Must return False and not click anything
        assert dismissed is False

    @pytest.mark.asyncio
    async def test_dismiss_views_modal_via_dismiss_button_fallback(self):
        page = MagicMock()

        composer_loc = MagicMock()
        composer_loc.count = AsyncMock(return_value=0)

        views_dialog = MagicMock()
        views_dialog.count = AsyncMock(return_value=1)
        views_dialog.is_visible = AsyncMock(return_value=True)

        # Cross button not visible, dismiss button visible
        close_btn = MagicMock()
        close_btn.count = AsyncMock(return_value=0)
        close_btn.first = close_btn

        dismiss_btn = MagicMock()
        dismiss_btn.count = AsyncMock(return_value=1)
        dismiss_btn.is_visible = AsyncMock(return_value=True)
        dismiss_btn.click = AsyncMock()
        dismiss_btn.first = dismiss_btn

        def dialog_locator_router(selector):
            if "Dismiss" in selector:
                return dismiss_btn
            return close_btn

        views_dialog.locator.side_effect = dialog_locator_router

        filter_mock = MagicMock()
        filter_mock.filter.side_effect = lambda **kwargs: MagicMock(first=views_dialog)

        def locator_router(selector):
            if selector == '[data-testid="tweetTextarea_0"]':
                return composer_loc
            if "role=\"dialog\"" in selector:
                return filter_mock
            mock_empty = MagicMock(count=AsyncMock(return_value=0), first=MagicMock())
            return mock_empty

        page.locator.side_effect = locator_router

        dismissed = await dismiss_views_modal(page)

        assert dismissed is True
        dismiss_btn.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_do_not_dismiss_when_composer_active(self):
        page = MagicMock()

        # Active reply composer
        composer_loc = MagicMock()
        composer_loc.count = AsyncMock(return_value=1)

        page.locator.return_value = composer_loc

        dismissed = await dismiss_views_modal(page)

        assert dismissed is False

    @pytest.mark.asyncio
    async def test_safe_click_recovers_when_views_modal_intercepts(self):
        page = MagicMock()
        executor = ActionExecutor(page)

        target_locator = MagicMock()
        target_locator.click = AsyncMock(
            side_effect=[
                Exception("<div data-testid='mask'> intercepts pointer events"),
                None,
            ]
        )

        with patch("app.browser.executor.dismiss_x_modals", new=AsyncMock(return_value=True)) as mock_dismiss:
            await executor._safe_click(target_locator, description="reply button")

            assert mock_dismiss.await_count >= 2
            assert target_locator.click.await_count == 2
