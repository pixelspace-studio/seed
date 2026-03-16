"""Core tool: web_search — search the internet via Brave Search API."""

import json
import os
import urllib.request
import urllib.parse
import urllib.error

from core.config import config

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")


async def execute(query: str, count: int = 5) -> str:
    api_key = BRAVE_API_KEY or os.getenv("BRAVE_SEARCH_API_KEY", "")
    if not api_key:
        return "Error: BRAVE_SEARCH_API_KEY not set in .env"

    params = urllib.parse.urlencode({"q": query, "count": min(count, 20)})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"

    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} — {e.read().decode()[:200]}"
    except Exception as e:
        return f"Error: {e}"

    results = []
    for item in data.get("web", {}).get("results", [])[:count]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
        })

    if not results:
        return f"No results for: {query}"

    return json.dumps(results, ensure_ascii=False, indent=2)


tool = {
    "name": "web_search",
    "description": "Search the internet using Brave Search. Returns titles, URLs, and descriptions. Use this to find information, documentation, APIs, or anything on the web.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "count": {
                "type": "integer",
                "description": "Number of results (default 5, max 20)",
            },
        },
        "required": ["query"],
    },
    "execute": execute,
}
