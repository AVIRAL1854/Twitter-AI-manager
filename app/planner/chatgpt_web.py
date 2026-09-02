"""ChatGPT Web Automation Planner for free AI decision-making without API keys."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.async_api import BrowserContext, Page, async_playwright

from app.config import Settings
from app.memory.models import InteractionRecord
from app.models.action import ActionPlan, ProposedAction
from app.models.post import NormalizedPost
from app.observability.logging import PlanningError, get_logger
from app.planner.base import BasePlanner
from app.planner.prompts import SYSTEM_PROMPT, PromptBuilder

logger = get_logger("planner.chatgpt_web")


class ChatGPTWebPlanner(BasePlanner):
    """Uses Playwright to automate ChatGPT Web interface (chatgpt.com) for AI decisions."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def _ensure_browser(self) -> Page:
        """Launch or return existing persistent ChatGPT browser session."""
        if self._page and not self._page.is_closed():
            return self._page

        profile_dir = Path(self.settings.chatgpt_user_data_dir).resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Launching ChatGPT Web browser session at {profile_dir}...")
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.settings.headless,
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"],
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

        logger.info("Navigating to https://chatgpt.com...")
        await self._page.goto("https://chatgpt.com", wait_until="domcontentloaded")
        await asyncio.sleep(2.5)
        await self._dismiss_modals(self._page)
        return self._page

    async def _dismiss_modals(self, page: Page) -> None:
        """Dismiss sign-in modals, stay logged out prompts, and welcome dialogs."""
        try:
            # 1. Look for 'Stay logged out' link/button
            stay_logged_out = page.locator(
                'button:has-text("Stay logged out"), a:has-text("Stay logged out"), [data-testid="stay-logged-out-button"]'
            ).first
            if await stay_logged_out.count() > 0 and await stay_logged_out.is_visible():
                logger.info("Dismissing 'Stay logged out' modal...")
                await stay_logged_out.click()
                await asyncio.sleep(0.8)

            # 2. Look for close (X) / Dismiss / Maybe later buttons
            close_selectors = [
                '[data-testid="close-button"]',
                'button[aria-label="Close"]',
                'button:has-text("Close")',
                'button:has-text("Dismiss")',
                'button:has-text("Maybe later")',
                'button:has-text("Continue without logging in")',
                'div[role="dialog"] button:has-text("×")',
                'div[role="dialog"] button[aria-label="Close"]',
            ]
            for selector in close_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    try:
                        logger.debug(f"Dismissing modal via {selector}")
                        await btn.click()
                        await asyncio.sleep(0.4)
                    except Exception:
                        pass

            # 3. Fallback: Press Escape to close any active modal overlay
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.debug(f"Modal dismissal check: {e}")

    async def _start_new_chat(self, page: Page) -> None:
        """Start a new chat session via sidebar button or navigating to https://chatgpt.com."""
        logger.info("Starting fresh ChatGPT chat session (opening new chat)...")
        try:
            # 1. Try direct New chat button (if already visible in top bar or sidebar)
            new_chat_selectors = [
                'a[href="/"]',
                '[data-testid="create-new-chat-button"]',
                'button[aria-label="New chat"]',
                'a[aria-label="New chat"]',
                'a:has-text("New chat")',
                'button:has-text("New chat")',
            ]
            for sel in new_chat_selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    logger.debug(f"Clicking New chat button: {sel}")
                    await btn.click()
                    await asyncio.sleep(1.5)
                    await self._dismiss_modals(page)
                    return

            # 2. Open sidebar if collapsed, then click New chat
            sidebar_btn = page.locator(
                'button[aria-label="Open sidebar"], [data-testid="open-sidebar-button"]'
            ).first
            if await sidebar_btn.count() > 0 and await sidebar_btn.is_visible():
                await sidebar_btn.click()
                await asyncio.sleep(0.6)
                for sel in new_chat_selectors:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1.5)
                        await self._dismiss_modals(page)
                        return

        except Exception as e:
            logger.debug(f"New chat click attempt: {e}")

        # 3. Reliable Fallback: Navigate to root chatgpt.com URL
        logger.info("Reloading ChatGPT root page for a clean session...")
        await page.goto("https://chatgpt.com", wait_until="domcontentloaded")
        await asyncio.sleep(2.5)
        await self._dismiss_modals(page)

    async def _check_limit_reached(self, page: Page) -> bool:
        """Detect if ChatGPT displayed a message limit or capacity error."""
        try:
            # Check for model switch / limit button or alert
            limit_selectors = [
                'button:has-text("Stay on GPT-4o mini")',
                'button:has-text("Switch to GPT-4o mini")',
                'button:has-text("Continue without GPT-4o")',
                'div[role="alert"]:has-text("limit")',
                'div[role="alert"]:has-text("reached")',
            ]
            for sel in limit_selectors:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    # Click model switch if available
                    if "Stay on" in sel or "Switch to" in sel:
                        await el.click()
                        await asyncio.sleep(1)
                    return True

            # Check body text for limit notifications
            page_text = await page.locator("body").inner_text()
            text_lower = page_text.lower()
            limit_indicators = [
                "you've reached your limit",
                "you have reached your limit",
                "you've hit your limit",
                "you have hit your limit",
                "usage limit reached",
                "too many requests in 1 hour",
                "try again after",
            ]
            for ind in limit_indicators:
                if ind in text_lower:
                    return True

        except Exception as e:
            logger.debug(f"Limit check note: {e}")

        return False

    async def _find_input_field(self, page: Page):
        """Find ChatGPT prompt textarea or contenteditable element."""
        selectors = [
            "#prompt-textarea",
            'div[contenteditable="true"]#prompt-textarea',
            'div[contenteditable="true"][data-placeholder]',
            "textarea#prompt-textarea",
            "textarea",
        ]
        for sel in selectors:
            elem = page.locator(sel).first
            if await elem.count() > 0 and await elem.is_visible():
                return elem
        return None

    @staticmethod
    def _is_user_prompt_content(text: str) -> bool:
        """Check if captured text is the user prompt rather than the assistant's response."""
        markers = [
            "evaluate these posts",
            "critical instructions:",
            "token economy rules",
            "your persona & vibe",
            "system_prompt",
            "example output format:",
        ]
        text_lower = text.lower()
        return any(m in text_lower for m in markers)

    async def _extract_via_copy_button(self, page: Page) -> Optional[str]:
        """Click the ChatGPT Copy button specifically belonging to the assistant response."""
        try:
            # Locate the latest assistant message turn
            assistant_loc = page.locator(
                '[data-message-author-role="assistant"], div[data-testid*="conversation-turn-assistant"]'
            ).last

            if await assistant_loc.count() > 0:
                try:
                    await assistant_loc.hover(timeout=1000)
                except Exception:
                    pass

            # Dispatch JavaScript click specifically on the assistant's copy button
            clicked = await page.evaluate("""() => {
                // 1. Locate all assistant message elements
                const assistantNodes = Array.from(document.querySelectorAll(
                    '[data-message-author-role="assistant"], [data-testid*="conversation-turn-assistant"], div.agent-turn'
                ));

                if (assistantNodes.length === 0) {
                    return false;
                }

                // Get the latest assistant turn
                const latestAssistant = assistantNodes[assistantNodes.length - 1];

                // Find the enclosing turn container that houses the message and its action bar
                let turnContainer = latestAssistant.closest('article') ||
                                    latestAssistant.closest('[data-testid*="conversation-turn"]') ||
                                    latestAssistant.parentElement?.closest('[data-testid*="conversation-turn"]') ||
                                    latestAssistant.parentElement ||
                                    latestAssistant;

                // Safety check: ensure this container doesn't belong to the user
                if (turnContainer.querySelector('[data-message-author-role="user"]') && !turnContainer.querySelector('[data-message-author-role="assistant"]')) {
                    return false;
                }

                // 2. Search for copy buttons strictly within the assistant's turn container
                const copyBtns = Array.from(turnContainer.querySelectorAll(
                    'button[aria-label="Copy"], [data-testid="copy-turn-action-button"], button[data-testid="copy-turn-action-button"], button[aria-label="Copy code"]'
                ));

                for (let i = copyBtns.length - 1; i >= 0; i--) {
                    const btn = copyBtns[i];
                    if (!btn.closest('[data-message-author-role="user"]')) {
                        btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        if (typeof btn.click === 'function') btn.click();
                        return true;
                    }
                }

                // 3. Search for the copy SVG path specifically inside the assistant turn container
                const paths = Array.from(turnContainer.querySelectorAll('path'));
                for (let i = paths.length - 1; i >= 0; i--) {
                    const d = paths[i].getAttribute('d') || '';
                    if (d.includes('15.1006') || d.includes('M15.1') || d.includes('M16 1H4')) {
                        const target = paths[i].closest('button') || paths[i].closest('span') || paths[i];
                        if (target && !target.closest('[data-message-author-role="user"]')) {
                            target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                            if (typeof target.click === 'function') target.click();
                            return true;
                        }
                    }
                }

                return false;
            }""")

            if clicked:
                logger.info("Successfully clicked Assistant's Copy button.")
                await asyncio.sleep(0.5)
                clipboard_text = await page.evaluate("() => navigator.clipboard.readText()")
                if clipboard_text:
                    if self._is_user_prompt_content(clipboard_text):
                        logger.warning("Clipboard captured user prompt instead of assistant response. Ignoring.")
                        return None

                    if "actions" in clipboard_text or "post_id" in clipboard_text or "id" in clipboard_text:
                        logger.info(f"Captured text from clipboard via Assistant Copy button ({len(clipboard_text)} chars).")
                        return clipboard_text

        except Exception as e:
            logger.debug(f"JS Assistant Copy button click note: {e}")

        # Playwright direct force-click fallback strictly on the assistant turn
        try:
            assistant_turn = page.locator(
                '[data-message-author-role="assistant"], div[data-testid*="conversation-turn-assistant"]'
            ).last
            if await assistant_turn.count() > 0:
                parent_turn = assistant_turn.locator(
                    "xpath=./ancestor-or-self::article | ./ancestor-or-self::div[contains(@data-testid, 'conversation-turn')]"
                ).last
                target_scope = parent_turn if await parent_turn.count() > 0 else assistant_turn

                copy_selectors = [
                    'button:has(svg path[d*="15.1006"])',
                    '[data-testid="copy-turn-action-button"]',
                    'button[data-testid="copy-turn-action-button"]',
                    'button[aria-label="Copy"]',
                    'button:has-text("Copy code")',
                    'button:has-text("Copy")',
                ]
                for sel in copy_selectors:
                    btn = target_scope.locator(sel).last
                    if await btn.count() > 0:
                        await btn.click(force=True, timeout=1000)
                        await asyncio.sleep(0.5)
                        clipboard_text = await page.evaluate("() => navigator.clipboard.readText()")
                        if (
                            clipboard_text
                            and not self._is_user_prompt_content(clipboard_text)
                            and ("actions" in clipboard_text or "post_id" in clipboard_text)
                        ):
                            logger.info(f"Captured text via Playwright assistant Copy ({len(clipboard_text)} chars).")
                            return clipboard_text
        except Exception as e:
            logger.debug(f"Playwright assistant Copy note: {e}")

        return None

    async def _get_latest_assistant_text(self, page: Page) -> str:
        """Extract text from the latest assistant response in the DOM."""
        try:
            # 1. Check for ChatGPT stream paragraph blocks (e.g. data-assistant-stream-block)
            stream_blocks = page.locator(
                'p[data-assistant-stream-block], [data-assistant-stream-block], p[data-assistant-stream-block-index], [data-assistant-stream-block-index]'
            )
            if await stream_blocks.count() > 0:
                count = await stream_blocks.count()
                texts = []
                for i in range(count):
                    t = await stream_blocks.nth(i).inner_text()
                    if t.strip():
                        texts.append(t.strip())
                joined = "\n".join(texts)
                if (
                    not self._is_user_prompt_content(joined)
                    and ("actions" in joined or "post_id" in joined or "id" in joined)
                ):
                    return joined

            # 2. Check if <pre><code> block is present inside assistant turn
            code_blocks = page.locator(
                '[data-message-author-role="assistant"] pre code, [data-message-author-role="assistant"] pre, pre code'
            )
            if await code_blocks.count() > 0:
                code_text = await code_blocks.last.inner_text()
                if (
                    not self._is_user_prompt_content(code_text)
                    and ("actions" in code_text or "post_id" in code_text or "id" in code_text)
                ):
                    return code_text

            # 3. Check assistant message role containers
            assistant_msgs = page.locator('[data-message-author-role="assistant"]')
            if await assistant_msgs.count() > 0:
                text = await assistant_msgs.last.inner_text()
                if (
                    not self._is_user_prompt_content(text)
                    and text.strip()
                    and ("actions" in text or "post_id" in text)
                ):
                    return text

            # 4. Check markdown containers inside assistant turns
            md_blocks = page.locator(
                '[data-message-author-role="assistant"] div.markdown, div[data-testid*="conversation-turn-assistant"] div.markdown'
            )
            if await md_blocks.count() > 0:
                text = await md_blocks.last.inner_text()
                if (
                    not self._is_user_prompt_content(text)
                    and text.strip()
                    and ("actions" in text or "post_id" in text)
                ):
                    return text

        except Exception as e:
            logger.debug(f"Error fetching assistant text: {e}")

        return ""

    async def _wait_for_response(self, page: Page, timeout_seconds: int = 120) -> str:
        """Wait patiently until ChatGPT finishes generating and return the response text."""
        start_time = asyncio.get_event_loop().time()
        logger.info("Waiting for ChatGPT to process prompt and respond...")

        # Phase 1: Allow ChatGPT time to receive and dispatch the prompt
        await asyncio.sleep(3.5)
        await self._dismiss_modals(page)

        # Phase 2: Wait up to 15 seconds for generation to actively begin
        logger.debug("Waiting for ChatGPT generation to start...")
        for _ in range(12):
            if await self._check_limit_reached(page):
                logger.warning("ChatGPT usage limit detected during response wait.")
                raise PlanningError("ChatGPT limit reached. Starting fresh chat.")

            stop_btn = page.locator(
                '[data-testid="stop-button"], button[aria-label="Stop streaming"], button[aria-label="Stop generating"], button:has-text("Stop")'
            ).first
            is_generating = await stop_btn.count() > 0 and await stop_btn.is_visible()

            assistant_msgs = page.locator('[data-message-author-role="assistant"]')
            has_assistant = await assistant_msgs.count() > 0

            if is_generating or has_assistant:
                logger.info("ChatGPT generation detected. Streaming in progress...")
                break
            await asyncio.sleep(1.0)

        # Phase 3: Wait for generation to fully complete
        last_text = ""
        steady_count = 0

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            await self._dismiss_modals(page)

            # Check if limit was reached mid-generation
            if await self._check_limit_reached(page):
                logger.warning("ChatGPT usage limit detected during response generation.")
                raise PlanningError("ChatGPT limit reached. Starting fresh chat.")

            # Check if stop generating button is visible
            stop_btn = page.locator(
                '[data-testid="stop-button"], button[aria-label="Stop streaming"], button[aria-label="Stop generating"], button:has-text("Stop")'
            ).first
            is_generating = await stop_btn.count() > 0 and await stop_btn.is_visible()

            # If actively generating, wait patiently for it to finish
            if is_generating:
                logger.debug("ChatGPT still streaming response...")
                await asyncio.sleep(1.5)
                continue

            # Generation has stopped - give a brief 1.5s pause for DOM and action buttons to settle
            await asyncio.sleep(1.5)

            # First attempt: Try Assistant Copy button ONLY when not generating
            copy_text = await self._extract_via_copy_button(page)
            if copy_text and not self._is_user_prompt_content(copy_text):
                try:
                    plan = self._extract_json_from_text(copy_text)
                    if plan and len(plan.actions) > 0:
                        logger.info(
                            f"Successfully parsed plan via Assistant Copy button ({len(plan.actions)} actions)."
                        )
                        return copy_text
                except Exception:
                    pass

            # Second attempt: Extract latest assistant text directly from assistant DOM
            current_text = await self._get_latest_assistant_text(page)

            if current_text and not self._is_user_prompt_content(current_text):
                # If text is present, test if it's already a complete valid JSON plan
                try:
                    plan = self._extract_json_from_text(current_text)
                    if plan and len(plan.actions) > 0:
                        logger.info(
                            f"Captured complete valid ActionPlan from ChatGPT assistant DOM ({len(plan.actions)} actions, {len(current_text)} chars)."
                        )
                        return current_text
                except Exception:
                    pass

                if current_text == last_text and len(current_text) > 10:
                    steady_count += 1
                    if steady_count >= 2:
                        logger.info(
                            f"Captured steady ChatGPT response ({len(current_text)} chars)."
                        )
                        return current_text
                else:
                    steady_count = 0
                    last_text = current_text

            await asyncio.sleep(1.5)

        # Timeout reached: if we captured non-empty text, attempt to use it
        if last_text and len(last_text) > 20:
            logger.warning("Generation wait timed out, but captured text. Proceeding to parse.")
            return last_text

        raise PlanningError("Timed out waiting for ChatGPT Web response.")

    def _extract_json_from_text(self, raw_text: str) -> ActionPlan:
        """Robustly parse ActionPlan JSON from raw ChatGPT markdown or text response."""
        text = raw_text.strip()

        # 1. Search markdown code blocks
        code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        for block in reversed(code_blocks):
            try:
                data = json.loads(block.strip())
                return self._normalize_and_validate(data)
            except Exception:
                pass

        # 2. Bracket counting extractor for balanced JSON objects
        start_idx = text.find("{")
        while start_idx != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start_idx, len(text)):
                c = text[i]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            candidate = text[start_idx : i + 1]
                            try:
                                data = json.loads(candidate)
                                return self._normalize_and_validate(data)
                            except Exception:
                                pass
                            break
            start_idx = text.find("{", start_idx + 1)

        # 3. Direct parse
        try:
            data = json.loads(text)
            return self._normalize_and_validate(data)
        except Exception:
            pass

        raise PlanningError(
            f"Failed to extract valid JSON ActionPlan from ChatGPT output:\n{text[:400]}..."
        )

    def _normalize_and_validate(self, data: Any) -> ActionPlan:
        """Normalize parsed dictionary or list into ActionPlan schema."""
        if isinstance(data, list):
            data = {"actions": data}

        if not isinstance(data, dict):
            raise ValueError("Expected JSON dictionary or list.")

        # Find actions list: could be at top-level or inside nested keys
        actions_list = None
        if "actions" in data and isinstance(data["actions"], list):
            actions_list = data["actions"]
        else:
            for k, v in data.items():
                if k == "actions" and isinstance(v, list):
                    actions_list = v
                    break
                elif isinstance(v, dict) and "actions" in v and isinstance(v["actions"], list):
                    actions_list = v["actions"]
                    break

        if actions_list is None:
            raise ValueError("Parsed JSON does not contain an 'actions' list.")

        normalized_actions: List[ProposedAction] = []
        for idx, item in enumerate(actions_list):
            if not isinstance(item, dict):
                continue

            post_id = str(item.get("post_id") or item.get("id") or "").strip()
            action_type = str(item.get("action") or "skip").lower().strip()
            if action_type not in ("like", "comment", "reply", "skip"):
                action_type = "skip"

            reason = str(item.get("reason") or "relevant post").strip()
            content = item.get("content")
            if content is not None:
                content = str(content).strip() or None

            priority = item.get("priority", idx + 1)
            try:
                priority = int(priority)
            except (ValueError, TypeError):
                priority = idx + 1

            explore_thread = bool(item.get("explore_thread", False))
            interest_score = item.get("interest_score")
            try:
                if interest_score is not None:
                    interest_score = int(interest_score)
            except (ValueError, TypeError):
                interest_score = None

            if post_id:
                normalized_actions.append(
                    ProposedAction(
                        post_id=post_id,
                        action=action_type,
                        reason=reason,
                        content=content,
                        priority=priority,
                        interest_score=interest_score,
                        explore_thread=explore_thread,
                    )
                )

        return ActionPlan(actions=normalized_actions)

    async def plan(
        self,
        posts: List[NormalizedPost],
        remaining_budget: int,
        recent_history: Optional[List[InteractionRecord]] = None,
    ) -> ActionPlan:
        """Execute planning prompt through ChatGPT Web interface with auto-recovery."""
        if not posts or remaining_budget <= 0:
            return ActionPlan(actions=[])

        page = await self._ensure_browser()

        # Build prompt
        user_prompt = PromptBuilder.build_user_prompt(
            self.settings, posts, remaining_budget, recent_history
        )
        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{user_prompt}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "- Do NOT repeat or echo the input profile, goal, or post list.\n"
            "- Output ONLY the valid JSON object with the 'actions' key matching the ActionPlan schema.\n"
            "- Example output format: {\"actions\": [{\"post_id\": \"123\", \"action\": \"like\", \"reason\": \"cool project\", \"content\": null, \"priority\": 1}]}\n"
        )

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"Sending {len(posts)} posts to ChatGPT Web (remaining budget: {remaining_budget}, attempt {attempt}/{max_attempts})..."
                )
                await self._dismiss_modals(page)

                # Check if limit was reached before typing
                if await self._check_limit_reached(page):
                    logger.warning("ChatGPT limit detected. Starting new chat...")
                    await self._start_new_chat(page)

                input_field = await self._find_input_field(page)
                if not input_field:
                    logger.warning("Input field not found, opening fresh ChatGPT session...")
                    await self._start_new_chat(page)
                    input_field = await self._find_input_field(page)
                    if not input_field:
                        raise PlanningError("Unable to locate ChatGPT prompt input field.")

                await input_field.click()
                await input_field.fill(full_prompt)
                await asyncio.sleep(0.8)

                # Click send button or press Enter
                send_btn = page.locator(
                    '[data-testid="send-button"], button[aria-label="Send prompt"], button[data-testid="fruitjuice-send-button"]'
                ).first
                if await send_btn.count() > 0 and await send_btn.is_visible():
                    await send_btn.click()
                else:
                    await input_field.press("Enter")

                # Wait for response text
                response_text = await self._wait_for_response(page)
                plan = self._extract_json_from_text(response_text)
                logger.info(f"ChatGPT Web Planner proposed {len(plan.actions)} actions.")
                return plan

            except Exception as e:
                logger.warning(f"ChatGPT Web attempt {attempt} failed: {e}")
                if attempt < max_attempts:
                    logger.info("Opening sidebar / starting new chat for retry...")
                    await self._start_new_chat(page)
                    await asyncio.sleep(1.5)
                else:
                    if isinstance(e, PlanningError):
                        raise
                    raise PlanningError(f"ChatGPT Web Planner encountered error: {e}") from e

    async def close(self) -> None:
        """Close ChatGPT browser session."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("ChatGPT Web browser session closed.")
        except Exception as e:
            logger.warning(f"Error closing ChatGPT browser session: {e}")
