"""Core tool: switch_model — change the active AI model at runtime."""

import json
import os

from config import config

MODELS_PATH = os.path.join(config.seed_dir, "models.json")

# Shorthand aliases
ALIASES = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001",
    "gpt": "gpt-5.4",
    "gemini": "gemini-2.5-pro",
    "flash": "gemini-2.5-flash",
}


def _load_models():
    with open(MODELS_PATH, "r") as f:
        return json.load(f)


def _recommended_context(context_window):
    """Leave 10% headroom for response + tool schemas."""
    if not context_window:
        return None
    return int(context_window * 0.9)


async def execute(model: str) -> str:
    models = _load_models()

    # Resolve alias or direct model ID
    key = model.lower().strip()
    resolved = ALIASES.get(key, key)

    if resolved not in models:
        text_models = [
            f"  {mid} ({m['name']})"
            for mid, m in models.items()
            if "text" in m["capabilities"]
        ]
        return f"Unknown model '{model}'. Available for chat:\n" + "\n".join(text_models)

    info = models[resolved]

    # Only allow models with text capability as the chat model
    if "text" not in info["capabilities"]:
        caps = ", ".join(info["capabilities"])
        return (
            f"'{resolved}' is a {caps} model, not a chat model. "
            f"It can be used through its specific tool, not as the main model."
        )

    previous = config.model
    if resolved == previous:
        return f"Already using {resolved}."

    config.model = resolved

    # Auto-adjust context window
    recommended = _recommended_context(info.get("context"))
    if recommended:
        config.max_context_tokens = recommended

    return (
        f"Switched from {previous} → {info['name']} ({resolved}). "
        f"Provider: {info['provider']}. "
        f"Context window adjusted to {config.max_context_tokens:,} tokens."
    )


tool = {
    "name": "switch_model",
    "description": (
        "Switch the active AI model. Only accepts models with text capability. "
        "Use this when a task needs more capability (opus), speed (haiku/flash), "
        "or when the user requests a model change. "
        "Shortcuts: sonnet, opus, haiku, gpt, gemini, flash. "
        "Or use full model IDs from models.json."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "Model name, shortcut, or full model ID",
            }
        },
        "required": ["model"],
    },
    "execute": execute,
}
