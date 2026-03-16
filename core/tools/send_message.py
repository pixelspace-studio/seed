"""Core tool: send_message — inter-agent messaging."""


async def execute(agent: str, message: str) -> str:
    from core.state import agents
    target = agents.get(agent)
    if not target:
        available = ", ".join(agents.keys())
        return f"Unknown agent: {agent}. Available: {available}"
    await target.inject_queue.put({"text": message, "source": "agent"})
    return f"Message sent to {agent}"


tool = {
    "name": "send_message",
    "description": (
        "Send a message to another agent. The message will be injected into "
        "the target agent's conversation loop."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Name of the target agent",
            },
            "message": {
                "type": "string",
                "description": "Message text to send",
            },
        },
        "required": ["agent", "message"],
    },
    "execute": execute,
}
