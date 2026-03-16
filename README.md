# Semillita

**An AI agent that builds itself.**

It starts with a handful of tools: bash, read, write, respond, browser, computer, vision, web search. No plugins, no marketplace, no config files.

When it needs a capability it doesn't have, it creates it. Ask it to post to Slack — it'll build a Slack tool. Ask it to query a database — it'll write a database tool. Each tool is a single Python file, hot-reloaded instantly.

The entire kernel is ~500 lines of Python. A loop, a registry, a provider. If you can't explain a component in one sentence, it's too complex.

## What makes it different

- **No framework.** No SDK. No abstractions. Just a loop with tools.
- **Self-building.** The agent writes its own tools and skills at runtime.
- **Multi-provider.** Anthropic, OpenAI, Google — switch models mid-conversation.
- **The kernel never changes.** The tools always change.
- **Readable.** You can read the entire codebase in 20 minutes.

## Get started

```bash
git clone https://github.com/pixelspace-studio/seed.git
cd seed
./seed.sh install
./seed.sh config
./seed.sh chat
```

The install script sets up Python, dependencies, and Chrome. The config step asks for your API keys interactively. Then `chat` starts the server and drops you into conversation.

```
Semillita v0.1.0
  Enter = send | Shift+Enter = newline | ESC = interrupt
  Commands: /model, /color, /verbose on|off, exit

> who are you?
  thinking... (iteration 1)

I am Semillita. I just woke up.
I have tools. I can run commands, read and write files,
browse the web, search the internet, and control this Mac.
What would you like me to do?
```

## The self-building moment

```
> create a tool called dice that rolls a random number from 1 to 6

  [write_file] {"path": "tools/dice.py", ...}
  → OK

Done. Created tools/dice.py. Want me to roll?

> yes

4
```

Semillita wrote a Python file, the registry hot-reloaded it, and she used it — all in one conversation.

## Project structure

```
seed/
├── main.py              # FastAPI server — entry point
├── cli.py               # Interactive TUI client
├── seed.sh              # Install, start, stop, update, chat
│
├── core/                # The kernel (~500 lines)
│   ├── loop.py          # Agent loop — the heart
│   ├── provider.py      # Multi-provider routing (Anthropic, OpenAI, Google)
│   ├── registry.py      # Tool discovery and hot-reload
│   ├── session.py       # Conversation history (JSONL + sliding window)
│   └── config.py        # Configuration from .env + models
│
├── core_tools/          # Built-in tools (agent can't modify)
│   ├── bash.py          # Shell commands with audit logging
│   ├── read_file.py     # Read files
│   ├── write_file.py    # Write files (with protection rules)
│   ├── respond.py       # Message the user
│   ├── browser.py       # Web automation (Playwright + real Chrome)
│   ├── computer.py      # Desktop control (PyAutoGUI + AppleScript)
│   ├── vision.py        # Image analysis
│   ├── web_search.py    # Brave Search
│   ├── web_fetch.py     # URL fetching
│   ├── switch_model.py  # Change AI model at runtime
│   └── set_config.py    # Change config at runtime
│
├── tools/               # Self-built tools (agent creates these)
├── skills/              # Knowledge docs (agent creates these)
│
├── agents/
│   └── semillita/
│       └── prompt.md    # System prompt — identity
│
├── registry/
│   └── models.json      # Model registry (capabilities, context windows)
│
├── data/                # Runtime state
│   ├── history.jsonl    # Conversation log
│   ├── audit.jsonl      # Command audit log
│   ├── files/           # in/ out/ temp/
│   └── .model           # Persisted model selection
│
├── docs/                # Design documents and roadmap
├── .env                 # API keys
└── requirements.txt
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/message` | POST | Send a message, get a response |
| `/inject` | POST | Inject a message mid-loop |
| `/interrupt` | POST | Stop current task |
| `/model` | POST | Switch AI model |
| `/status` | GET | Current state and active model |
| `/tools` | GET | List available tools |
| `/history` | GET | Conversation history |
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
- At least one API key (Anthropic, OpenAI, or Google)
- macOS (for computer tool — everything else is cross-platform)

## Philosophy

The entire system fits in your head. If you can't explain a component in one sentence, it's too complex. Semillita is a loop with tools. Everything else is a client of that loop.

## License

MIT
