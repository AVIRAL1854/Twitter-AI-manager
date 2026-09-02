"""Interactive manual login routine to save persistent X (Twitter) authentication state."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel

from app.config import Settings
from app.observability.logging import get_logger

logger = get_logger("browser.login")
console = Console()


async def interactive_login(settings: Settings) -> bool:
    """Launch visible browser with persistent profile for one-time manual login."""
    profile_dir = Path(settings.user_data_dir).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel.fit(
            f"[bold cyan]X (Twitter) Authentication Setup[/bold cyan]\n\n"
            f"Persistent Profile Directory:\n[yellow]{profile_dir}[/yellow]\n\n"
            f"A Chromium window will now open.\n"
            f"1. Log into your X account in the browser.\n"
            f"2. Complete any 2-factor authentication if required.\n"
            f"3. Return to this terminal once your feed is loaded.",
            border_style="cyan",
        )
    )

    playwright = await async_playwright().start()
    try:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
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

        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        # Navigate to login / home
        logger.info("Opening X login page...")
        await page.goto("https://x.com/login", wait_until="domcontentloaded")

        console.print("\n[bold green]Waiting for login...[/bold green]")
        console.print("When you are logged in and can see your home feed, press [bold cyan]ENTER[/bold cyan] in this terminal to save session and exit.")

        # Non-blocking input listener with periodic check
        loop = asyncio.get_running_loop()
        input_task = loop.run_in_executor(None, input, "Press ENTER when logged in: ")

        # While waiting for user input, also check if home feed indicators appear
        logged_in_detected = False
        while not input_task.done():
            try:
                if not page.is_closed():
                    if (
                        await page.locator('[data-testid="SideNav_AccountSwitcher_Button"]').count() > 0
                        or await page.locator('[data-testid="AppTabBar_Home_Link"]').count() > 0
                    ):
                        if not logged_in_detected:
                            logged_in_detected = True
                            console.print("[green]✓ Detected successful login session in browser![/green]")
            except Exception:
                pass
            await asyncio.sleep(1.0)

        # Wait for input task completion
        await input_task

        # Give browser time to persist cookies/storage
        await asyncio.sleep(2.0)
        await context.close()
        await playwright.stop()

        console.print(
            Panel.fit(
                f"[bold green]✓ Session successfully saved![/bold green]\n\n"
                f"Your authenticated profile is saved at:\n"
                f"[yellow]{profile_dir}[/yellow]\n\n"
                f"All future agent runs will automatically reuse this session.",
                border_style="green",
            )
        )
        return True

    except Exception as e:
        logger.error(f"Error during interactive login: {e}")
        console.print(f"[red]Failed during login setup: {e}[/red]")
        try:
            await playwright.stop()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    asyncio.run(interactive_login(Settings()))

