# Seed — Code Review (March 15, 2026)

Full architecture and code review of Semillita v0.1.0 at commit `e595ea3` (38 commits on develop).

---

## Architecture Overview

Semillita is a minimal, self-building AI agent built on a ~500-line Python kernel. FastAPI server with an async event loop that executes tools and persists conversation to JSONL.

```
Seed-01/
├── main.py              # FastAPI server
├── loop.py              # Agent loop (~140 lines) — the kernel
├── provider.py          # Multi-provider routing (Anthropic, OpenAI, Google)
├── registry.py          # Tool discovery and hot-reload
├── session.py           # JSONL conversation history + sliding context window
├── config.py            # Configuration from .env + models.json
├── cli.py               # TUI client (prompt_toolkit + WebSocket streaming)
├── seed.sh              # Install, start, stop, update lifecycle
├── models.json          # Model registry with capabilities and context sizes
├── prompt.md            # System prompt (Semillita's identity)
├── VERSION              # Semver (0.1.0)
├── core_tools/          # Protected core tools (agent can't modify)
│   ├── bash.py          # Shell execution with audit logging
│   ├── read_file.py     # File reading with binary detection
│   ├── write_file.py    # File writing with protection rules
│   ├── respond.py       # User messaging
│   ├── browser.py       # Playwright + real Chrome automation
│   ├── computer.py      # Mac desktop control (PyAutoGUI + AppleScript)
│   ├── vision.py        # Image analysis (Anthropic/OpenAI)
│   ├── web_search.py    # Brave Search API
│   ├── web_fetch.py     # URL fetching
│   ├── switch_model.py  # Runtime model switching with persistence
│   └── set_config.py    # Runtime config changes
├── tools/               # Self-built tools (agent creates these)
├── data/                # Runtime: history.jsonl, audit.jsonl, .model, artifacts/
└── docs/                # Design documents
```

---

## What Works Well

1. **Simplicity.** The entire kernel is ~500 lines. Easy to understand and modify.
2. **Self-building.** Agent writes Python files to `tools/`, hot-reload picks them up. Elegant.
3. **Multi-provider.** Anthropic, OpenAI, Google behind one `send()` function.
4. **JSONL persistence.** Append-only, crash-safe. Sliding context window is smart.
5. **Tool system.** Each tool is a module with `tool` dict + `execute` coroutine. Clean plugin pattern.
6. **Real Chrome.** Browser tool connects to actual Chrome via CDP, not headless.
7. **CLI.** Kitty keyboard protocol, Shift+Enter for newline, ESC to interrupt, WebSocket event streaming.

---

## Bugs and Issues

### Critical

| Issue | File | Details |
|---|---|---|
| `shell=True` injection risk | `bash.py:38` | Uses `create_subprocess_shell()`. Metacharacters like `;` can chain commands. Should use shlex. |
| browser.py incomplete | `browser.py` | Execute function body is disconnected from parameter definitions. Tool is broken. |
| Hard-coded `max_tokens=8192` | `provider.py:138` | All providers capped at 8KB output regardless of model capability. |

### Medium

| Issue | File | Details |
|---|---|---|
| write_file changelog bug | `write_file.py:39` | Checks `os.path.exists()` after writing — always logs "modified", never "created". |
| `is_working` race condition | `cli.py` | WebSocket event and HTTP response can arrive out of order, desyncing state. |
| No API key validation on model switch | `switch_model.py` | Switching to GPT doesn't check if `OPENAI_API_KEY` exists. Fails later. |
| Reload flag race condition | `loop.py:72-76` | File-based IPC — flag can be written between check and delete. |
| No version pinning | `requirements.txt` | `anthropic`, `openai`, `google-genai` could break on major updates. |

### Low

| Issue | File | Details |
|---|---|---|
| Token estimation heuristic | `session.py:39` | `len(json.dumps(m)) / 4` is rough. Can underestimate code-heavy messages. |
| Binary detection naive | `read_file.py:23` | Only checks null bytes in first 1024 bytes. |
| Symlinks can bypass protected paths | `config.py:50` | `os.path.relpath()` doesn't resolve symlinks. |
| Regex HTML stripping | `web_fetch.py:41` | `<[^>]+>` doesn't handle malformed HTML or CDATA. |

---

## File-by-File Quality

| File | Lines | Grade | Notes |
|---|---|---|---|
| loop.py | 140 | A | Clean state machine. Reload flag race is the only issue. |
| provider.py | 365 | A- | Good abstraction. Hard-coded max_tokens and error handling asymmetry (Google catches generic Exception). |
| registry.py | 96 | B+ | Simple plugin system. Silences tool loading errors. |
| session.py | 97 | A | Solid JSONL + sliding window. Token estimation could improve. |
| config.py | 75 | B+ | Clean. Symlink vulnerability in `is_protected()`. |
| cli.py | 501 | B+ | Sophisticated TUI. Race condition on `is_working`. Some threading that could be pure async. |
| bash.py | 95 | C+ | `shell=True` is dangerous. Good audit logging though. |
| read_file.py | 71 | B | Works. No whitelist, naive binary detection. |
| write_file.py | 69 | B | Protected paths help. Changelog bug. |
| browser.py | 378 | D | Incomplete execute function. Stale session handling. |
| computer.py | 102 | B- | Works. No bounds checking, no success verification. |
| vision.py | 194 | B | Multi-provider. Fragile fallback logic, hard-coded max_tokens. |
| web_search.py | 67 | B- | Works. No key validation until request time. |
| web_fetch.py | 74 | B | Works. Naive HTML parsing. |
| switch_model.py | 87 | B+ | Clean. No API key validation. |
| set_config.py | 58 | A- | Clean whitelist approach. |

---

## Security Summary

1. **bash.py `shell=True`** — highest risk. Agent can chain arbitrary commands.
2. **read_file.py** — no whitelist. Can read any file the process has access to.
3. **write_file.py** — no confirmation. Protected paths help but don't cover everything.
4. **browser.py JavaScript eval** — low risk (read-only context) but could be exploited.
5. **API keys** — .env is gitignored (good), but keys were briefly exposed in git history.

---

## Architectural Patterns

**Good:**
- Dataclasses for type safety (ToolCall, ProviderResponse)
- JSONL for append-only, crash-safe history
- Async/await throughout the core
- Modular tool design with hot-reload
- Provider abstraction with per-provider message conversion

**Should Improve:**
- File-based IPC (`.reload_flag`) — replace with asyncio.Event
- Threading in CLI for WebSocket — could be pure async
- Bare `except Exception` in multiple places — swallows errors silently
- Hard-coded magic numbers (8192 tokens, 100KB output, 1024 binary check)
- No structured logging — just print and audit.jsonl

---

## Dependency Graph

```
main.py
  ├── config.py (loads .env + models.json)
  ├── registry.py (discovers core_tools/ + tools/)
  ├── session.py (JSONL history)
  └── loop.py
      ├── provider.py → anthropic / openai / google.genai
      └── registry.execute() → individual tools

cli.py → main.py (HTTP + WebSocket client)
seed.sh → main.py (process management)
```

---

## Recommended Fixes (Priority Order)

1. Fix browser.py — complete the execute function
2. Dynamic `max_tokens` per model from models.json
3. Validate API key exists before switching model
4. Fix write_file.py changelog (check before write)
5. Pin dependency versions
6. Replace `.reload_flag` with asyncio.Event
7. Add structured logging
