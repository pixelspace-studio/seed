# Seed — Roadmap

Living document. Updated March 15, 2026.

The guiding principle: **build the minimum core so Semillita can improve herself.** Every feature we add to core should unlock the agent's ability to do more on her own.

---

## Current deployment model

Semillita runs on a **Mac Mini** as a persistent local agent. Future deployment: a **VM in the cloud** (AWS, Azure, GCP) with the Mac Mini as an operational node via Tailscale.

---

## 1. Fix What's Broken

Before new features, fix the issues from the [code review](seed-05-code-review-2026-03-15.md):

- [ ] Fix browser.py — complete the execute function
- [ ] Dynamic `max_tokens` per model (not hard-coded 8192)
- [ ] Validate API key exists before model switch
- [ ] Fix write_file.py changelog bug
- [ ] Pin dependency versions in requirements.txt
- [ ] Replace `.reload_flag` with asyncio.Event

---

## 2. Browser and Computer Use

The browser and computer tools are the weakest part right now. Without reliable browser and desktop control, the agent is limited to text and code.

### Browser
- Fix the broken execute function in browser.py
- Improve session management (stale session cleanup, port allocation)
- Add cookie/localStorage persistence across calls
- Add skill docs (markdown instructions for the agent on how to use browser effectively)

### Computer Use
- Investigate **Google Gemini's computer use model** — native screen understanding
- Investigate **Anthropic's computer use** (released ~2025) — Claude can see and interact with screens
- Improve PyAutoGUI reliability: bounds checking, success verification, wait-for-result
- Consider replacing custom computer.py with a provider's native computer use if it's good enough

### Goal
The agent should be able to: open a browser, navigate to a site, fill forms, extract data, take screenshots, and interact with desktop apps — reliably.

---

## 3. Gateway and Communication Channels

A gateway system to connect Semillita to the outside world — and the outside world to Semillita.

### Architecture
```
External Channels          Gateway            Semillita
┌──────────────┐      ┌──────────────┐      ┌──────────┐
│  WhatsApp    │─────▶│              │─────▶│          │
│  Slack       │─────▶│   gateway.py │─────▶│  /message│
│  Telegram    │─────▶│              │─────▶│  /inject │
│  Email       │─────▶│  normalize   │      │          │
│  Webhooks    │─────▶│  route       │◀─────│  events  │
└──────────────┘      │  deliver     │      └──────────┘
                      └──────────────┘
```

### Design
- Each channel is a plugin (like tools) — a Python file with `receive()` and `send()`
- Gateway normalizes all incoming messages to `{"text": ..., "source": "whatsapp", "metadata": {...}}`
- Gateway delivers outgoing messages to the right channel based on source
- All channels talk to the existing `/message` and `/inject` endpoints
- Agent can reply to the channel the message came from, or broadcast to multiple

### Channels to implement
- [ ] WhatsApp (via Twilio or WhatsApp Business API)
- [ ] Slack (via Slack Bot API)
- [ ] Telegram (via Bot API — simplest to start with)
- [ ] Email (IMAP/SMTP)
- [ ] Webhooks (generic HTTP callbacks)

---

## 4. Memory System

Current state: sliding context window only. No long-term memory.

### Proposed architecture
```
┌─────────────────────────────────────┐
│           Working Memory            │
│   (sliding context window — today)  │
└──────────────┬──────────────────────┘
               │ summarize + extract
┌──────────────▼──────────────────────┐
│          Episodic Memory            │
│   conversation summaries, events    │
│   "what happened" — timestamped     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│          Semantic Memory            │
│   facts, preferences, knowledge     │
│   "what I know" — structured        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Procedural Memory           │
│   skills, how-tos, patterns         │
│   "how to do things" — executable   │
└─────────────────────────────────────┘
```

### Implementation ideas
- Memory stored as markdown files (like Claude Code's memory system)
- Agent can read/write/search memories via tools
- Auto-summarize conversations on session end
- Relevance-based retrieval: embed + search, or keyword matching
- Keep it file-based — no vector DB dependency for now

---

## 5. Identity and Soul

Current state: single `prompt.md` file in `agents/semillita/`.

### Proposed split
```
agents/semillita/
├── identity.md      # Who is Semillita? Name, personality, values, voice.
├── purpose.md       # What is her mission? What does she care about?
├── boundaries.md    # What she won't do. Safety, ethics, limits.
└── style.md         # How she communicates. Tone, language, formatting.
```

### Design principles
- Minimal. Not 20 files — 3 or 4 at most.
- The agent can read these but not modify them (protected paths).
- Each file is self-contained and independent.
- Inspired by but simpler than OpenAI's "soul" pattern. No corporate bloat.

---

## 6. Skills System

Tools are code (Python functions). Skills are knowledge (markdown instructions on how to use tools effectively).

### Structure
```
core/skills/               # Protected, we maintain
├── browser.md             # How to use browser tool
├── computer.md            # How to use computer tool
└── research.md            # How to search and synthesize info

agents/shared/skills/      # Agent-created, shared between agents
├── coding.md              # Patterns the agent learned
└── communication.md       # How to talk to humans
```

### How it works
- Skills are loaded into system prompt (or injected on demand)
- Agent can create new skills in `agents/shared/skills/`
- Skills reference tools: "when you need to click a button, use the computer tool with action=click"
- Skills are living documents — agent can improve them over time

---

## 7. Multi-Agent System

Current state: one agent, one loop, one session.

### Vision
Multiple specialized agents that can communicate and delegate.

### Architecture options

**Option A: Orchestrator pattern**
```
User → Orchestrator Agent → delegates to:
  ├── Research Agent (web search, reading)
  ├── Coding Agent (bash, files)
  ├── Browser Agent (web automation)
  └── Creative Agent (writing, images)
```

**Option B: Peer network**
```
Agent A ←→ Agent B ←→ Agent C
  Each has own session, tools, identity
  Communicate via message passing (/inject to each other)
```

### Implementation ideas
- Each agent is a separate `loop.py` instance with its own session and registry
- Agents communicate via the existing `/message` and `/inject` endpoints
- Shared tools and skills live in `agents/shared/`
- Each agent's identity lives in `agents/{name}/`
- Start with Option A (simpler) — one orchestrator that spawns sub-loops

---

## 8. ElevenLabs Audio

Voice synthesis for Semillita's responses.

- [ ] `core/tools/speak.py` — send text to ElevenLabs, save audio to `data/files/out/`
- [ ] Voice selection and configuration
- [ ] Streaming audio (play while generating)
- [ ] Integration with gateway (voice messages on WhatsApp/Telegram)

---

## 9. Autonomy: Heartbeat, Scheduler, Calendar, Tasks

Semillita should be able to act on her own — not just respond to messages.

### Heartbeat
- Periodic wake-up (every N minutes) where Semillita checks if there's anything she should do
- Review pending tasks, check calendar, process queued actions
- Configurable interval via `set_config` or `data/.heartbeat`
- Implementation: background async loop in `main.py` that calls `/message` with a system prompt like "check your tasks and calendar"

### Scheduler (Cron-like)
- Schedule actions at specific timestamps: "at 9am tomorrow, send me a summary"
- Persistent schedule stored in `data/schedule.jsonl`
- Agent can create/list/delete scheduled items via a `schedule` tool
- Runner checks schedule on each heartbeat tick

### Calendar
- Simple calendar awareness: knows today's date, can store and query events
- `data/calendar.jsonl` — structured events with date, time, description
- `core/tools/calendar.py` — add, list, search events
- Feeds into heartbeat: "you have a meeting in 30 minutes"

### Tasks
- Persistent task list the agent manages herself
- `data/tasks.jsonl` — structured tasks with status, priority, due date
- `core/tools/tasks.py` — create, update, complete, list tasks
- Agent reviews tasks on heartbeat and can prioritize her own work

---

## 10. MCP (Model Context Protocol)

Two directions:

### MCP Server (others connect to Semillita)
- Expose Semillita's tools and capabilities via MCP
- External agents or applications can use Semillita as a tool provider
- Already have the FastAPI endpoints — MCP is a protocol wrapper

### MCP Client (Semillita connects to external services)
- Connect to external MCP servers (databases, APIs, specialized tools)
- Agent discovers and uses external tools dynamically
- Extends Semillita's capabilities without writing custom tools

---

## 11. CLI Improvements

- [ ] Persistent color scheme (save to `data/.colors`)
- [ ] `/history` command to browse past conversations
- [ ] `/clear` command to start fresh session
- [ ] `/tools` command to list available tools
- [ ] `/status` command showing model, tokens used, uptime
- [ ] Tab completion for commands
- [ ] Markdown rendering in responses (bold, lists, code blocks)

---

## 12. API Completeness

Ensure all agent capabilities are accessible via HTTP:

- [x] POST /message — send message
- [x] POST /inject — inject mid-loop
- [x] POST /interrupt — stop current work
- [x] POST /model — switch model
- [x] GET /status — current state
- [x] GET /tools — list tools
- [x] GET /history — conversation history
- [ ] POST /clear — clear session
- [ ] GET /models — list available models
- [ ] POST /config — update config
- [ ] GET /memory — list memories
- [ ] POST /memory — create memory
- [ ] WebSocket /stream — event stream (exists)

---

## 13. Secrets Management

Current state: API keys in plain text `.env` file. Works but insecure.

### Strategy: cascading resolution

`config.py` resolves each secret in order:
1. **Environment variables** — works everywhere (VMs, Docker, CI)
2. **macOS Keychain** — when running local on Mac (via `keyring` library)
3. **`.env` file** — fallback for development

### Deployment scenarios
- **Mac Mini (today):** `./seed.sh config` saves to Keychain, encrypted with user login
- **Cloud VM (AWS/Azure/GCP):** secrets set as env vars on the VM or via the cloud provider's secret manager (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) — all inject as env vars
- **Development:** `.env` file, gitignored

### Implementation
- [ ] Add `keyring` to requirements.txt
- [ ] Update `config.py` to try env → Keychain → .env
- [ ] Update `seed.sh config` to save to Keychain on macOS
- [ ] Document the resolution chain for cloud deployments

### Alternatives considered
- **1Password CLI** (`op`) — great DX but requires paid subscription
- **Bitwarden** — open source, self-hosteable, but extra setup
- **HashiCorp Vault** — enterprise, overkill for now
- **SOPS/age** — encrypts .env in git, but adds key management complexity

---

## TBD / Far Future

Ideas captured but not prioritized:

- **Web UI** — browser-based chat interface (TBD — CLI is primary)
- **Mobile access** — talk to Semillita from phone (depends on gateway)
- **PaaS deployment** (Render, Railway, Fly) — possible but not priority. VMs are the target.
- **Tool sandboxing** — run agent-created tools in isolated subprocesses
- **Distributed tracing** — structured logging and observability

---

## Priority Order

1. **Fix what's broken** — browser, max_tokens, validations
2. **Browser and computer use** — most impactful for agent capability
3. **Memory system** — enables learning and continuity
4. **Autonomy** — heartbeat, scheduler, calendar, tasks
5. **Identity split** — cleaner soul definition
6. **Skills system** — agent knows how to use her own tools
7. **Gateway** — connects to the world
8. **ElevenLabs** — voice
9. **Multi-agent** — scaling
10. **MCP** — interoperability
11. **Secrets management** — security hardening
12. **CLI + API polish** — ongoing
