"""Semillita configuration — loads from .env."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

_SEED_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_SEED_DIR, ".env"))


@dataclass
class Config:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    google_ai_api_key: str = os.getenv("GOOGLE_AI_API_KEY", "")  # Gemini models (AI Studio)
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")        # Other Google APIs (Maps, etc.)
    host: str = os.getenv("SEED_HOST", "localhost")
    port: int = int(os.getenv("SEED_PORT", "9999"))
    working_dir: str = _SEED_DIR
    seed_dir: str = _SEED_DIR
    agents_dir: str = os.path.join(_SEED_DIR, "agents")
    default_agent: str = "semillita"
    max_iterations: int = 25
    context_keep_recent: int = 10
    chars_per_token: float = 4.0

    protected_paths: list[str] = field(default_factory=lambda: [
        "main.py",
        "cli.py",
        "core/",
        "registry/",
        "agents/semillita/identity.md",
        "docs/",
    ])

    def is_protected(self, path: str) -> bool:
        rel = os.path.relpath(os.path.abspath(path), self.seed_dir)
        for p in self.protected_paths:
            if rel == p or rel.startswith(p):
                return True
        return False


config = Config()
