"""Core tool: read — read file contents with line numbers."""

import os

from core.config import config


async def execute(path: str, offset: int = 0, limit: int = 2000) -> str:
    # Resolve relative paths against working dir
    if not os.path.isabs(path):
        path = os.path.join(config.working_dir, path)

    if not os.path.exists(path):
        return f"Error: file not found: {path}"

    if os.path.isdir(path):
        return f"Error: {path} is a directory, not a file"

    # Binary detection
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return f"Error: {path} appears to be a binary file"
    except Exception as e:
        return f"Error reading file: {e}"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    total = len(lines)
    selected = lines[offset : offset + limit]

    result_lines = []
    for i, line in enumerate(selected, start=offset + 1):
        result_lines.append(f"{i:>6}\t{line.rstrip()}")

    header = f"File: {path} ({total} lines)"
    if offset > 0 or total > offset + limit:
        header += f" [showing lines {offset + 1}-{min(offset + limit, total)}]"

    return header + "\n" + "\n".join(result_lines)


tool = {
    "name": "read",
    "description": "Read a file and return its contents with line numbers. Supports offset and limit for large files.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read (relative to working directory or absolute)",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (0-indexed, default 0)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read (default 2000)",
            },
        },
        "required": ["path"],
    },
    "execute": execute,
}
