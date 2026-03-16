# Seed — Multi-Agent Architecture

Feature design document. March 15, 2026.

---

## Overview

Multiple agents running in a single FastAPI process, each with their own identity, session, and state — but sharing tools, skills, and the ability to talk to each other.

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              FastAPI (main.py)           │
                    │                                         │
                    │  ┌─────────────┐  ┌─────────────┐      │
                    │  │  semillita  │  │  researcher  │ ...  │
                    │  │             │  │              │      │
                    │  │  loop.py    │  │  loop.py     │      │
                    │  │  session    │  │  session     │      │
                    │  │  inject_q   │  │  inject_q    │      │
                    │  │  interrupt  │  │  interrupt   │      │
                    │  └──────┬──────┘  └──────┬───────┘      │
                    │         │                │              │
                    │         └───── talk ──────┘              │
                    │                                         │
                    │  Shared: registry, tools, skills        │
                    └─────────────────────────────────────────┘
```

### Per-agent (isolated)
- Identity (`agents/{name}/identity.md`)
- Data (`agents/{name}/data/` — history, audit, changelog, files, .model)
- Session (own history.jsonl, own sliding window)
- Inject queue (own message queue)
- Interrupt event (own stop signal)
- Model selection (each agent can use a different model)

### Shared (global)
- Protocol (`agents/shared/protocol.md`)
- Tools (`agents/shared/tools/` + `core/tools/`)
- Skills (`agents/shared/skills/` + `core/skills/`)
- Registry (`registry/models.json`, etc.)
- FastAPI process, event loop, WebSocket broadcast

---

## Agent Definition

Each agent is a folder in `agents/`:

```
agents/
├── shared/
│   ├── protocol.md
│   ├── tools/
│   └── skills/
├── semillita/
│   ├── identity.md
│   └── data/
├── researcher/
│   ├── identity.md
│   └── data/
└── designer/
    ├── identity.md
    └── data/
```

To create a new agent: create a folder with an `identity.md`. That's it. The system discovers agents by scanning `agents/*/identity.md`.

---

## Runtime: Agent Registry

```python
@dataclass
class AgentInstance:
    name: str
    config: Config           # agent-specific config (model, data dir)
    session: Session         # own history
    registry: Registry       # shared tools (same for all)
    inject_queue: asyncio.Queue
    interrupt: asyncio.Event
    status: str = "idle"     # idle | working

# On startup
agents: dict[str, AgentInstance] = {}
for agent_dir in glob("agents/*/identity.md"):
    name = agent_dir.parent.name
    if name == "shared":
        continue
    agents[name] = AgentInstance(...)
```

---

## API: Agent-Scoped Endpoints

Option A — path prefix:
```
POST /agents/semillita/message
POST /agents/researcher/message
POST /agents/semillita/inject
GET  /agents/semillita/status
GET  /agents                          # list all agents
```

Option B — query param:
```
POST /message?agent=semillita
POST /message?agent=researcher
```

Option A is cleaner. Default agent (when path is just `/message`) could be configurable — defaults to `semillita`.

---

## Inter-Agent Communication

Agents talk to each other using the existing inject mechanism:

### Tool: `send_message`

```python
async def execute(agent: str, message: str) -> str:
    """Send a message to another agent."""
    target = agents.get(agent)
    if not target:
        return f"Unknown agent: {agent}"

    await target.inject_queue.put({
        "text": message,
        "source": f"agent:{config.agent_name}",
    })
    return f"Message sent to {agent}"
```

The receiving agent sees it as a regular injected message. The `source` field tells them who sent it.

### How it works in practice

```
User → semillita: "research the best chess engines and summarize"

semillita thinks: "I'll ask the researcher agent to do this"

semillita → send_message(agent="researcher", message="Find the top 5 chess engines...")

researcher's inject_queue receives the message
researcher starts working (web_search, web_fetch, etc.)
researcher → send_message(agent="semillita", message="Here are the top 5: ...")

semillita receives the response in her inject_queue
semillita → respond to user with the summary
```

### No new infrastructure needed
- `inject_queue` already exists and works
- `source` field already distinguishes message origins
- The loop already drains the queue each iteration
- WebSocket events already broadcast to all listeners

---

## CLI: Multi-Agent Interface

The hard question. Options:

### Option 1: Active agent switching

```
Semillita v0.1.0
  Agents: semillita*, researcher, designer

> hello                              # goes to semillita (active)
  thinking...

> /agent researcher                  # switch active agent
  Active agent: researcher

> find me the latest AI papers       # goes to researcher
  thinking...

> /agent semillita                   # switch back
> /agents                            # list all + status
  semillita    idle
  researcher   working (iteration 3)
  designer     idle
```

### Option 2: Prefixed messages

```
> hello                              # goes to default agent
> @researcher find me AI papers      # goes to researcher
> @designer create a logo            # goes to designer
```

### Option 3: Split panes (future)

Multiple prompt_toolkit panes, one per agent. Each shows their own event stream. Way more complex but powerful.

### Recommendation

Start with **Option 1** (active agent switching via `/agent`). Simple, works with existing CLI architecture. Add **Option 2** (@mentions) as sugar later.

The prompt could show the active agent:

```
semillita> hello
researcher> find me papers
```

### WebSocket events

Events already include metadata. Add `agent` field:

```json
{"type": "thinking", "agent": "researcher", "iteration": 1}
{"type": "tool_call", "agent": "researcher", "tool": "web_search", ...}
{"type": "response_complete", "agent": "semillita", "text": "..."}
```

CLI filters events by active agent (or shows all in verbose).

---

## Agent Creation

Two ways to create agents:

### 1. Manual (us)
Create `agents/{name}/identity.md`, restart server.

### 2. Self-created (by an agent)
An agent could create another agent:

```
> semillita, create a researcher agent that specializes in academic papers

semillita → write_file("agents/researcher/identity.md", "...")
semillita → respond("Created researcher agent. Restart to activate.")
```

Hot-loading agents at runtime (without restart) is a future optimization.

---

## System Prompt Composition

Each agent's system prompt is assembled from:

1. `agents/shared/protocol.md` — global rules (same for all)
2. `agents/{name}/identity.md` — who this agent is
3. Relevant skills from `agents/shared/skills/` and `core/skills/` (injected on demand)

---

## Orchestration Patterns

### Direct delegation
One agent explicitly asks another for help via `send_message`.

### Broadcast
An agent sends a message to all agents:
```python
async def execute(message: str) -> str:
    for name, agent in agents.items():
        if name != config.agent_name:
            await agent.inject_queue.put({"text": message, "source": f"agent:{config.agent_name}"})
```

### Pipeline
Chain agents: user → researcher → analyst → writer → user.
Each agent sends their output to the next via `send_message`.

### Autonomous collaboration
Combined with heartbeat: agents wake up periodically, check if other agents left them messages, and act on them.

---

## Implementation Order

1. **Agent discovery** — scan `agents/*/identity.md` on startup
2. **Agent-scoped state** — per-agent session, queue, interrupt (mostly done via `config.agent_data_dir`)
3. **API routing** — `/agents/{name}/message` endpoints
4. **`send_message` tool** — inter-agent communication
5. **CLI `/agent` command** — switch active agent
6. **CLI prompt update** — show active agent name
7. **WebSocket agent field** — filter events by agent

---

## What We Already Have

| Capability | Status |
|---|---|
| Per-agent data directories | Done (agents/{name}/data/) |
| Per-agent identity | Done (agents/{name}/identity.md) |
| Shared protocol | Done (agents/shared/protocol.md) |
| Shared tools and skills | Done (agents/shared/) |
| Inject queue (message passing) | Done (used for user inject) |
| Source tracking on messages | Done (source field) |
| Agent-scoped config | Done (config.agent_name, agent_dir, agent_data_dir) |
| Multiple agent instances | Not yet (main.py hardcodes one) |
| Inter-agent communication tool | Not yet |
| Agent-scoped API endpoints | Not yet |
| CLI multi-agent support | Not yet |

The foundation is in place. The remaining work is in `main.py` (instantiation) and `cli.py` (UI).
