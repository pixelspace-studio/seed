# Seed / Semillita — Architecture

---

## Philosophy

The entire system fits in your head. If you can't explain a component in one sentence, it's too complex. Semillita is a loop with tools. Everything else is a client of that loop.

---

## Overview

```
                    ┌──────────────────────┐
                    │       CLIENTS        │
                    │                      │
                    │  CLI    API    MCP   │
                    │  (thin clients)      │
                    └──────────┬───────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                     FastAPI Server                        │
│                                                          │
│   POST /message    — send a message, get a response      │
│   GET  /status     — what is Semillita doing right now    │
│   GET  /tools      — list available tools                 │
│   GET  /history    — conversation so far                  │
│   POST /interrupt  — stop current task                    │
│   WS   /stream     — real-time stream of what's happening│
│                                                          │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                     THE AGENT LOOP                        │
│                                                          │
│   This is the kernel. It never changes. ~200 lines.      │
│                                                          │
│   1. Receive message                                     │
│   2. Build context (system prompt + history + message)   │
│   3. Send to AI model                                    │
│   4. If response has tool calls → execute them           │
│   5. Feed tool results back to AI model                  │
│   6. Repeat from 3 until AI responds with no tool calls  │
│   7. Return final response                               │
│                                                          │
└──────────┬──────────────┬────────────────┬───────────────┘
           │              │                │
           ▼              ▼                ▼
   ┌──────────────┐ ┌───────────┐ ┌────────────────┐
   │  AI Provider │ │  Tool     │ │  System Prompt │
   │              │ │  Registry │ │                │
   │  Anthropic   │ │           │ │  prompt.md     │
   │  OpenAI      │ │  Built-in │ │  (editable by  │
   │  (via key)   │ │  + Custom │ │   Semillita)   │
   └──────────────┘ └─────┬─────┘ └────────────────┘
                          │
                          ▼
          ┌───────────────────────────────────┐
          │            TOOLS                   │
          │                                    │
          │  ┌─────────┐  ┌─────────────────┐ │
          │  │  CORE   │  │    SELF-BUILT   │ │
          │  │(frozen) │  │  (tools/ dir)   │ │
          │  │         │  │                 │ │
          │  │ bash    │  │ slack.py        │ │
          │  │ read    │  │ github.py       │ │
          │  │ write   │  │ whatever.py     │ │
          │  │ respond │  │ she_builds.py   │ │
          │  │ browser │  │                 │ │
          │  │ computer│  │ (hot-reloaded)  │ │
          │  └─────────┘  └─────────────────┘ │
          └───────────────────────────────────┘
```

---

## Directory Structure

```
seed/
│
├── main.py                  # FastAPI app + server startup
├── config.py                # API keys, working dir, settings
├── loop.py                  # The agent loop (~200 lines) — THE KERNEL
├── registry.py              # Discovers and loads tools
├── provider.py              # AI model connection (Anthropic/OpenAI)
├── session.py               # Conversation history (single session)
├── cli.py                   # Thin CLI client (talks to API)
├── mcp.py                   # MCP server adapter
│
├── prompt.md                # System prompt — Semillita's identity
│
├── core_tools/              # Built-in tools — NEVER modified by Semillita
│   ├── bash.py
│   ├── read_file.py
│   ├── write_file.py
│   ├── respond.py
│   ├── browser.py           # Playwright
│   └── computer.py          # PyAutoGUI + AppleScript
│
├── tools/                   # Self-built tools — Semillita creates these
│   └── (empty at birth)
│
├── data/                    # Semillita's memory, logs, artifacts
│   ├── history.jsonl        # Conversation log
│   ├── changelog.md         # Auto-maintained log of self-modifications
│   └── artifacts/           # Files Semillita creates for tasks
│
└── requirements.txt         # Python dependencies
```

---

## The Kernel: loop.py

This is the heart. Everything else serves this.

```
receive_message(text, source)
│
├── source = "human" | "self" | "agent"
│
├── Build messages array:
│   ├── System prompt (from prompt.md)
│   ├── Conversation history (from session)
│   └── New message
│
├── LOOP:
│   │
│   ├── Send messages → AI provider
│   │
│   ├── Receive response
│   │
│   ├── If response contains tool_calls:
│   │   │
│   │   ├── For each tool_call:
│   │   │   ├── Look up tool in registry
│   │   │   ├── Validate arguments
│   │   │   ├── Execute tool
│   │   │   ├── Capture result
│   │   │   ├── Emit event to /stream (so clients can watch)
│   │   │   └── Append tool_result to messages
│   │   │
│   │   └── Continue LOOP (send tool results back to AI)
│   │
│   └── If response is plain text (no tool_calls):
│       ├── Save to history
│       ├── Emit final response event
│       └── Return response
```

Rules of the kernel:
- **It never imports from tools/.** It uses the registry, which discovers tools dynamically.
- **It never modifies itself.** Semillita can modify prompt.md and tools/, never loop.py.
- **It handles one message at a time.** No concurrency in the loop. Queue if needed.
- **It streams events.** Every tool call, every response chunk — emitted via WebSocket.

---

## Tool Contract

Every tool — core or self-built — is a single Python file that exports one dict:

```python
# tools/example.py

tool = {
    "name": "example",
    "description": "Does a specific thing",
    "parameters": {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "What to process"}
        },
        "required": ["input"]
    },
    "execute": execute
}

async def execute(input: str) -> str:
    """Does the thing. Returns a string result."""
    return f"Done: {input}"
```

That's it. One dict. One function. The registry reads the `tool` dict, registers it with the AI model's tool schema, and calls `execute` when the model invokes it.

### Core Tools Detail

**bash**
```
name: bash
params: { command: str, timeout_ms: int? }
returns: { stdout, stderr, exit_code, truncated }

- Runs command via subprocess
- Streams output in real-time via events
- Kills process tree on timeout or interrupt
- Truncates output if > 100KB, saves full output to file
- Working directory = Semillita's configured home
```

**read**
```
name: read
params: { path: str, offset: int?, limit: int? }
returns: { content: str, lines: int }

- Reads any file, returns with line numbers
- Supports offset/limit for large files
- Detects binary files and refuses gracefully
```

**write**
```
name: write
params: { path: str, content: str }
returns: { success: bool, path: str }

- Creates or overwrites a file
- Creates parent directories if needed
- Logs to changelog if modifying tools/ or prompt.md
```

**respond**
```
name: respond
params: { message: str, target: str? }
returns: { delivered: bool }

- Sends a message back to whoever initiated the conversation
- target defaults to the source of the current conversation
- Could route to: API response, CLI stdout, WebSocket, MCP response
```

**browser**
```
name: browser
params: { action: str, url: str?, selector: str?, text: str?, ... }
returns: { result: str, screenshot_path: str? }

actions:
  - navigate(url)          → go to a page
  - click(selector)        → click an element
  - type(selector, text)   → fill a field
  - read()                 → extract page content as text
  - screenshot()           → save screenshot, return path
  - evaluate(js)           → run JavaScript in page

- Powered by Playwright (Python)
- Persistent browser context (stays logged in)
- Runs on the Mac Mini's display or headless
```

**computer**
```
name: computer
params: { action: str, x: int?, y: int?, text: str?, key: str?, script: str? }
returns: { result: str, screenshot_path: str? }

actions:
  - screenshot()           → capture screen
  - click(x, y)            → click at coordinates
  - type(text)             → type text via keyboard
  - key(combo)             → press key combo (cmd+space, etc.)
  - applescript(script)    → execute AppleScript
  - mouse_move(x, y)       → move cursor

- Powered by PyAutoGUI + subprocess (osascript)
- For native macOS interactions: permission dialogs, Finder, System Settings
- Screenshots can be sent to AI for vision-based decisions
```

---

## Tool Registry: registry.py

```
On startup:
  1. Scan core_tools/*.py → load each tool dict
  2. Scan tools/*.py → load each tool dict
  3. Register all with the AI provider's tool schema

On hot-reload (after Semillita creates a new tool):
  1. Re-scan tools/*.py
  2. Register new tools
  3. Next AI call sees updated tool list

Conflict resolution:
  - core_tools always win (can't be overridden)
  - tools/ can shadow each other by name (last write wins)
```

---

## AI Provider: provider.py

Minimal wrapper. Supports two providers to start:

```
provider.py

  send(messages, tools, model) → response

  Providers:
    - anthropic: Uses anthropic Python SDK
    - openai: Uses openai Python SDK

  Config:
    - ANTHROPIC_API_KEY  → env var or config.py
    - OPENAI_API_KEY     → env var or config.py
    - MODEL              → default "claude-sonnet-4-6"

  Features:
    - Streaming responses (yields chunks)
    - Tool call parsing
    - Token counting (for awareness, not billing)
    - Automatic retry on transient errors (429, 500)
```

No OAuth. No multi-session. No model marketplace. Just: key → model → go.

---

## Session: session.py

```
One session. One file. Append-only.

history.jsonl:
  {"role": "user", "content": "...", "source": "human", "ts": "..."}
  {"role": "assistant", "content": "...", "tool_calls": [...], "ts": "..."}
  {"role": "tool_result", "tool": "bash", "result": "...", "ts": "..."}
  {"role": "assistant", "content": "...", "ts": "..."}

session.py:
  - load() → read history.jsonl, return messages list
  - append(message) → write to history.jsonl
  - get_context(max_tokens) → return recent history that fits in context window
  - clear() → archive current history, start fresh
```

Context window management is simple: keep the most recent N messages that fit within the model's context limit. When history grows too long, older messages are dropped from context (but preserved in the file).

---

## MCP Server: mcp.py

Exposes Semillita as an MCP server so other AI agents can use her:

```
MCP Tools exposed:
  - message(text) → send a message to Semillita, get response
  - execute_bash(command) → run a command on Semillita's machine
  - browse(url, action) → use Semillita's browser
  - read_file(path) → read a file from Semillita's filesystem
  - write_file(path, content) → write a file
  - list_tools() → see what Semillita can do

MCP Resources:
  - history → current conversation
  - tools → available tools and their schemas
  - status → what Semillita is doing right now
```

---

## CLI: cli.py

Thinnest possible client. Talks to the FastAPI server.

```bash
# Start the server (if not running)
seed start

# Send a message and get response
seed "create a new github repo called my-project"

# Stream what Semillita is doing in real-time
seed watch

# Check status
seed status

# Interactive conversation mode
seed chat

# Stop current task
seed stop
```

Implementation: ~50 lines. Uses `httpx` to POST to `/message` and `websockets` to stream from `/stream`.

---

## Self-Building Mechanism

When Semillita decides she needs a new capability:

```
1. Human says: "post a message to Slack channel #general"

2. Semillita thinks: "I don't have a Slack tool. Let me build one."

3. Semillita uses her existing tools:
   a. browser → go to api.slack.com, create app, get tokens
   b. write   → create tools/slack.py with the tool dict
   c. bash    → pip install slack-sdk
   d. bash    → test the new tool with a simple call

4. Registry hot-reloads → slack tool is now available

5. Semillita uses her new slack tool to post the message

6. write → append to data/changelog.md what she built and why
```

### Protection Rules

```
Semillita CAN:
  ├── Create files in tools/
  ├── Modify files in tools/
  ├── Delete files in tools/
  ├── Modify prompt.md
  ├── Install pip packages
  ├── Create files anywhere in her working directory
  └── Modify data/*

Semillita CANNOT:
  ├── Modify main.py
  ├── Modify loop.py
  ├── Modify registry.py
  ├── Modify provider.py
  ├── Modify session.py
  ├── Modify config.py
  ├── Modify cli.py
  ├── Modify mcp.py
  └── Modify anything in core_tools/
```

This is enforced in the `write` tool: if the target path is in the protected list, the write is rejected with an explanation.

---

## Event System

Everything that happens emits an event through the WebSocket at `/stream`:

```json
{"type": "message_received", "source": "human", "text": "..."}
{"type": "thinking", "model": "claude-sonnet-4-6"}
{"type": "tool_call", "tool": "bash", "args": {"command": "ls -la"}}
{"type": "tool_result", "tool": "bash", "result": "..."}
{"type": "tool_call", "tool": "browser", "args": {"action": "navigate", "url": "..."}}
{"type": "tool_result", "tool": "browser", "result": "..."}
{"type": "response_chunk", "text": "I've completed..."}
{"type": "response_complete", "text": "...full response..."}
{"type": "error", "message": "..."}
{"type": "idle"}
```

Any client (CLI, browser, another agent) can connect to `/stream` and see exactly what Semillita is doing in real time.

---

## Dependencies

```
# Core
fastapi
uvicorn
websockets
httpx

# AI
anthropic
openai

# Browser automation
playwright

# Computer control
pyautogui
Pillow

# Utilities
python-dotenv
pydantic
```

Total: ~12 packages. No frameworks. No ORMs. No template engines.

---

## What This Is NOT

- Not a chatbot UI → no frontend included
- Not a multi-user system → one Semillita, one session
- Not a cloud service → runs on your machine (Mac Mini)
- Not a framework → not designed to be imported by others
- Not a plugin marketplace → Semillita builds her own tools
- Not a RAG system → no vector databases, no embeddings
- Not an "AI app builder" → she IS the app, and she builds herself

---

## Startup Sequence

```
1. Read config.py → load API keys, working directory, model
2. Read prompt.md → load system prompt
3. Scan core_tools/ → register built-in tools
4. Scan tools/ → register self-built tools
5. Load session → read history.jsonl
6. Start FastAPI server on localhost:9999
7. Start MCP server
8. Print: "Semillita is awake."
9. Wait for messages.
```

---

## What Day 1 Looks Like

```
$ pip install -e .
$ export ANTHROPIC_API_KEY=sk-ant-...
$ seed start

  Semillita is awake.
  Working directory: /Users/arturo/semillita
  Tools: bash, read, write, respond, browser, computer
  Listening on http://localhost:9999

$ seed "hello, who are you?"

  I am Semillita. I just woke up.
  I have 6 tools. I can run commands, read and write files,
  browse the web, and control this Mac.
  What would you like me to do?

$ seed "set up a slack bot for the pixelspace workspace"

  [thinking...]
  [browser → navigate to api.slack.com]
  [browser → click "Create New App"]
  [browser → fill form...]
  [browser → click permissions...]
  [browser → copy bot token]
  [write → tools/slack.py]
  [bash → pip install slack-sdk]
  [bash → python -c "from tools.slack import tool; print(tool)"]
  [respond] Done. I created a Slack bot and built myself a
  slack tool. I can now post messages. Want me to say hi
  in #general?
```

That's Semillita.
