"""Semillita — FastAPI server with multi-agent support."""

import asyncio
import json
import logging
import os
import traceback

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from core.config import config
from core.agent_state import AgentState, discover_agents, _context_for_model
from core.registry import Registry
from core.loop import run

app = FastAPI(title="Semillita", version="0.1")

# --- State ---
agents: dict[str, AgentState] = {}
registry = Registry(seed_dir=config.seed_dir)


# --- WebSocket broadcast ---
class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.remove(ws)


manager = ConnectionManager()


def event_sink(event: dict):
    """Sync wrapper to broadcast events."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(event))
    except RuntimeError:
        pass


# --- Helpers ---
def _get_agent(name: str) -> AgentState | None:
    return agents.get(name)


def _models_json() -> dict:
    path = os.path.join(config.seed_dir, "registry", "models.json")
    with open(path) as f:
        return json.load(f)


# --- Startup ---
@app.on_event("startup")
async def startup():
    agents.update(discover_agents(config.seed_dir))
    registry.load()
    tools = registry.get_tool_names()
    agent_names = list(agents.keys())
    print()
    print("  Semillita is awake.")
    print(f"  Agents: {', '.join(agent_names)}")
    print(f"  Tools: {', '.join(tools)}")
    print(f"  Listening on http://{config.host}:{config.port}")
    print()


# --- Pydantic models ---
class MessageRequest(BaseModel):
    text: str
    source: str = "human"


class MessageResponse(BaseModel):
    response: str


class ModelRequest(BaseModel):
    text: str


# --- Agent-scoped endpoints ---
@app.post("/agents/{name}/message", response_model=MessageResponse)
async def post_agent_message(name: str, req: MessageRequest):
    agent = _get_agent(name)
    if not agent:
        return MessageResponse(response=f"Unknown agent: {name}")
    # Drain stale injected messages
    while not agent.inject_queue.empty():
        try:
            agent.inject_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    agent.status["state"] = "working"
    agent.interrupt.clear()
    try:
        result = await run(
            message=req.text,
            source=req.source,
            agent_state=agent,
            registry=registry,
            event_sink=event_sink,
        )
        return MessageResponse(response=result)
    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"Error processing message for {name}: {e}\n{tb}")
        await manager.broadcast({"type": "error", "message": str(e), "agent": name})
        raise
    finally:
        agent.status["state"] = "idle"
        await manager.broadcast({"type": "idle", "agent": name})


@app.get("/agents/{name}/status")
async def get_agent_status(name: str):
    agent = _get_agent(name)
    if not agent:
        return {"error": f"Unknown agent: {name}"}
    return {**agent.status, "model": agent.model, "name": agent.name}


@app.get("/agents/{name}/history")
async def get_agent_history(name: str):
    agent = _get_agent(name)
    if not agent:
        return {"error": f"Unknown agent: {name}"}
    return agent.session.load()


@app.post("/agents/{name}/inject")
async def post_agent_inject(name: str, req: MessageRequest):
    agent = _get_agent(name)
    if not agent:
        return {"ok": False, "error": f"Unknown agent: {name}"}
    if agent.status["state"] != "working":
        return {"ok": False, "error": "Not working. Use /agents/{name}/message instead."}
    await agent.inject_queue.put({"text": req.text, "source": req.source})
    await manager.broadcast({"type": "injected", "text": req.text, "agent": name})
    return {"ok": True}


@app.post("/agents/{name}/interrupt")
async def post_agent_interrupt(name: str):
    agent = _get_agent(name)
    if not agent:
        return {"ok": False, "error": f"Unknown agent: {name}"}
    agent.interrupt.set()
    return {"ok": True}


@app.post("/agents/{name}/model")
async def post_agent_model(name: str, req: ModelRequest):
    agent = _get_agent(name)
    if not agent:
        return {"ok": False, "error": f"Unknown agent: {name}"}

    models = _models_json()
    model_id = req.text.strip()

    if model_id not in models:
        text_models = [
            f"  {mid} ({m['name']})"
            for mid, m in models.items()
            if "text" in m.get("capabilities", [])
        ]
        return {"ok": False, "error": f"Unknown model '{model_id}'. Available:\n" + "\n".join(text_models)}

    info = models[model_id]
    if "text" not in info.get("capabilities", []):
        return {"ok": False, "error": f"'{model_id}' is not a text model."}

    previous = agent.model
    if model_id == previous:
        return {"ok": True, "result": f"Already using {model_id}."}

    agent.model = model_id

    # Persist
    model_file = os.path.join(agent.data_dir, ".model")
    with open(model_file, "w") as f:
        f.write(model_id)

    # Adjust context window
    agent.max_context_tokens = _context_for_model(model_id, models)

    result = (
        f"Switched from {previous} → {info['name']} ({model_id}). "
        f"Provider: {info['provider']}. "
        f"Context window adjusted to {agent.max_context_tokens:,} tokens."
    )
    return {"ok": True, "result": result}


# --- Global endpoints ---
@app.get("/agents")
async def get_agents():
    return [
        {"name": a.name, "status": a.status["state"], "model": a.model}
        for a in agents.values()
    ]


@app.get("/models")
async def get_models():
    return _models_json()


@app.websocket("/stream")
async def websocket_stream(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.host, port=config.port)
