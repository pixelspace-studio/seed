"""Core tool: create_agent — spawn a new agent at runtime."""


async def execute(name: str, identity: str, model: str = None) -> str:
    from core.config import config
    from core.agent_state import create_agent
    from main import agents

    name = name.strip().lower()

    if name in agents:
        return f"Agent '{name}' already exists."
    if name == "shared":
        return "'shared' is a reserved name."

    # Default to the calling agent's model
    if not model:
        from core.agent_state import get_active_agent
        caller = get_active_agent()
        model = caller.model if caller else "claude-sonnet-4-6"

    try:
        agent = create_agent(config.seed_dir, name, identity, model)
        agents[name] = agent
        return f"Agent '{name}' created and ready. Model: {model}."
    except Exception as e:
        return f"Error creating agent: {e}"


tool = {
    "name": "create_agent",
    "description": (
        "Create a new agent with its own identity, session, and data directory. "
        "The agent becomes available immediately without restart. "
        "Provide a name (lowercase, no spaces) and an identity prompt in markdown."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Agent name (lowercase, no spaces, e.g. 'researcher')",
            },
            "identity": {
                "type": "string",
                "description": "The agent's identity.md content — who it is, its principles, behavior",
            },
            "model": {
                "type": "string",
                "description": "Model ID for the agent (default: claude-sonnet-4-6)",
            },
        },
        "required": ["name", "identity"],
    },
    "execute": execute,
}
