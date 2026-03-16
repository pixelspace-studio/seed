"""Core tool: set_config — change runtime configuration."""

from core.config import config

# Config-level mutable fields
CONFIG_MUTABLE = {
    "max_iterations": int,
    "context_keep_recent": int,
    "chars_per_token": float,
}

# Agent-level mutable fields
AGENT_MUTABLE = {
    "max_context_tokens": int,
}

MUTABLE = {**CONFIG_MUTABLE, **AGENT_MUTABLE}


async def execute(key: str, value: str) -> str:
    key = key.strip().lower()

    if key not in MUTABLE:
        available = ", ".join(MUTABLE.keys())
        return f"Unknown config key '{key}'. Available: {available}"

    cast = MUTABLE[key]
    try:
        new_value = cast(value)
    except (ValueError, TypeError):
        return f"Invalid value '{value}' for {key} (expected {cast.__name__})"

    if key in AGENT_MUTABLE:
        from core.agent_state import get_active_agent
        agent = get_active_agent()
        if not agent:
            return "No active agent to set config on."
        old_value = getattr(agent, key)
        setattr(agent, key, new_value)
    else:
        old_value = getattr(config, key)
        setattr(config, key, new_value)

    return f"{key}: {old_value} → {new_value}"


tool = {
    "name": "set_config",
    "description": (
        "Change a runtime configuration value. "
        "Available keys: max_iterations (agent loop limit), "
        "max_context_tokens (context window size, per-agent), "
        "context_keep_recent (minimum protected messages), "
        "chars_per_token (token estimation ratio). "
        "Use this when the user wants to adjust iteration limits or context settings."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Config key to change",
                "enum": list(MUTABLE.keys()),
            },
            "value": {
                "type": "string",
                "description": "New value (will be cast to the appropriate type)",
            },
        },
        "required": ["key", "value"],
    },
    "execute": execute,
}
