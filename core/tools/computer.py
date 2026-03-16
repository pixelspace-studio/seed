"""Core tool: computer — native macOS control via PyAutoGUI + AppleScript."""

import asyncio
import os
import subprocess
from datetime import datetime, timezone

from core.config import config

TEMP_DIR = os.path.join(config.seed_dir, "data", "files", "temp")


async def execute(
    action: str,
    x: int = None,
    y: int = None,
    text: str = None,
    key: str = None,
    script: str = None,
) -> str:
    import pyautogui

    os.makedirs(TEMP_DIR, exist_ok=True)

    try:
        if action == "screenshot":
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = os.path.join(TEMP_DIR, f"screen-{ts}.png")
            img = pyautogui.screenshot()
            img.save(path)
            return f"Screenshot saved: {path}"

        elif action == "click":
            if x is None or y is None:
                return "Error: click requires x and y coordinates"
            pyautogui.click(x, y)
            return f"Clicked at ({x}, {y})"

        elif action == "type":
            if text is None:
                return "Error: type requires text"
            pyautogui.write(text, interval=0.02)
            return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"

        elif action == "key":
            if key is None:
                return "Error: key requires a key combo"
            keys = [k.strip() for k in key.split("+")]
            pyautogui.hotkey(*keys)
            return f"Pressed: {key}"

        elif action == "mouse_move":
            if x is None or y is None:
                return "Error: mouse_move requires x and y"
            pyautogui.moveTo(x, y)
            return f"Moved mouse to ({x}, {y})"

        elif action == "applescript":
            if script is None:
                return "Error: applescript requires a script"
            result = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            output = stdout.decode().strip()
            if result.returncode != 0:
                return f"AppleScript error: {stderr.decode().strip()}"
            return output or "OK"

        else:
            return f"Error: unknown action '{action}'. Valid: screenshot, click, type, key, mouse_move, applescript"

    except Exception as e:
        return f"Error: {e}"


tool = {
    "name": "computer",
    "description": "Control the Mac desktop. Actions: screenshot(), click(x,y), type(text), key(combo), mouse_move(x,y), applescript(script).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action: screenshot, click, type, key, mouse_move, applescript",
                "enum": ["screenshot", "click", "type", "key", "mouse_move", "applescript"],
            },
            "x": {"type": "integer", "description": "X coordinate"},
            "y": {"type": "integer", "description": "Y coordinate"},
            "text": {"type": "string", "description": "Text to type"},
            "key": {
                "type": "string",
                "description": "Key combo, e.g. 'cmd+space' or 'ctrl+c'",
            },
            "script": {"type": "string", "description": "AppleScript code to execute"},
        },
        "required": ["action"],
    },
    "execute": execute,
}
