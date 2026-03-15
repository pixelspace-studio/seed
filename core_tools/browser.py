"""Core tool: browser — general-purpose web automation via Playwright + real Chrome.

Upgraded from the original Chromium headless version based on a better
implementation Semillita built herself (tools/playwright_agent.py).
Supports multiple named sessions, click-by-text, structured DOM extraction,
scroll, wait, and real Chrome to avoid bot detection.
"""

import json
import os
from datetime import datetime, timezone

from config import config

ARTIFACTS_DIR = os.path.join(config.seed_dir, "data", "artifacts")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

# Active sessions: name -> {pw, browser, context, page}
_sessions: dict = {}


async def _get_page(session: str = "default"):
    """Get or create a named browser session."""
    if session in _sessions:
        return _sessions[session]["page"]

    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(channel="chrome", headless=False)
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1440, "height": 900},
    )
    page = await context.new_page()
    _sessions[session] = {"pw": pw, "browser": browser, "context": context, "page": page}
    return page


async def execute(
    action: str,
    url: str = None,
    selector: str = None,
    text: str = None,
    js: str = None,
    wait_for: str = None,
    timeout: int = 15000,
    session: str = "default",
) -> str:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    try:
        page = await _get_page(session)

        if action == "navigate":
            if not url:
                return "Error: navigate requires a url"
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=timeout)
            return f"OK: {page.url} — title: {await page.title()}"

        elif action == "click":
            if not selector:
                return "Error: click requires a selector"
            await page.wait_for_selector(selector, timeout=timeout)
            await page.click(selector)
            await page.wait_for_timeout(500)
            return f"OK: clicked '{selector}'"

        elif action == "click_text":
            if not text:
                return "Error: click_text requires text"
            locator = page.get_by_text(text, exact=False)
            count = await locator.count()
            if count == 0:
                return f"Error: no element with text '{text}'"
            await locator.first.click(timeout=timeout)
            await page.wait_for_timeout(500)
            return f"OK: clicked '{text}' ({count} matches, used first)"

        elif action == "type":
            if not selector or text is None:
                return "Error: type requires selector and text"
            await page.wait_for_selector(selector, timeout=timeout)
            await page.fill(selector, text)
            return f"OK: typed into '{selector}'"

        elif action == "read":
            content = await page.inner_text("body")
            if len(content) > 8000:
                content = content[:8000] + "\n[truncated — use dom or evaluate for more]"
            return f"URL: {page.url}\n\n{content}"

        elif action == "dom":
            if not js:
                js = """
                ({
                    title: document.title,
                    url: location.href,
                    links: Array.from(document.querySelectorAll('a[href]'))
                        .slice(0, 30)
                        .map(a => ({text: a.innerText.trim().slice(0,80), href: a.href}))
                        .filter(a => a.text),
                    asins: Array.from(document.querySelectorAll('[data-asin]'))
                        .map(el => ({
                            asin: el.getAttribute('data-asin'),
                            title: el.querySelector('h2 a span, h1')?.innerText?.trim(),
                            price: el.querySelector('.a-price .a-offscreen')?.innerText
                        }))
                        .filter(x => x.asin && x.asin.length > 0),
                    inputs: Array.from(document.querySelectorAll('input, textarea, select'))
                        .map(el => ({tag: el.tagName, name: el.name, id: el.id, placeholder: el.placeholder, type: el.type}))
                        .filter(el => el.name || el.id),
                    buttons: Array.from(document.querySelectorAll('button, input[type=submit], input[type=button]'))
                        .map(el => ({id: el.id, text: (el.innerText || el.value || '').trim().slice(0,60)}))
                        .filter(el => el.text || el.id)
                        .slice(0, 20)
                })
                """
            result = await page.evaluate(js)
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif action == "evaluate":
            if not js:
                return "Error: evaluate requires js"
            result = await page.evaluate(js)
            return json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result

        elif action == "screenshot":
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = os.path.join(ARTIFACTS_DIR, f"browser-{session}-{ts}.png")
            await page.screenshot(path=path)
            return f"Screenshot saved: {path}"

        elif action == "scroll":
            direction = (text or "down").lower()
            if direction == "top":
                await page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "up":
                await page.evaluate("window.scrollBy(0, -600)")
            else:
                await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(300)
            return f"OK: scrolled {direction}"

        elif action == "wait":
            if selector:
                await page.wait_for_selector(selector, timeout=timeout)
                return f"OK: '{selector}' is visible"
            else:
                ms = int(text) if text and text.isdigit() else 2000
                await page.wait_for_timeout(ms)
                return f"OK: waited {ms}ms"

        elif action == "url":
            return page.url

        elif action == "close":
            if session in _sessions:
                await _sessions[session]["browser"].close()
                await _sessions[session]["pw"].stop()
                del _sessions[session]
            return f"OK: session '{session}' closed"

        else:
            return (
                f"Error: unknown action '{action}'. "
                "Valid: navigate, click, click_text, type, read, dom, evaluate, "
                "screenshot, scroll, wait, url, close"
            )

    except Exception as e:
        return f"Error ({action}): {e}"


tool = {
    "name": "browser",
    "description": (
        "General-purpose web browser automation using real Chrome. "
        "Actions: navigate(url), click(selector), click_text(text), type(selector,text), "
        "read() page text, dom() structured extraction, evaluate(js), screenshot(), "
        "scroll(text=up/down/top/bottom), wait(selector or text=ms), url(), close(). "
        "Supports named sessions for multiple simultaneous browsers. "
        "Use this for all web tasks — it handles Google, Amazon, and sites with bot detection."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform",
                "enum": ["navigate", "click", "click_text", "type", "read", "dom",
                         "evaluate", "screenshot", "scroll", "wait", "url", "close"],
            },
            "url": {"type": "string", "description": "URL to navigate to"},
            "selector": {"type": "string", "description": "CSS selector for click, type, wait"},
            "text": {
                "type": "string",
                "description": "Text to type, text to click, scroll direction, or ms to wait",
            },
            "js": {"type": "string", "description": "JavaScript to evaluate"},
            "wait_for": {"type": "string", "description": "CSS selector to wait for after navigate"},
            "timeout": {"type": "integer", "description": "Timeout in ms (default 15000)"},
            "session": {
                "type": "string",
                "description": "Session name (default: 'default'). Use different names for multiple browsers.",
            },
        },
        "required": ["action"],
    },
    "execute": execute,
}
