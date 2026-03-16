"""Core tool: bash — run shell commands."""

import asyncio
import os
import signal
import subprocess
from datetime import datetime, timezone

from core.config import config

MAX_OUTPUT = 100 * 1024  # 100KB
AUDIT_LOG = os.path.join(config.seed_dir, "data", "audit.jsonl")


def _audit(command: str, exit_code: int | None, duration_ms: float, truncated: bool = False, error: str = None):
    """Append to audit log. Every bash command gets recorded."""
    import json
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": "bash",
        "command": command,
        "exit_code": exit_code,
        "duration_ms": round(duration_ms),
        "truncated": truncated,
    }
    if error:
        entry["error"] = error
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


async def execute(command: str, timeout_ms: int = 120000) -> str:
    timeout_s = timeout_ms / 1000
    start_time = asyncio.get_event_loop().time()

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=config.working_dir,
            preexec_fn=os.setsid,
        )

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(0.5)
            if proc.returncode is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            _audit(command, None, elapsed, error="timeout")
            return f"[timeout after {timeout_s}s] Process killed."

        output = stdout.decode("utf-8", errors="replace")
        truncated = False
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT]
            truncated = True

        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        _audit(command, proc.returncode, elapsed, truncated=truncated)

        result = f"exit_code: {proc.returncode}\n{output}"
        if truncated:
            result += "\n[output truncated at 100KB]"
        return result

    except Exception as e:
        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        _audit(command, None, elapsed, error=str(e))
        return f"Error: {e}"


tool = {
    "name": "bash",
    "description": "Run a shell command and return the output. Use for system commands, installing packages, running scripts, etc.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default 120000)",
            },
        },
        "required": ["command"],
    },
    "execute": execute,
}
