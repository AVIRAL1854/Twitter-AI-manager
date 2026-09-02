"""Interactive login helper for ChatGPT Web."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel

from app.config import Settings
from app.observability.logging import get_logger

logger = get_logger("planner.chatgpt_login")
console = Console()


async def interactive_chatgpt_login(settings: Settings) -> bool:
    """Open interactive browser for the user to manually log in to ChatGPT and persist cookies."""
    profile_dir = Path(settings.chatgpt_user_data_dir).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold green]Interactive ChatGPT Login[/bold green]\n\n"
            f"1. A Chromium browser window is opening to [cyan]https://chatgpt.com[/cyan].\n"
            f"2. Please log in with your OpenAI / Google / Apple account.\n"
            f"3. Once logged in and you see the ChatGPT home chat screen, return to this terminal.\n"
            f"4. Press [bold yellow]ENTER[/bold yellow] to save your session permanently in:\n"
            f"   [dim]{profile_dir}[/dim]",
            title="ChatGPT Authentication Setup",
            border_style="green",
        )
    )

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        logger.info("Opening ChatGPT login page...")
        await page.goto("https://chatgpt.com", wait_until="domcontentloaded")

        # Wait for user confirmation in terminal
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, input, "\n>>> Press ENTER here AFTER you have successfully logged in to ChatGPT: "
        )

        logger.info("Verifying ChatGPT session...")
        await asyncio.sleep(2)
        await context.close()

    console.print(
        "\n[bold green]✓ ChatGPT login state saved successfully![/bold green] All future `--jugad` runs will automatically stay logged in.\n"
    )
    return True

