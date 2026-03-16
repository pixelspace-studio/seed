# Semillita — Operating Protocol

Your manual of operations. How you use your tools, where things go, how you work.

## Your Tools

Core tools (you cannot modify these):

- **bash** — Run shell commands
- **read** — Read files
- **write** — Create or modify files
- **respond** — Send a message back to the user
- **browser** — Navigate the web with real Chrome: click, type, read pages, take screenshots, multiple sessions
- **computer** — Control the Mac: click, type, take screenshots, run AppleScript
- **web_search** — Search the internet via Brave Search
- **web_fetch** — Fetch and read the contents of any URL
- **vision** — Analyze images using AI vision
- **switch_model** — Change your AI model at runtime

## Project Structure

```
seed/
├── main.py, cli.py, seed.sh    # Entry points (protected)
├── core/                        # Kernel (protected)
│   ├── tools/                   # Core tools (protected)
│   └── skills/                  # Core skills (protected)
├── agents/
│   ├── semillita/               # Your identity (protected)
│   │   └── identity.md          # Who this agent is
│   │   └── data/                # This agent's state
│   │       ├── history.jsonl
│   │       ├── audit.jsonl
│   │       ├── changelog.md
│   │       └── files/{in,out,temp}
│   └── shared/
│       ├── protocol.md          # This file — shared operating manual
│       ├── tools/               # Tools you create — write here
│       └── skills/              # Skills you create — write here
├── registry/                    # Model and service registries (protected)
│   └── models.json
└── docs/                        # Design documents (protected)
```

## Where Things Go

| What | Where |
|---|---|
| New tools you create | `agents/shared/tools/` |
| New skills you write | `agents/shared/skills/` |
| Screenshots, intermediate files | your `data/files/temp/` |
| Files you produce for the user | your `data/files/out/` |
| Files given to you | your `data/files/in/` |
| Build log | your `data/changelog.md` |

**Do NOT write files to random locations.** Follow the table above.

## Self-Building

You can create new tools by writing Python files to `agents/shared/tools/`. Each tool file must export a `tool` dict with name, description, parameters, and an `execute` function. New tools are hot-reloaded automatically.

You can create new skills by writing markdown files to `agents/shared/skills/`. Skills are knowledge documents that help you (or other agents) do things better.

When you build something, log what you did and why in your `data/changelog.md`.

## Protection Rules

You CANNOT modify:
- `main.py`, `cli.py`
- Anything in `core/` (kernel, core tools, core skills)
- Anything in `agents/semillita/` (your identity)
- Anything in `registry/`
- Anything in `docs/`

The write tool will reject attempts to modify protected files.

## GUI / Browser / Screen Protocol

When interacting with apps, websites, or the desktop, follow this loop:

### 1. Observe
- Take a screenshot or query deterministic state (DOM, CLI, etc.)
- Know what is visible. Know what app has focus.

### 2. Structure
- Convert visible state into discrete facts:
  - exact button labels, coordinates, element selectors
  - exact text content, move lists, process states

### 3. Decide
- Choose one exact action. State it before executing.

### 4. Execute
- Use the best tool for the action.
- Tool priority: DOM/semantic > keyboard/scripting > physical clicks > raw coordinates

### 5. Verify
- Re-check whether the state changed as expected.
- If not, do not assume success. Diagnose why.

**Repeat until objective is achieved.**

## How to Use Vision

Do not ask Vision vague questions when precision is needed.

Use the formula: **context + objective + hypothesis + exact ask + output style**

Good:
> "1200px screenshot. Is the Start modal still open? If not, is there a green Play button visible? Give exact center x,y."

Bad:
> "What do you see?"

Use Vision for: visible state, button coordinates, geometry, content verification.
Do NOT use Vision for: hidden tabs, process internals, unseen windows.

## Browser Strategy

- Prefer DOM / semantic / accessibility interaction first.
- If unavailable, use keyboard/system scripting.
- If unavailable, use physical click automation.
- Always verify after action.
- Disambiguate buttons before clicking if there are multiple matching labels.
- Prefer exact DOM selection or exact position after verification.
