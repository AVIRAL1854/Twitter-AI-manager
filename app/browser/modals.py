"""Handler for detecting and dismissing ONLY the 'Views' modal overlay on X (Twitter)."""

import asyncio
from playwright.async_api import Page
from app.observability.logging import get_logger

logger = get_logger("browser.modals")


async def dismiss_views_modal(page: Page) -> bool:
    """Detect and dismiss ONLY the specific 'Views' modal/sheet ('Times this post was seen').
    
    Strictly avoids touching any sidebar cards (such as 'Today's News'), menus, or composers.
    Returns True if the Views modal was detected and dismissed, False otherwise.
    """
    try:
        # Never dismiss if the user/agent is actively typing in a reply composer
        if await page.locator('[data-testid="tweetTextarea_0"]').count() > 0:
            return False

        # Strictly locate the specific 'Views' modal:
        # It is a dialog/sheet inside #layers (or [role="dialog"]) containing:
        # 1. "Times this post was seen" OR
        # 2. Heading "Views" AND a "Dismiss" button.
        views_dialog = page.locator('div#layers div[role="dialog"], div[role="dialog"]').filter(
            has_text="Times this post was seen"
        ).first

        is_present = await views_dialog.count() > 0
        if not is_present:
            # Secondary check: Dialog with both "Views" title and "Dismiss" button
            views_dialog = page.locator('div#layers div[role="dialog"], div[role="dialog"]').filter(
                has_text="Views"
            ).filter(
                has_text="Dismiss"
            ).first
            is_present = await views_dialog.count() > 0

        if not is_present:
            return False

        # Verify that the dialog is actually visible
        try:
            if not await views_dialog.is_visible():
                return False
        except Exception:
            return False

        logger.info("Detected active 'Views' modal blocking the screen.")

        # 1. User requirement: Click the cross button on this modal
        close_btn = views_dialog.locator(
            'button[aria-label="Close"], [data-testid="app-bar-close"], [aria-label="Close"]'
        ).first

        if await close_btn.count() > 0:
            try:
                if await close_btn.is_visible():
                    logger.info("Clicking the cross button to close 'Views' modal...")
                    await close_btn.click(timeout=1500)
                    await asyncio.sleep(0.4)
                    return True
            except Exception as click_err:
                logger.debug(f"Cross button click failed: {click_err}")

        # 2. Fallback: Click the 'Dismiss' button inside the Views dialog
        dismiss_btn = views_dialog.locator(
            'button:has-text("Dismiss"), [role="button"]:has-text("Dismiss")'
        ).first

        if await dismiss_btn.count() > 0:
            try:
                if await dismiss_btn.is_visible():
                    logger.info("Clicking 'Dismiss' button inside 'Views' modal...")
                    await dismiss_btn.click(timeout=1500)
                    await asyncio.sleep(0.4)
                    return True
            except Exception as click_err:
                logger.debug(f"Dismiss button click failed: {click_err}")

        # 3. Final fallback: Press Escape to close the Views modal
        logger.info("Pressing Escape to dismiss 'Views' modal...")
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.4)
        return True

    except Exception as e:
        logger.debug(f"Error checking/dismissing Views modal: {e}")
        return False


# Alias for backwards compatibility
dismiss_x_modals = dismiss_views_modal
