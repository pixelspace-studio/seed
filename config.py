"""Semillita configuration — loads from .env, no magic."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("MODEL", "claude-sonnet-4-6")
    host: str = os.getenv("SEED_HOST", "localhost")
    port: int = int(os.getenv("SEED_PORT", "9999"))
    working_dir: str = os.path.dirname(os.path.abspath(__file__))
    seed_dir: str = os.path.dirname(os.path.abspath(__file__))
    max_iterations: int = 25

    # Sliding context window
    # MAX_CONTEXT_TOKENS: how many tokens of history to send to the model.
    # Leave headroom vs the model's hard limit for the response and tool schemas.
    # Sonnet = 200K limit → default 180K. Opus = 1M → raise to e.g. 900000.
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "180000"))

    # CONTEXT_KEEP_RECENT: minimum number of messages that are NEVER evicted,
    # regardless of token count. Protects the tail of the conversation.
    context_keep_recent: int = int(os.getenv("CONTEXT_KEEP_RECENT", "10"))

    # CHARS_PER_TOKEN: characters-per-token ratio for fast token estimation.
    # Research consensus: 4 for English/Spanish prose, 3.5 for code-heavy sessions.
    # Anthropic, OpenAI, and Gemini all converge to ~4 for Latin-script text.
    chars_per_token: float = float(os.getenv("CHARS_PER_TOKEN", "4"))

    protected_paths: list[str] = field(default_factory=lambda: [
        "main.py",
        "loop.py",
        "registry.py",
        "provider.py",
        "session.py",
        "config.py",
        "cli.py",
        "mcp.py",
        "core_tools/",
    ])

    def is_protected(self, path: str) -> bool:
        """Check if a path is protected from modification by Semillita."""
        rel = os.path.relpath(os.path.abspath(path), self.seed_dir)
        for p in self.protected_paths:
            if rel == p or rel.startswith(p):
                return True
        return False


config = Config()
