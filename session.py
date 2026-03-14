"""Session management — single session, JSONL-backed history."""

import json
import os
import shutil
from datetime import datetime, timezone


class Session:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.history_path = os.path.join(data_dir, "history.jsonl")
        os.makedirs(data_dir, exist_ok=True)

    def load(self) -> list[dict]:
        """Read all messages from history file."""
        if not os.path.exists(self.history_path):
            return []
        messages = []
        with open(self.history_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages

    def append(self, message: dict):
        """Append a message to history."""
        message["ts"] = datetime.now(timezone.utc).isoformat()
        with open(self.history_path, "a") as f:
            f.write(json.dumps(message) + "\n")

    def get_context(self) -> list[dict]:
        """Return all messages. No truncation — let the model hit its limit."""
        return self.load()

    def clear(self):
        """Archive current history and start fresh."""
        if not os.path.exists(self.history_path):
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archive_path = os.path.join(self.data_dir, f"history-{ts}.jsonl")
        shutil.move(self.history_path, archive_path)
