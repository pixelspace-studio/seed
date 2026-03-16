"""Core tool: send_message — inter-agent messaging."""


async def execute(agent: str, message: str) -> str:
    from core.agent import AgentMessage, get_active_agent
    from core.globals import agents
    target = agents.get(agent)
    if not target:
        available = ", ".join(agents.keys())
        return f"Unknown agent: {agent}. Available: {available}"
    caller = get_active_agent()
    source = f"agent:{caller.name}" if caller else "agent"
    await target.queue.put(AgentMessage(text=message, source=source))
    return f"Message sent to {agent}"


tool = {
    "name": "send_message",
    "description": (
        "Send a message to another agent. The message is queued and the "
        "target agent's lifecycle loop picks it up."
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
