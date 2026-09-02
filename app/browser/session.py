"""Browser session and context management with persistent profile support."""

from pathlib import Path
from typing import Optional
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import Settings
from app.observability.logging import BrowserError, get_logger

logger = get_logger("browser.session")


class BrowserSessionManager:
    """Manages the lifecycle of the Playwright browser, context, and page."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def page(self) -> Page:
        """Get the active page instance."""
        if not self._page:
            raise BrowserError("Browser session has not been started.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """Get the active browser context."""
        if not self._context:
            raise BrowserError("Browser context has not been started.")
        return self._context

    async def start(self) -> Page:
        """Start Playwright browser with persistent context if configured."""
        try:
            self._playwright = await async_playwright().start()
            user_data_dir = self.settings.user_data_dir

            if user_data_dir:
                Path(user_data_dir).mkdir(parents=True, exist_ok=True)
                logger.info(f"Launching persistent browser context at {user_data_dir} (headless={self.settings.headless})...")
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=self.settings.headless,
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
                pages = self._context.pages
                self._page = pages[0] if pages else await self._context.new_page()
            else:
                logger.info(f"Launching browser (headless={self.settings.headless})...")
                self._browser = await self._playwright.chromium.launch(
                    headless=self.settings.headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                )
                self._page = await self._context.new_page()

            logger.info("Browser session initialized successfully.")
            return self._page

        except Exception as e:
            raise BrowserError(f"Failed to start browser session: {e}") from e

    async def close(self) -> None:
        """Close browser, context, and Playwright session."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Browser session closed cleanly.")
        except Exception as e:
            logger.warning(f"Error during browser session shutdown: {e}")

    async def __aenter__(self) -> Page:
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

