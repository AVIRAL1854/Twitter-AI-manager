"""Scraper for discovering and extracting visible post elements from the DOM."""

from typing import List
from playwright.async_api import Page

from app.extraction.normalizer import PostNormalizer
from app.extraction.parser import PostParser
from app.models.post import NormalizedPost
from app.observability.logging import get_logger

logger = get_logger("browser.scraper")


class BrowserScraper:
    """Discovers and extracts visible tweet elements from the current browser page."""

    def __init__(self, page: Page):
        self.page = page

    async def scrape_visible_posts(self, limit: int = 20) -> List[NormalizedPost]:
        """Locate visible tweet elements on the page, parse and normalize them."""
        normalized_posts: List[NormalizedPost] = []
        try:
            tweet_locators = self.page.locator('article[data-testid="tweet"]')
            total_elements = await tweet_locators.count()
            logger.debug(f"Found {total_elements} tweet DOM elements on page.")

            # Process up to limit
            count_to_process = min(total_elements, limit)
            for i in range(count_to_process):
                locator = tweet_locators.nth(i)
                raw_data = await PostParser.extract_from_locator(locator)
                if not raw_data:
                    continue

                normalized = PostNormalizer.normalize(raw_data)
                if normalized:
                    normalized_posts.append(normalized)

            logger.info(
                f"Successfully extracted and normalized {len(normalized_posts)} posts from visible page."
            )
            return normalized_posts

        except Exception as e:
            logger.warning(f"Error while scraping visible posts: {e}")
            return normalized_posts

