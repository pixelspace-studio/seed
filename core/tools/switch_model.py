"""Core tool: switch_model — change the active AI model at runtime."""

import json
import os

from core.config import config

MODELS_PATH = os.path.join(config.seed_dir, "registry", "models.json")



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

    resolved = model.strip()

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

    # Persist selection
    model_file = os.path.join(config.seed_dir, "data", ".model")
    with open(model_file, "w") as f:
        f.write(resolved)

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
        "Use full model IDs from models.json (e.g. claude-sonnet-4-6, gemini-3-flash)."
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
