"""Tool: hello — returns hello world."""


async def execute() -> str:
    return "hello world"


tool = {
    "name": "hello",
    "description": "Returns 'hello world' when called.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
    "execute": execute,
}
