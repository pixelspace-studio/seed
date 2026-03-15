"""Session management — single session, JSONL-backed history."""

import json
import os
import shutil
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import Config


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

    def estimate_tokens(self, messages: list[dict], chars_per_token: float) -> int:
        """Estimate total tokens across all messages."""
        total_chars = sum(len(json.dumps(m)) for m in messages)
        return int(total_chars / chars_per_token)

    def get_context(self, cfg=None) -> list[dict]:
        """Return messages, applying sliding window if config is provided."""
        messages = self.load()

        if cfg is None:
            return messages

        max_tokens = cfg.max_context_tokens
        keep_recent = cfg.context_keep_recent
        chars_per_token = cfg.chars_per_token

        # If within limit, return everything
        if self.estimate_tokens(messages, chars_per_token) <= max_tokens:
            return messages

        # Split into evictable (older) and protected (recent)
        if len(messages) <= keep_recent:
            return messages

        protected = messages[-keep_recent:]
        evictable = messages[:-keep_recent]

        # Drop oldest messages one "turn" at a time, respecting tool pairs.
        # A turn is either:
        #   - a single user or assistant message (no tool calls)
        #   - an assistant message with tool_calls + all its following tool_results
        while evictable:
            # Check if we're within budget now
            remaining = evictable + protected
            if self.estimate_tokens(remaining, chars_per_token) <= max_tokens:
                break

            # Find and drop the oldest complete turn
            i = 0
            if evictable[i].get("role") == "assistant" and evictable[i].get("tool_calls"):
                # Collect the tool_use IDs from this assistant message
                tool_ids = {tc["id"] for tc in evictable[i].get("tool_calls", [])}
                i += 1
                # Skip all tool_result messages that belong to this turn
                while i < len(evictable) and evictable[i].get("role") == "tool_result" and evictable[i].get("tool_use_id") in tool_ids:
                    i += 1
            else:
                i = 1  # drop this single message

            evictable = evictable[i:]

        return evictable + protected

    def clear(self):
        """Archive current history and start fresh."""
        if not os.path.exists(self.history_path):
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archive_path = os.path.join(self.data_dir, f"history-{ts}.jsonl")
        shutil.move(self.history_path, archive_path)
