"""Browser navigator handling page transitions, element waiting, and feed scrolling."""

import asyncio
from typing import Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.observability.logging import BrowserError, get_logger

logger = get_logger("browser.navigator")


class BrowserNavigator:
    """Handles page navigation, wait states, and smooth scrolling for post discovery."""

    def __init__(self, page: Page):
        self.page = page

    async def navigate_to(self, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 30000) -> None:
        """Navigate to target URL and wait for initial render."""
        try:
            logger.info(f"Navigating to {url}...")
            await self.page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            # Give short stabilization pause
            await asyncio.sleep(2)
        except Exception as e:
            raise BrowserError(f"Navigation to {url} failed: {e}") from e

    async def wait_for_posts(self, timeout_ms: int = 15000) -> bool:
        """Wait for tweet article elements to appear on the page."""
        try:
            await self.page.wait_for_selector(
                'article[data-testid="tweet"]',
                state="attached",
                timeout=timeout_ms,
            )
            return True
        except PlaywrightTimeoutError:
            logger.warning("Timed out waiting for tweet elements to render.")
            return False
        except Exception as e:
            logger.warning(f"Error waiting for tweet elements: {e}")
            return False

    async def check_login_state(self) -> bool:
        """Check whether the user is logged into X or viewing a public/login-required page."""
        try:
            # If account switcher or home timeline header is visible, user is logged in
            logged_in_indicators = [
                '[data-testid="SideNav_AccountSwitcher_Button"]',
                '[data-testid="AppTabBar_Home_Link"]',
                '[data-testid="tweetButtonInline"]',
            ]
            for selector in logged_in_indicators:
                if await self.page.locator(selector).count() > 0:
                    return True
            return False
        except Exception:
            return False

    async def go_back(self, wait_until: str = "domcontentloaded", delay_seconds: float = 2.0) -> None:
        """Navigate back to previous page in history and wait for render."""
        try:
            logger.info("Navigating back to previous page in browser history...")
            await self.page.go_back(wait_until=wait_until)
            await asyncio.sleep(delay_seconds)
        except Exception as e:
            logger.warning(f"Browser go_back encountered error: {e}")

    async def scroll_down(self, step_px: int = 600, delay_seconds: float = 2.0) -> None:
        """Smoothly scroll down to load more posts in the infinite feed."""
        try:
            logger.debug(f"Scrolling down by {step_px}px...")
            await self.page.evaluate(f"window.scrollBy({{top: {step_px}, behavior: 'smooth'}})")
            await asyncio.sleep(delay_seconds)
        except Exception as e:
            logger.warning(f"Scroll operation encountered error: {e}")

