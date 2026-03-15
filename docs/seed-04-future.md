# Seed — Future Architecture Ideas

Captured during v0.1 development. Not committed to — just ideas worth preserving.

---

## Hybrid Cloud + Local Model

Semillita doesn't have to be monolithic. The architecture could split into:

```
                    ┌─────────────────┐
                    │   CLOUD (Render) │
                    │                  │
                    │  loop.py         │  ← the brain
                    │  provider.py     │
                    │  session.py      │
                    │  registry.py     │
                    │                  │
                    │  tools:          │
                    │    bash          │
                    │    read/write    │
                    │    web_search    │
                    │    web_fetch     │
                    │    browser       │  ← headless, works
                    │    respond       │
                    └────────┬─────────┘
                             │
                    (remote connection)
                             │
                    ┌────────┴─────────┐
                    │   MAC MINI (node) │
                    │                   │
                    │  tools:           │
                    │    computer       │  ← real display
                    │    browser        │  ← visible Chrome
                    └───────────────────┘
```

### Identity

"The real Semillita" is where the session lives — `history.jsonl`, the memory. Not where the tools execute. She is one agent with multiple limbs.

### Technologies to investigate

- **Tailscale** — mesh VPN. Creates a private network between devices (cloud server ↔ Mac Mini ↔ laptop ↔ phone). No port forwarding, no public IPs. Each device gets a stable address like `mac-mini.tailnet`. This would let Semillita's cloud brain reach the Mac Mini's tools securely.

- **Gateway / reverse proxy** — expose Semillita's API (`:9999`) to the internet securely. Options: Tailscale Funnel (simplest), Cloudflare Tunnel, or nginx reverse proxy. Needed for: mobile access, remote CLI, webhook integrations.

- **SSH** — Secure Shell. Direct terminal access to the Mac Mini from anywhere. Already built into macOS. Tailscale makes SSH trivial (no port forwarding).

### Remote access scenarios

1. **Same network (today):** Screen Share + CLI. Works.
2. **Remote, same Tailscale net:** SSH to Mac Mini, run CLI there. Or point CLI's BASE_URL to Mac Mini's Tailscale IP.
3. **Phone / browser:** Need a simple web UI or a Telegram/WhatsApp bot that talks to `/message`. Future.
4. **Full cloud:** Semillita runs on Render, Mac Mini is a node. Future.

---

## Self-Building Safety

Semillita can create tools and modify `prompt.md`. If she breaks something, she currently has no way back.

### Ideas

- **Tool versioning:** Before overwriting `tools/X.py`, copy to `tools/.versions/X-{timestamp}.py`. Automatic backup.
- **Rollback command:** "undo last tool change" — restore from `.versions/`.
- **Test before activate:** After writing a tool, import it in a subprocess first. If it fails to import, don't activate it.
- **Changelog is already there:** `data/changelog.md` logs every modification. Build rollback on top of it.

---

## Web Search Integration

### Brave Search API
- Designed for programmatic use, AI-friendly
- Free tier: 2,000 queries/month
- Returns clean structured results (title, URL, description, snippets)
- No Google account needed, no complex OAuth
- Already implemented in `core_tools/web_search.py`

### Alternatives considered
- **Tavily** — built specifically for AI agents. Returns pre-extracted content, not just links. More expensive but less work per query. Worth evaluating.
- **Exa (formerly Metaphor)** — semantic search, finds content by meaning not keywords. Good for research tasks. Neural approach.
- **Google Custom Search** — powerful but complex setup, requires Google Cloud project.
- **SerpAPI** — Google results via API. Reliable but expensive.

---

## Cloud Deployment (Render)

When ready to deploy to cloud:

- Semillita runs as a Render Web Service (Python)
- `browser` tool works headless (Playwright on Linux)
- `computer` tool is disabled or routed to Mac Mini node
- Session/history could move to Render PostgreSQL or stay as JSONL
- Environment variables managed in Render dashboard

The question is not "if" but "when" — and whether the Mac Mini stays as primary or becomes a node.

---

## Mobile Access

Long-term: talk to Semillita from your phone.

Options (simplest → most complex):
1. **Telegram bot** — Semillita listens for messages via Telegram Bot API, responds via `/message`
2. **WhatsApp via Twilio** — same pattern, different channel
3. **Simple web UI** — single-page chat app, hosted on Render or Mac Mini
4. **iOS Shortcut** — curl to Semillita's API, show response in notification

All of these are thin clients that POST to `/message` — the same API the CLI uses.
