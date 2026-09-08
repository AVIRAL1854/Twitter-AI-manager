"""CLI entry point for the X Interaction AI Agent."""

import argparse
import asyncio
import sys
from rich.console import Console
from rich.table import Table

from app.config import Settings
from app.observability.logging import setup_logging
from app.planner.planner import MockPlanner
from app.services.run_service import RunService

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="X (Twitter) Interaction AI Agent - Intelligent, validated engagement pipeline."
    )
    parser.add_argument(
        "--target-url",
        type=str,
        help="Target X page or feed URL (e.g. https://x.com/home or search URL)",
    )
    parser.add_argument(
        "-n",
        "--count",
        "--limit",
        "--target-posts",
        "--max-interactions",
        dest="max_interactions",
        type=int,
        default=10,
        help="Target number of posts/interactions to perform for this run (default: 10). Example: -n 5 or --count 20",
    )
    parser.add_argument(
        "-s",
        "--max-scrolls",
        "--max-scroll-attempts",
        "--scroll-limit",
        dest="max_scroll_attempts",
        type=int,
        default=None,
        help="Maximum scroll attempts to find new posts before stopping (default: 10). Example: -s 5 or --max-scrolls 20",
    )
    parser.add_argument(
        "-i",
        "--max-inner-interactions",
        "--inner-limit",
        "--inner-interactions",
        dest="max_inner_interactions",
        type=int,
        default=None,
        help="Maximum interactions to perform inside a single post's comment thread (default: 10). Example: -i 5",
    )
    parser.add_argument(
        "--no-deep-dive",
        "--disable-deep-dive",
        dest="no_deep_dive",
        action="store_true",
        help="Disable exploring and interacting with comments inside high-interest posts (default: deep dive is enabled)",
    )
    parser.add_argument(
        "--deep-dive",
        dest="deep_dive",
        action="store_true",
        default=None,
        help="Explicitly enable exploring comments inside high-interest posts (default: enabled)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery, planning, and validation without clicking/typing in browser",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--mock-ai",
        action="store_true",
        help="Use deterministic mock planner instead of calling Gemini API",
    )
    parser.add_argument(
        "--jugad",
        action="store_true",
        help="Use free ChatGPT Web interface (chatgpt.com) via Playwright instead of Gemini API",
    )
    parser.add_argument(
        "--nvidia",
        action="store_true",
        help="Use NVIDIA OpenRouter model (nemotron-3.5-content-safety:free) for AI planning via OPEN_ROUTER_KEY",
    )
    parser.add_argument(
        "--try-nvidia",
        action="store_true",
        help="Test connectivity and sample response for the NVIDIA OpenRouter model using OPEN_ROUTER_KEY",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open interactive browser window to manually log in to X (Twitter) and save persistent session",
    )
    parser.add_argument(
        "--login-chatgpt",
        action="store_true",
        help="Open interactive browser window to manually log in to ChatGPT and save persistent session",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug level logging",
    )
    return parser.parse_args()


async def async_main() -> int:
    """Async main routine."""
    args = parse_args()

    # Configure logging
    log_level = 10 if args.debug else 20  # DEBUG vs INFO
    setup_logging(level=log_level)

    # Load settings with overrides
    settings = Settings()
    if args.target_url:
        settings.target_page = args.target_url
    if args.max_interactions is not None:
        settings.max_interactions = args.max_interactions
    if args.max_scroll_attempts is not None:
        settings.max_scroll_attempts = args.max_scroll_attempts
    if args.max_inner_interactions is not None:
        settings.max_inner_interactions = args.max_inner_interactions
    if args.no_deep_dive:
        settings.deep_dive_enabled = False
    elif args.deep_dive is True:
        settings.deep_dive_enabled = True
    if args.headless:
        settings.headless = True

    # Check if NVIDIA test connection requested
    if args.try_nvidia:
        from app.planner.nvidia_planner import test_nvidia_connection

        console.print("\n[bold cyan]🔍 Testing NVIDIA OpenRouter API connection...[/bold cyan]")
        result = await test_nvidia_connection(settings)

        table = Table(title="NVIDIA OpenRouter API Test Result", border_style="green" if result.get("success") else "red")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("Status", "[bold green]SUCCESS (200 OK)[/bold green]" if result.get("success") else "[bold red]FAILED[/bold red]")
        table.add_row("Target Model", str(result.get("model", settings.nvidia_model)))
        table.add_row("Latency", f"{result.get('elapsed_ms', 0):.1f} ms")

        api_key = settings.get_openrouter_api_key()
        masked_key = f"{api_key[:12]}...{api_key[-4:]}" if api_key and len(api_key) > 16 else ("DETECTED" if api_key else "[red]NOT CONFIGURED[/red]")
        table.add_row("OPEN_ROUTER_KEY", masked_key)

        if result.get("success"):
            usage = result.get("usage", {})
            table.add_row("Prompt Tokens", str(usage.get("prompt_tokens", "N/A")))
            table.add_row("Completion Tokens", str(usage.get("completion_tokens", "N/A")))
            table.add_row("Response Sample", str(result.get("response_content", "")))
            console.print(table)
            console.print("[bold green]✔ NVIDIA OpenRouter calls are going out and returning successfully![/bold green]\n")
            return 0
        else:
            table.add_row("Error", str(result.get("error", "Unknown error")))
            console.print(table)
            console.print("[bold red]✘ NVIDIA OpenRouter test call failed. Please verify OPEN_ROUTER_KEY in your .env file.[/bold red]\n")
            return 1

    # Check if login setup mode requested
    if args.login:
        from app.browser.login import interactive_login
        success = await interactive_login(settings)
        return 0 if success else 1

    if args.login_chatgpt:
        from app.planner.login_chatgpt import interactive_chatgpt_login
        success = await interactive_chatgpt_login(settings)
        return 0 if success else 1

    planner = None
    if args.mock_ai:
        planner = MockPlanner(settings)
    elif args.jugad:
        from app.planner.chatgpt_web import ChatGPTWebPlanner
        planner = ChatGPTWebPlanner(settings)
    elif args.nvidia:
        from app.planner.nvidia_planner import NvidiaOpenRouterPlanner
        planner = NvidiaOpenRouterPlanner(settings)

    run_service = RunService(
        settings=settings,
        planner=planner,
        dry_run=args.dry_run,
    )

    try:
        state = await run_service.run()
    finally:
        if planner and hasattr(planner, "close"):
            await planner.close()

    # Print summary table
    table = Table(title="Execution Summary", border_style="bright_blue")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Run ID", state.run_id)
    table.add_row("Status", state.status.upper())
    table.add_row("Posts Discovered", str(state.metrics.posts_discovered))
    table.add_row("Posts Eligible", str(state.metrics.posts_eligible))
    table.add_row("Actions Proposed", str(state.metrics.actions_proposed))
    table.add_row("Actions Approved", str(state.metrics.actions_approved))
    table.add_row("Actions Executed", str(state.metrics.actions_executed))
    table.add_row("Actions Succeeded", str(state.metrics.actions_succeeded))
    table.add_row("Actions Failed", str(state.metrics.actions_failed))
    table.add_row("Deep Dives Performed", str(state.metrics.deep_dives_performed))
    table.add_row("Inner Comments Interacted", str(state.metrics.inner_interactions_executed))
    table.add_row("Scrolls Performed", str(state.metrics.scroll_count))
    table.add_row("Duration (s)", f"{state.metrics.run_duration_seconds:.2f}")

    console.print()
    console.print(table)

    return 0 if state.status in ("completed", "budget_exhausted") else 1


def main():
    """Synchronous entry point."""
    try:
        sys.exit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        console.print("\n[yellow]Run interrupted by user.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()

