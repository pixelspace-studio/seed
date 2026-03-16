"""Core tool: browser — general-purpose web automation via Playwright + real Chrome.

Supports multiple named sessions with persistence — sessions survive context
compression and conversation restarts by tracking CDP ports in a JSON file.
On reconnect, Playwright connects to existing Chrome instances via CDP.
"""

import json
import os
import subprocess
from datetime import datetime, timezone

from core.config import config

TEMP_DIR = os.path.join(config.agent_data_dir, "files", "temp")
SESSIONS_FILE = os.path.join(config.agent_data_dir, "browser_sessions.json")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

# Base port for CDP — each session gets base + offset
_CDP_BASE_PORT = 9200

# Active sessions: name -> {pw, browser, context, page, port}
_sessions: dict = {}


def _load_persisted() -> dict:
    """Load persisted session info from disk."""
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted(data: dict):
    """Save session info to disk."""
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    with open(SESSIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _next_port() -> int:
    """Find the next available CDP port."""
    persisted = _load_persisted()
    used_ports = {v["port"] for v in persisted.values()}
    port = _CDP_BASE_PORT
    while port in used_ports:
        port += 1
    return port


def _is_port_alive(port: int) -> bool:
    """Check if something is listening on a port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


async def _get_page(session: str = "default"):
    """Get or create a named browser session. Reconnects to persisted sessions."""
    # Already in memory
    if session in _sessions:
        try:
            # Verify the page is still alive
            await _sessions[session]["page"].title()
            return _sessions[session]["page"]
        except Exception:
            # Dead session in memory — clean up
            try:
                await _sessions[session]["pw"].stop()
            except Exception:
                pass
            del _sessions[session]

    from playwright.async_api import async_playwright

    persisted = _load_persisted()

    # Try to reconnect to a persisted session
    if session in persisted:
        port = persisted[session]["port"]
        if _is_port_alive(port):
            try:
                pw = await async_playwright().start()
                browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                context = browser.contexts[0] if browser.contexts else await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1440, "height": 900},
                )
                page = context.pages[0] if context.pages else await context.new_page()
                _sessions[session] = {"pw": pw, "browser": browser, "context": context, "page": page, "port": port}
                return page
            except Exception:
                # Can't reconnect — remove stale entry
                del persisted[session]
                _save_persisted(persisted)
        else:
            # Port is dead — remove stale entry
            del persisted[session]
            _save_persisted(persisted)

    # Create new session with a dedicated CDP port
    port = _next_port()
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        channel="chrome",
        headless=False,
        args=[f"--remote-debugging-port={port}"],
    )
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1440, "height": 900},
    )
    page = await context.new_page()
    _sessions[session] = {"pw": pw, "browser": browser, "context": context, "page": page, "port": port}

    # Persist
    persisted = _load_persisted()
    persisted[session] = {"port": port}
    _save_persisted(persisted)

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
    os.makedirs(TEMP_DIR, exist_ok=True)

    # tabs doesn't need a page
    if action == "tabs":
        return await _action_tabs()

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
            path = os.path.join(TEMP_DIR, f"browser-{session}-{ts}.png")
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
            persisted = _load_persisted()
            persisted.pop(session, None)
            _save_persisted(persisted)
            return f"OK: session '{session}' closed"

        else:
            return (
                f"Error: unknown action '{action}'. "
                "Valid: navigate, click, click_text, type, read, dom, evaluate, "
                "screenshot, scroll, wait, url, tabs, close"
            )

    except Exception as e:
        return f"Error ({action}): {e}"


async def _action_tabs() -> str:
    """List all tabs from Playwright sessions (in-memory + persisted) and real Chrome."""
    from playwright.async_api import async_playwright

    lines = []
    persisted = _load_persisted()

    # Reconnect to any persisted sessions not yet in memory
    for sname, sinfo in list(persisted.items()):
        if sname not in _sessions:
            port = sinfo["port"]
            if _is_port_alive(port):
                try:
                    pw = await async_playwright().start()
                    browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                    context = browser.contexts[0] if browser.contexts else await browser.new_context()
                    page = context.pages[0] if context.pages else await context.new_page()
                    _sessions[sname] = {"pw": pw, "browser": browser, "context": context, "page": page, "port": port}
                except Exception:
                    # Stale — clean up
                    del persisted[sname]
                    _save_persisted(persisted)
            else:
                del persisted[sname]
                _save_persisted(persisted)

    # List tabs from all in-memory Playwright sessions
    for sname, sdata in _sessions.items():
        try:
            for ctx in sdata["browser"].contexts:
                for p in ctx.pages:
                    try:
                        title = await p.title()
                    except Exception:
                        title = "(unknown)"
                    lines.append(f"[playwright:{sname} port:{sdata.get('port','?')}] {title} | {p.url}")
        except Exception:
            lines.append(f"[playwright:{sname}] (error reading tabs)")

    # List tabs from real Chrome via AppleScript
    try:
        script = (
            'tell application "Google Chrome"\n'
            '  set output to ""\n'
            '  repeat with w from 1 to count of windows\n'
            '    repeat with t from 1 to count of tabs of window w\n'
            '      set tabTitle to title of tab t of window w\n'
            '      set tabURL to URL of tab t of window w\n'
            '      set output to output & "[chrome:window" & w & "] " & tabTitle & " | " & tabURL & linefeed\n'
            '    end repeat\n'
            '  end repeat\n'
            '  return output\n'
            'end tell'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            lines.extend(result.stdout.strip().split("\n"))
    except Exception as e:
        lines.append(f"[chrome] Error querying Chrome via AppleScript: {e}")

    return "\n".join(lines) if lines else "No tabs found"


tool = {
    "name": "browser",
    "description": (
        "General-purpose web browser automation using real Chrome. "
        "Actions: navigate(url), click(selector), click_text(text), type(selector,text), "
        "read() page text, dom() structured extraction, evaluate(js), screenshot(), "
        "scroll(text=up/down/top/bottom), wait(selector or text=ms), url(), "
        "tabs() list all open tabs (Playwright sessions + real Chrome via AppleScript), close(). "
        "Supports named sessions that persist across conversations via CDP ports. "
        "Use this for all web tasks — it handles Google, Amazon, and sites with bot detection."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform",
                "enum": ["navigate", "click", "click_text", "type", "read", "dom",
                         "evaluate", "screenshot", "scroll", "wait", "url", "tabs", "close"],
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
