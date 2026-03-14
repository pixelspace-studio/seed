"""Core tool: respond — send a message back to the user."""


async def execute(message: str) -> str:
    # In v0.1, the loop handles delivery. This tool simply returns the message.
    return message


tool = {
    "name": "respond",
    "description": "Send a message back to the user. Use this when you want to communicate something to the person who sent you a message.",
    "parameters": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to send to the user",
            },
        },
        "required": ["message"],
    },
    "execute": execute,
}
