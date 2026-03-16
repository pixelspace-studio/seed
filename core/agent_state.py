"""AgentState dataclass + discovery — one state per agent."""

import asyncio
import json
import os
from dataclasses import dataclass, field

from core.session import Session


@dataclass
class AgentState:
    name: str
    agent_dir: str           # agents/{name}/
    data_dir: str            # agents/{name}/data/
    session: Session
    inject_queue: asyncio.Queue
    interrupt: asyncio.Event
    status: dict = field(default_factory=lambda: {"state": "idle"})
    model: str = "claude-sonnet-4-6"
    max_context_tokens: int = 180000


def _context_for_model(model_id: str, models: dict) -> int:
    """90% of model's context window, as a safe default."""
    info = models.get(model_id, {})
    ctx = info.get("context")
    if ctx:
        return int(ctx * 0.9)
    return 180000


def get_active_agent():
    """Get the currently working agent, or fall back to default."""
    from core.config import config
    from main import agents
    for agent in agents.values():
        if agent.status.get("state") == "working":
            return agent
    return agents.get(config.default_agent)


def create_agent(seed_dir: str, name: str, identity: str, model: str = None) -> AgentState:
    """Create a new agent: directory, identity.md, data/, and return AgentState."""
    agents_dir = os.path.join(seed_dir, "agents")
    agent_dir = os.path.join(agents_dir, name)
    data_dir = os.path.join(agent_dir, "data")

    if os.path.exists(os.path.join(agent_dir, "identity.md")):
        raise ValueError(f"Agent '{name}' already exists")

    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(agent_dir, "identity.md"), "w") as f:
        f.write(identity)

    models_path = os.path.join(seed_dir, "registry", "models.json")
    with open(models_path) as f:
        models = json.load(f)

    # No default model — will be set via /model picker or API
    if not model:
        model = ""

    max_context = _context_for_model(model, models)

    return AgentState(
        name=name,
        agent_dir=agent_dir,
        data_dir=data_dir,
        session=Session(data_dir=data_dir),
        inject_queue=asyncio.Queue(),
        interrupt=asyncio.Event(),
        model=model,
        max_context_tokens=max_context,
    )


def discover_agents(seed_dir: str) -> dict[str, AgentState]:
    """Scan agents/*/identity.md, skip shared/, return AgentState per agent."""
    agents_dir = os.path.join(seed_dir, "agents")
    models_path = os.path.join(seed_dir, "registry", "models.json")

    with open(models_path) as f:
        models = json.load(f)

    agents = {}
    if not os.path.isdir(agents_dir):
        return agents

    for entry in sorted(os.listdir(agents_dir)):
        if entry == "shared":
            continue
        agent_dir = os.path.join(agents_dir, entry)
        identity = os.path.join(agent_dir, "identity.md")
        if not os.path.isfile(identity):
            continue

        data_dir = os.path.join(agent_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        # Load persisted model — empty string means "not yet chosen"
        model = ""
        model_file = os.path.join(data_dir, ".model")
        if os.path.exists(model_file):
            with open(model_file) as f:
                saved = f.read().strip()
            if saved:
                model = saved

        max_context = _context_for_model(model, models)

        agents[entry] = AgentState(
            name=entry,
            agent_dir=agent_dir,
            data_dir=data_dir,
            session=Session(data_dir=data_dir),
            inject_queue=asyncio.Queue(),
            interrupt=asyncio.Event(),
            model=model,
            max_context_tokens=max_context,
        )

    return agents
