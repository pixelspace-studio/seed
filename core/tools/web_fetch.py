"""Core tool: web_fetch — fetch and extract content from a URL."""

import urllib.request
import urllib.error
import re


async def execute(url: str, max_length: int = 10000) -> str:
    if not url:
        return "Error: url is required"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/json,text/plain,*/*",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code}"
    except Exception as e:
        return f"Error: {e}"

    # JSON — return as-is
    if "json" in content_type:
        text = raw.decode("utf-8", errors="replace")
        if len(text) > max_length:
            text = text[:max_length] + "\n[truncated]"
        return text

    # HTML — strip tags, extract text
    if "html" in content_type:
        text = raw.decode("utf-8", errors="replace")
        # Remove script and style blocks
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Strip tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Clean whitespace
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_length:
            text = text[:max_length] + "\n[truncated]"
        return text

    # Plain text or other
    text = raw.decode("utf-8", errors="replace")
    if len(text) > max_length:
        text = text[:max_length] + "\n[truncated]"
    return text


tool = {
    "name": "web_fetch",
    "description": "Fetch a URL and return its content as text. Strips HTML tags automatically. Use this to read web pages, APIs, documentation, or any URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to return (default 10000)",
            },
        },
        "required": ["url"],
    },
    "execute": execute,
}
