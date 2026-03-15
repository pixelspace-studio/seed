"""Semillita — FastAPI server."""

import asyncio
import json
import logging
import traceback

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from config import config
from session import Session
from registry import Registry
from loop import run

app = FastAPI(title="Semillita", version="0.1")

# --- State ---
session = Session(data_dir="data")
registry = Registry(seed_dir=config.seed_dir)
status = {"state": "idle"}
interrupt_event = asyncio.Event()
inject_queue = asyncio.Queue()


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


# --- Startup ---
@app.on_event("startup")
async def startup():
    registry.load()
    tools = registry.get_tool_names()
    print()
    print("  Semillita is awake.")
    print(f"  Working directory: {config.working_dir}")
    print(f"  Tools: {', '.join(tools)}")
    print(f"  Listening on http://{config.host}:{config.port}")
    print()


# --- Models ---
class MessageRequest(BaseModel):
    text: str
    source: str = "human"


class MessageResponse(BaseModel):
    response: str


# --- Endpoints ---
@app.post("/message", response_model=MessageResponse)
async def post_message(req: MessageRequest):
    # Drain stale injected messages from previous runs
    while not inject_queue.empty():
        try:
            inject_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    status["state"] = "working"
    interrupt_event.clear()
    try:
        result = await run(
            message=req.text,
            source=req.source,
            session=session,
            registry=registry,
            event_sink=event_sink,
            interrupt=interrupt_event,
            inject_queue=inject_queue,
        )
        return MessageResponse(response=result)
    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"Error processing message: {e}\n{tb}")
        await manager.broadcast({"type": "error", "message": str(e)})
        raise
    finally:
        status["state"] = "idle"
        await manager.broadcast({"type": "idle"})


@app.get("/status")
async def get_status():
    return status


@app.get("/tools")
async def get_tools():
    return registry.get_tools_schema()


@app.get("/history")
async def get_history():
    return session.load()


@app.post("/inject")
async def post_inject(req: MessageRequest):
    if status["state"] != "working":
        return {"ok": False, "error": "Not working. Use /message instead."}
    await inject_queue.put({"text": req.text, "source": req.source})
    await manager.broadcast({"type": "injected", "text": req.text})
    return {"ok": True}


@app.post("/model")
async def post_model(req: MessageRequest):
    """Switch model at runtime. Accepts aliases (sonnet, opus) or full IDs."""
    from core_tools.switch_model import execute as switch_execute
    result = await switch_execute(req.text)
    return {"ok": True, "result": result}


@app.post("/interrupt")
async def post_interrupt():
    interrupt_event.set()
    return {"ok": True}


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
