"""Core tool: bash — run shell commands."""

import asyncio
import os
import signal
import subprocess

from config import config

MAX_OUTPUT = 100 * 1024  # 100KB


async def execute(command: str, timeout_ms: int = 120000) -> str:
    timeout_s = timeout_ms / 1000

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
            return f"[timeout after {timeout_s}s] Process killed."

        output = stdout.decode("utf-8", errors="replace")
        truncated = False
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT]
            truncated = True

        result = f"exit_code: {proc.returncode}\n{output}"
        if truncated:
            result += "\n[output truncated at 100KB]"
        return result

    except Exception as e:
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
