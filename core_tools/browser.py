"""Core tool: browser — web automation via Playwright."""

import os
from datetime import datetime, timezone

from config import config

# Lazy-initialized browser state
_browser = None
_context = None
_page = None

ARTIFACTS_DIR = os.path.join(config.seed_dir, "data", "artifacts")


async def _ensure_browser():
    """Launch browser on first use."""
    global _browser, _context, _page
    if _page is not None:
        return _page

    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    _browser = await pw.chromium.launch(headless=False)
    _context = await _browser.new_context(viewport={"width": 1280, "height": 800})
    _page = await _context.new_page()
    return _page


async def execute(
    action: str,
    url: str = None,
    selector: str = None,
    text: str = None,
    js: str = None,
) -> str:
    page = await _ensure_browser()
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    try:
        if action == "navigate":
            if not url:
                return "Error: navigate requires a url"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return f"Navigated to {page.url} — title: {await page.title()}"

        elif action == "click":
            if not selector:
                return "Error: click requires a selector"
            await page.click(selector, timeout=10000)
            return f"Clicked: {selector}"

        elif action == "type":
            if not selector or text is None:
                return "Error: type requires selector and text"
            await page.fill(selector, text, timeout=10000)
            return f"Typed into {selector}"

        elif action == "read":
            content = await page.inner_text("body")
            # Truncate long pages
            if len(content) > 50000:
                content = content[:50000] + "\n[truncated]"
            return f"URL: {page.url}\n\n{content}"

        elif action == "screenshot":
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = os.path.join(ARTIFACTS_DIR, f"screenshot-{ts}.png")
            await page.screenshot(path=path, full_page=False)
            return f"Screenshot saved: {path}"

        elif action == "evaluate":
            if not js:
                return "Error: evaluate requires js"
            result = await page.evaluate(js)
            return f"Result: {result}"

        else:
            return f"Error: unknown action '{action}'. Valid: navigate, click, type, read, screenshot, evaluate"

    except Exception as e:
        return f"Error: {e}"


tool = {
    "name": "browser",
    "description": "Control a web browser. Actions: navigate(url), click(selector), type(selector, text), read() page content, screenshot(), evaluate(js).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform: navigate, click, type, read, screenshot, evaluate",
                "enum": ["navigate", "click", "type", "read", "screenshot", "evaluate"],
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to (for navigate action)",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for the target element (for click/type actions)",
            },
            "text": {
                "type": "string",
                "description": "Text to type (for type action)",
            },
            "js": {
                "type": "string",
                "description": "JavaScript to evaluate (for evaluate action)",
            },
        },
        "required": ["action"],
    },
    "execute": execute,
}
