"""Global shared state — the one mutable singleton everyone imports.

Why this file exists: Python's import system can create duplicate module
instances when the same file is imported via different paths (e.g.
__main__ vs core.something). If two modules each get their own copy of
the agents dict, mutations in one are invisible to the other.

This module solves that by being the single canonical home for shared
mutable state. Every module does `from core.globals import agents` and
gets the exact same dict. main.py fills it at startup; tools read it
at runtime.
"""

from core.agent import AgentState

agents: dict[str, AgentState] = {}
_registry = None     # set by main.py at startup
_event_sink = None   # set by main.py at startup
