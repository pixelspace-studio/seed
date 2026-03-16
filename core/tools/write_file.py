"""Core tool: write — create or modify files with protection rules."""

import os
from datetime import datetime, timezone

from core.config import config

def _log_change(path: str, action: str):
    """Append to changelog when modifying tools/ or prompt.md."""
    from core.agent_state import get_active_agent
    agent = get_active_agent()
    changelog_path = os.path.join(agent.data_dir, "changelog.md") if agent else "changelog.md"
    os.makedirs(os.path.dirname(changelog_path) or ".", exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"- [{ts}] {action}: `{path}`\n"
    with open(changelog_path, "a") as f:
        f.write(entry)


async def execute(path: str, content: str) -> str:
    # Resolve relative paths
    if not os.path.isabs(path):
        path = os.path.join(config.working_dir, path)

    # Protection check
    if config.is_protected(path):
        return f"Error: {path} is a protected file and cannot be modified."

    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"Error writing file: {e}"

    # Log changes to tools/ or prompt.md
    rel = os.path.relpath(path, config.seed_dir)
    if rel.startswith("agents/shared/tools/") or rel.startswith("agents/") and rel.endswith("prompt.md"):
        action = "created" if not os.path.exists(path) else "modified"
        _log_change(rel, action)

        # Signal that registry should reload (checked by the loop)
        from core.agent_state import get_active_agent
        _agent = get_active_agent()
        flag_path = os.path.join(_agent.data_dir, ".reload_flag") if _agent else ".reload_flag"
        with open(flag_path, "w") as f:
            f.write("1")

    return f"OK: wrote {len(content)} bytes to {path}"


tool = {
    "name": "write",
    "description": "Create or overwrite a file. Creates parent directories if needed. Cannot modify protected core files.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write (relative to working directory or absolute)",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    },
    "execute": execute,
}
