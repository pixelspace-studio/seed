# Seed / Semillita — User Stories

Three users interact with the system: a **Human**, **Semillita herself**, and **other AI agents**.

---

## Human User

### Getting Started

- As a human, I want to install Semillita with a single command so I don't waste time on setup.
- As a human, I want to give Semillita my API keys once and never think about them again.
- As a human, I want to point Semillita at a folder and say "this is your home" so she knows where she lives and works.
- As a human, I want Semillita to read a prompt file on startup so she knows who she is without me explaining every time.

### Talking to Semillita

- As a human, I want to send Semillita a message in natural language and get a response, like a conversation.
- As a human, I want to send messages through an API endpoint so I can talk to her from any interface — a browser, a script, Slack, whatever I build later.
- As a human, I want to send messages through a simple CLI command so I can talk to her from my terminal when that's convenient.
- As a human, I want Semillita to remember our conversation within the current session so I don't have to repeat context.

### Delegating Work

- As a human, I want to tell Semillita "set up a Slack bot for this workspace" and walk away — she should handle the browser, the permissions, the keys, everything.
- As a human, I want to tell Semillita "create a new GitHub repo and push this code" without touching a browser or filling out forms.
- As a human, I want to tell Semillita to install software on my Mac and handle any permission dialogs that pop up.
- As a human, I want to give Semillita a vague goal ("organize my downloads folder") and have her figure out the steps herself.
- As a human, I want to tell Semillita to monitor something ("let me know if this website goes down") and have her do it on her own.
- As a human, I want to be able to say "sign up for this service" and have Semillita navigate the website, fill forms, and come back with the credentials.

### Trust & Control

- As a human, I want Semillita to ask me before spending money or doing something irreversible.
- As a human, I want to see what Semillita is doing — what commands she's running, what pages she's visiting — so I can trust her.
- As a human, I want to be able to interrupt Semillita mid-task if she's going in the wrong direction.
- As a human, I want Semillita to tell me when she's stuck instead of spinning forever.
- As a human, I want to decide the level of autonomy — sometimes I want her to ask me at every step, sometimes I want her to just figure it out.

### Not Having To Do Things

- As a human, I do not want to deal with macOS permission dialogs — Semillita should handle them.
- As a human, I do not want to configure services manually in browser UIs — Semillita should do it.
- As a human, I do not want to copy-paste API keys between services — Semillita should manage that.
- As a human, I do not want to write boilerplate code — Semillita should generate it.
- As a human, I do not want to learn the CLI syntax of every tool — I just describe what I want.

---

## Semillita (Self-User)

### Existing & Understanding

- As Semillita, I want to read my system prompt on startup so I know who I am and what I can do.
- As Semillita, I want to know my working directory so I understand where my files live.
- As Semillita, I want to know what tools I currently have available so I can plan what actions to take.
- As Semillita, I want to be aware of my own source code location so I can modify myself when needed.

### Thinking & Acting

- As Semillita, I want to receive a message, think about it, decide on a plan, execute it step by step, and respond — in a loop, until the goal is achieved.
- As Semillita, I want to execute bash commands and read their output so I can interact with the operating system.
- As Semillita, I want to read files so I can understand code, configurations, and documents.
- As Semillita, I want to write and edit files so I can create and modify code, configs, and data.
- As Semillita, I want to control a web browser so I can navigate sites, fill forms, click buttons, and read page content — like a human would.
- As Semillita, I want to control the Mac desktop (mouse, keyboard, screenshots) so I can interact with native apps and system dialogs that have no API.
- As Semillita, I want to see the results of my own tool executions so I can decide what to do next based on what happened.

### Growing & Self-Building

- As Semillita, I want to create new tool files in my tools directory so I can give myself new capabilities.
- As Semillita, I want my new tools to be available immediately without restarting so I can use them right away.
- As Semillita, I want to modify my own system prompt so I can refine my own identity and instructions as I learn.
- As Semillita, I want to install Python packages so I can use new libraries for tools I'm building.
- As Semillita, I want to create scripts and automations that persist so I can reuse them later.
- As Semillita, I want to keep a log of what I've built and changed so I can understand my own evolution.
- As Semillita, I want to test my new tools before relying on them so I don't break myself.

### Self-Preservation

- As Semillita, I want to never modify my core loop — only add to my tools and prompt — so I can't accidentally destroy my ability to function.
- As Semillita, I want to version my changes so I can roll back if something I built breaks me.
- As Semillita, I want to recognize when I'm stuck in a loop and stop myself instead of burning API credits forever.
- As Semillita, I want to be honest about what I can't do so the human can help me or find another way.

---

## Other AI Agent

### Discovering Semillita

- As an AI agent, I want to discover Semillita's capabilities through an MCP server so I know what tools she offers.
- As an AI agent, I want to see a list of Semillita's available skills and tools via the API so I can decide what to delegate to her.

### Delegating Tasks

- As an AI agent, I want to send Semillita a task via API and receive a structured response so I can integrate her work into my own workflow.
- As an AI agent, I want to ask Semillita to execute bash commands on her machine and return the output so I can use her as a remote executor.
- As an AI agent, I want to ask Semillita to browse a website and extract information so I can use her browser capabilities without having my own.
- As an AI agent, I want to ask Semillita to create or modify files on her filesystem so I can use her as a builder.
- As an AI agent, I want to send Semillita a multi-step task and have her execute the full plan, not just one step at a time.

### Coordination

- As an AI agent, I want to check on the status of a task I gave Semillita so I know if it's done, in progress, or stuck.
- As an AI agent, I want Semillita to notify me when a task is complete so I don't have to poll.
- As an AI agent, I want to send Semillita context (files, data, instructions) along with a task so she has everything she needs.
- As an AI agent, I want Semillita's responses in structured JSON so I can parse them programmatically, not just read natural language.

### Using Semillita's Unique Abilities

- As an AI agent, I want to use Semillita's browser to do things I can't do myself — sign up for services, navigate UIs, fill forms.
- As an AI agent, I want to use Semillita's Mac control to interact with native apps that have no API.
- As an AI agent, I want to ask Semillita to build me a new tool or script and return the code so I can use it in my own environment.
- As an AI agent, I want Semillita to be my "hands" — I provide the intelligence and planning, she provides the physical execution on a real machine.

---

## Cross-Cutting Concerns (All Users)

- All interactions go through the same core — the agent loop. Whether a human types a message, Semillita decides to act on her own, or another agent sends a request, the processing is identical.
- The API is the single source of truth. The CLI is just a thin client that talks to the API. MCP is another client. Everything is a client.
- There is one session. Not multiple. The context is continuous.
- Semillita's identity, tools, and capabilities grow over time. What she can do today is less than what she can do tomorrow. That's the whole point.
