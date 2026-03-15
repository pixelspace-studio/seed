"""Core tool: switch_model — change the active AI model at runtime."""

from config import config

KNOWN_MODELS = {
    # Claude
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001",
    # Shortcuts
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-opus-4-6": "claude-opus-4-6",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
}

# Context window sizes per model (tokens)
MODEL_CONTEXT = {
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-6": 1_000_000,
    "claude-haiku-4-5-20251001": 200_000,
}

# Recommended MAX_CONTEXT_TOKENS per model (leaves headroom for response)
MODEL_RECOMMENDED_CONTEXT = {
    "claude-sonnet-4-6": 180_000,
    "claude-opus-4-6": 900_000,
    "claude-haiku-4-5-20251001": 180_000,
}


async def execute(model: str) -> str:
    resolved = KNOWN_MODELS.get(model.lower().strip())
    if not resolved:
        available = ", ".join(sorted(set(KNOWN_MODELS.keys())))
        return f"Unknown model '{model}'. Available: {available}"

    previous = config.model
    if resolved == previous:
        return f"Already using {resolved}."

    config.model = resolved

    # Auto-adjust context window for the new model
    recommended = MODEL_RECOMMENDED_CONTEXT.get(resolved)
    if recommended:
        config.max_context_tokens = recommended

    return (
        f"Switched from {previous} → {resolved}. "
        f"Context window adjusted to {config.max_context_tokens:,} tokens."
    )


tool = {
    "name": "switch_model",
    "description": (
        "Switch the active AI model. Use this when a task needs more capability (switch to opus), "
        "speed (switch to haiku), or when the user requests a model change. "
        "The change takes effect on the next message. "
        "Available: sonnet (claude-sonnet-4-6, 200K ctx), "
        "opus (claude-opus-4-6, 1M ctx), "
        "haiku (claude-haiku-4-5-20251001, 200K ctx, fastest)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "Model name or shortcut: 'sonnet', 'opus', 'haiku', or full model ID.",
            }
        },
        "required": ["model"],
    },
    "execute": execute,
}
