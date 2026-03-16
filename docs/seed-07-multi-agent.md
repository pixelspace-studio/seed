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
                    │  │  actor loop │  │  actor loop  │      │
                    │  │  session    │  │  session     │      │
                    │  │  queue      │  │  queue       │      │
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
- Message queue (one queue per agent, fed by humans, other agents, crons)
- Actor loop (permanent `asyncio.Task` — always alive, drains queue)
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
class AgentMessage:
    text: str
    source: str                          # "human", "agent:buscador", "cron:daily"
    response_future: asyncio.Future = None  # set when caller wants to await

@dataclass
class AgentState:
    name: str
    agent_dir: str
    data_dir: str
    session: Session
    queue: asyncio.Queue          # one queue, all sources
    interrupt: asyncio.Event
    status: dict                  # {"state": "idle"} | {"state": "working"}
    model: str
    _loop_task: asyncio.Task = None  # the permanent actor loop

# On startup — discover agents + start actor loops
agents: dict[str, AgentState] = {}
for agent_dir in glob("agents/*/identity.md"):
    name = agent_dir.parent.name
    if name == "shared":
        continue
    agents[name] = AgentState(...)
    start_agent_loop(agents[name], registry, event_sink)
```

---

## API: Agent-Scoped Endpoints

```
POST /agents/semillita/message        # await_response=true (default) blocks until done
POST /agents/semillita/message        # await_response=false returns {"queued": true}
POST /agents/researcher/message
GET  /agents/semillita/status
GET  /agents                          # list all agents
```

All messages go through `/message`. The `await_response` flag controls whether the caller blocks or fires-and-forgets.

---

## Inter-Agent Communication

Each agent is a permanent actor (always-alive `asyncio.Task`). Messages from any source — human, other agents, crons — go into the agent's queue. The actor loop processes them one at a time.

### Tool: `send_message`

```python
async def execute(agent: str, message: str) -> str:
    """Send a message to another agent."""
    target = agents.get(agent)
    if not target:
        return f"Unknown agent: {agent}"

    caller = get_active_agent()
    source = f"agent:{caller.name}" if caller else "agent"
    await target.queue.put(AgentMessage(text=message, source=source))
    return f"Message sent to {agent}"
```

Fire-and-forget — the message lands in the target's queue and the target's actor loop picks it up. The `source` field tells the receiver who sent it.

### How it works in practice

```
User → semillita: "research the best chess engines and summarize"

semillita thinks: "I'll ask the researcher agent to do this"

semillita → send_message(agent="researcher", message="Find the top 5 chess engines...")

researcher's queue receives the AgentMessage
researcher's actor loop wakes up, starts working (web_search, web_fetch, etc.)
researcher → send_message(agent="semillita", message="Here are the top 5: ...")

semillita's queue receives the response
semillita's actor loop processes it on the next cycle
semillita → respond to user with the summary
```

### Why this works
- Each agent has a permanent actor loop — always alive, always listening
- One queue per agent, one consumer — messages are processed in order
- `AgentMessage` unifies all sources: human, agent, cron, webhook
- `response_future` enables blocking (HTTP) or fire-and-forget (agent-to-agent)
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
    caller = get_active_agent()
    source = f"agent:{caller.name}" if caller else "agent"
    for name, agent in agents.items():
        if name != caller.name:
            await agent.queue.put(AgentMessage(text=message, source=source))
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
| Lifecycle (always-alive agents) | Done (core/lifecycle.py — permanent asyncio.Task per agent) |
| Unified message queue | Done (AgentMessage → agent.queue) |
| Source tracking on messages | Done (source field in AgentMessage) |
| Multiple agent instances | Done (discover_agents + start_agent_loop at startup) |
| Inter-agent communication tool | Done (send_message — fire-and-forget via queue) |
| Agent-scoped API endpoints | Done (/agents/{name}/message, status, history, interrupt, model) |
| CLI multi-agent support | Done (/agent command — switch, list, create) |
| Runtime agent creation | Done (create_agent tool + POST /agents/{name}/create) |
| Fire-and-forget messaging | Done (await_response=false on /message) |
