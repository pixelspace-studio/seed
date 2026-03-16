"""Core tool: set_config — change runtime configuration."""

from core.config import config

# Which config fields can be changed at runtime, with their types
MUTABLE = {
    "max_iterations": int,
    "max_context_tokens": int,
    "context_keep_recent": int,
    "chars_per_token": float,
}


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

    old_value = getattr(config, key)
    setattr(config, key, new_value)
    return f"{key}: {old_value} → {new_value}"


tool = {
    "name": "set_config",
    "description": (
        "Change a runtime configuration value. "
        "Available keys: max_iterations (agent loop limit), "
        "max_context_tokens (context window size), "
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
