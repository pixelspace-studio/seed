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
    """Switch the model for the calling agent. Finds agent via main.agents."""
    from core.state import agents

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

    if "text" not in info["capabilities"]:
        caps = ", ".join(info["capabilities"])
        return (
            f"'{resolved}' is a {caps} model, not a chat model. "
            f"It can be used through its specific tool, not as the main model."
        )

    # Find which agent is currently working (the one calling this tool)
    active_agent = None
    for agent in agents.values():
        if agent.status.get("state") == "working":
            active_agent = agent
            break

    if not active_agent:
        # Fallback to default agent
        active_agent = agents.get(config.default_agent)

    if not active_agent:
        return "No active agent found to switch model for."

    previous = active_agent.model
    if resolved == previous:
        return f"Already using {resolved}."

    active_agent.model = resolved

    # Persist selection
    model_file = os.path.join(active_agent.data_dir, ".model")
    with open(model_file, "w") as f:
        f.write(resolved)

    # Auto-adjust context window
    recommended = _recommended_context(info.get("context"))
    if recommended:
        active_agent.max_context_tokens = recommended

    return (
        f"Switched from {previous} → {info['name']} ({resolved}). "
        f"Provider: {info['provider']}. "
        f"Context window adjusted to {active_agent.max_context_tokens:,} tokens."
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
