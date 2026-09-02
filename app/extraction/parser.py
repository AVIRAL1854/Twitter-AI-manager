"""DOM parser extracting raw post attributes from Playwright elements."""

import re
from typing import Any, Optional
from playwright.async_api import Locator

from app.models.post import RawPostData
from app.observability.logging import ExtractionError, get_logger

logger = get_logger("extraction.parser")

STATUS_ID_REGEX = re.compile(r"/status/(\d+)")
HANDLE_REGEX = re.compile(r"@[\w_]+")


class PostParser:
    """Extracts raw post fields from an X tweet DOM Locator."""

    @staticmethod
    async def extract_from_locator(tweet_locator: Locator) -> Optional[RawPostData]:
        """Extract RawPostData from an article[data-testid="tweet"] locator."""
        try:
            # 1. Extract Post URL and Post ID from status link
            post_id: Optional[str] = None
            url: Optional[str] = None

            # Look for status link (usually contains /status/<id>)
            status_link_loc = tweet_locator.locator('a[href*="/status/"]').first
            if await status_link_loc.count() > 0:
                href = await status_link_loc.get_attribute("href")
                if href:
                    match = STATUS_ID_REGEX.search(href)
                    if match:
                        post_id = match.group(1)
                        if href.startswith("http"):
                            url = href
                        else:
                            url = f"https://x.com{href}"

            # Fallback: time element's parent link
            if not post_id:
                time_loc = tweet_locator.locator("time").first
                if await time_loc.count() > 0:
                    parent_link = time_loc.locator("xpath=..")
                    href = await parent_link.get_attribute("href")
                    if href:
                        match = STATUS_ID_REGEX.search(href)
                        if match:
                            post_id = match.group(1)
                            url = href if href.startswith("http") else f"https://x.com{href}"

            if not post_id:
                logger.debug("Could not locate stable post_id in tweet element; skipping.")
                return None

            # 2. Extract Author Name and Username
            author_name: str = ""
            author_username: str = ""
            user_name_loc = tweet_locator.locator('[data-testid="User-Name"]').first
            if await user_name_loc.count() > 0:
                user_text = await user_name_loc.inner_text()
                lines = [line.strip() for line in user_text.split("\n") if line.strip()]
                if lines:
                    author_name = lines[0]
                    # Find the @username line
                    for line in lines:
                        handle_match = HANDLE_REGEX.search(line)
                        if handle_match:
                            author_username = handle_match.group(0)
                            break
                    if not author_username and len(lines) > 1:
                        author_username = lines[1]

            # 3. Extract Tweet Text
            text: str = ""
            text_loc = tweet_locator.locator('[data-testid="tweetText"]').first
            if await text_loc.count() > 0:
                text = await text_loc.inner_text()

            # 4. Extract Timestamp
            timestamp: Optional[str] = None
            time_elem = tweet_locator.locator("time").first
            if await time_elem.count() > 0:
                timestamp = await time_elem.get_attribute("datetime")

            # 5. Extract Engagement Metrics
            reply_count_str = await PostParser._get_aria_or_text(tweet_locator, '[data-testid="reply"]')
            repost_count_str = await PostParser._get_aria_or_text(
                tweet_locator, '[data-testid="retweet"], [data-testid="unretweet"]'
            )
            like_count_str = await PostParser._get_aria_or_text(
                tweet_locator, '[data-testid="like"], [data-testid="unlike"]'
            )

            # 6. Check if Reply or Repost
            is_repost = False
            social_context = tweet_locator.locator('[data-testid="socialContext"]').first
            if await social_context.count() > 0:
                ctx_text = await social_context.inner_text()
                if "reposted" in ctx_text.lower():
                    is_repost = True

            is_reply = False
            # If there is a "Replying to @..." header
            reply_header = tweet_locator.locator('text=/Replying to/i').first
            if await reply_header.count() > 0:
                is_reply = True

            return RawPostData(
                post_id=post_id,
                url=url,
                author_name=author_name,
                author_username=author_username,
                text=text,
                timestamp=timestamp,
                likes_str=like_count_str,
                replies_str=reply_count_str,
                reposts_str=repost_count_str,
                is_reply=is_reply,
                is_repost=is_repost,
            )

        except Exception as e:
            logger.warning(f"Error parsing post element: {e}")
            return None

    @staticmethod
    async def _get_aria_or_text(tweet_locator: Locator, selector: str) -> Optional[str]:
        """Extract engagement count from aria-label or inner text."""
        try:
            elem = tweet_locator.locator(selector).first
            if await elem.count() > 0:
                # Often aria-label has e.g. "42 Likes" or "10 replies"
                aria = await elem.get_attribute("aria-label")
                if aria:
                    return aria
                return await elem.inner_text()
        except Exception:
            pass
        return None

