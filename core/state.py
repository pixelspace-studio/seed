"""Shared runtime state — single source of truth for agents dict.

Avoids the __main__ vs module-name dual-import problem by keeping
mutable state in a dedicated module that everyone imports the same way.
"""

from core.agent_state import AgentState

agents: dict[str, AgentState] = {}
