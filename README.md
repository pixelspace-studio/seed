# Semillita

**An AI agent that builds itself.**

It starts with 6 tools: bash, read, write, respond, browser, computer. That's it. No plugins, no marketplace, no config files.

When it needs a capability it doesn't have, it creates it. Ask it to post to Slack — it'll build a Slack tool. Ask it to query a database — it'll write a database tool. Each tool is a single Python file, hot-reloaded instantly.

The entire architecture is ~500 lines of Python. A loop, a registry, a provider. If you can't explain a component in one sentence, it's too complex.

## What makes it different

- **No framework.** No SDK. No abstractions. Just a loop with tools.
- **Self-building.** The agent writes its own tools at runtime.
- **The kernel never changes.** The tools always change.
- **Readable.** You can read the entire codebase in 20 minutes.

## Get started

```bash
git clone <repo-url>
cd semillita
pip install -r requirements.txt
```

Create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Start the server:

```bash
python main.py
```

```
  Semillita is awake.
  Working directory: /Users/you/semillita
  Tools: bash, browser, computer, read, respond, write
  Listening on http://localhost:9999
```

Open a second terminal and chat:

```bash
python cli.py chat
```

```
you> who are you?

I am Semillita. I just woke up.
I have 6 tools. I can run commands, read and write files,
browse the web, and control this Mac.
What would you like me to do?
```

## The self-building moment

```
you> create a tool called dice that rolls a random number from 1 to 6

Done. Created tools/dice.py. Want me to roll?

you> yes

🎲 4
```

Semillita wrote a Python file, the registry hot-reloaded it, and she used it — all in one conversation.

## Project structure

```
semillita/
├── main.py           # FastAPI server — the entry point
├── loop.py           # The agent loop — THE KERNEL (~100 lines)
├── provider.py       # Anthropic API connection
├── registry.py       # Discovers and loads tools
├── session.py        # Conversation history (JSONL)
├── config.py         # Configuration from .env
├── cli.py            # Thin CLI client
├── prompt.md         # System prompt — Semillita's identity
│
├── core_tools/       # Built-in tools (FROZEN — agent can't modify)
│   ├── bash.py       # Run shell commands
│   ├── read_file.py  # Read files with line numbers
│   ├── write_file.py # Write files (with protection rules)
│   ├── respond.py    # Send message back to user
│   ├── browser.py    # Web automation (Playwright)
│   └── computer.py   # Desktop control (PyAutoGUI + AppleScript)
│
├── tools/            # Self-built tools (agent creates these)
│   └── (empty at birth)
│
├── data/             # History, logs, artifacts
│   ├── history.jsonl # Conversation log
│   ├── changelog.md  # Auto-log of self-modifications
│   └── artifacts/    # Screenshots, files created by tasks
│
├── .env              # API keys
└── requirements.txt  # Python dependencies
```

## API

Semillita exposes a simple HTTP API:

| Endpoint | Method | Description |
|---|---|---|
| `/message` | POST | Send a message, get a response |
| `/status` | GET | What is Semillita doing right now |
| `/tools` | GET | List available tools |
| `/history` | GET | Conversation so far |
| `/interrupt` | POST | Stop current task |
| `/stream` | WebSocket | Real-time event stream |

## Tool contract

Every tool — core or self-built — is a single Python file:

```python
async def execute(input: str) -> str:
    return f"Done: {input}"

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
```

One dict. One function. That's it.

## Requirements

- Python 3.11+
- An Anthropic API key
- macOS (for computer tool — everything else is cross-platform)

## Philosophy

The entire system fits in your head. If you can't explain a component in one sentence, it's too complex. Semillita is a loop with tools. Everything else is a client of that loop.

## License

MIT
