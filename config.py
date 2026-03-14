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
    max_context_messages: int = 50

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
