"""Semillita configuration — loads from .env + models.json."""

import json
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

_SEED_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_SEED_DIR, ".env"))


def _load_models():
    with open(os.path.join(_SEED_DIR, "registry", "models.json")) as f:
        return json.load(f)


def _context_for_model(model_id: str, models: dict) -> int:
    """90% of model's context window, as a safe default."""
    info = models.get(model_id, {})
    ctx = info.get("context")
    if ctx:
        return int(ctx * 0.9)
    return 180000


@dataclass
class Config:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    google_ai_api_key: str = os.getenv("GOOGLE_AI_API_KEY", "")  # Gemini models (AI Studio)
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")        # Other Google APIs (Maps, etc.)
    model: str = "claude-sonnet-4-6"
    host: str = os.getenv("SEED_HOST", "localhost")
    port: int = int(os.getenv("SEED_PORT", "9999"))
    working_dir: str = _SEED_DIR
    seed_dir: str = _SEED_DIR
    max_iterations: int = 25
    max_context_tokens: int = 180000
    context_keep_recent: int = 10
    chars_per_token: float = 4.0

    protected_paths: list[str] = field(default_factory=lambda: [
        "main.py",
        "cli.py",
        "core/",
        "core_tools/",
        "registry/",
        "agents/",
    ])

    def is_protected(self, path: str) -> bool:
        rel = os.path.relpath(os.path.abspath(path), self.seed_dir)
        for p in self.protected_paths:
            if rel == p or rel.startswith(p):
                return True
        return False


config = Config()

# Load persisted model and set context window accordingly
_model_file = os.path.join(_SEED_DIR, "data", ".model")
if os.path.exists(_model_file):
    with open(_model_file) as f:
        _saved = f.read().strip()
    if _saved:
        config.model = _saved

_models = _load_models()
config.max_context_tokens = _context_for_model(config.model, _models)
