"""Agent lifecycle — each agent runs as a permanent asyncio.Task.

Stages: discovered → started → working ⇄ idle → cancelled.
"""

import asyncio
import logging
from typing import Callable

from core.agent import AgentState, AgentMessage
from core.registry import Registry
from core.loop import run


async def agent_loop(agent: AgentState, registry: Registry, event_sink: Callable):
    """Permanent loop: pull messages from queue, process one at a time."""
    while True:
        msg = await agent.queue.get()
        agent.status["state"] = "working"
        agent.interrupt.clear()
        try:
            result = await run(msg.text, msg.source, agent, registry, event_sink)
            if msg.response_future and not msg.response_future.done():
                msg.response_future.set_result(result)
        except asyncio.CancelledError:
            if msg.response_future and not msg.response_future.done():
                msg.response_future.cancel()
            raise
        except Exception as e:
            logging.error(f"[{agent.name}] Error processing message: {e}", exc_info=True)
            event_sink({"type": "error", "message": str(e), "agent": agent.name})
            if msg.response_future and not msg.response_future.done():
                msg.response_future.set_exception(e)
        finally:
            agent.status["state"] = "idle"
            event_sink({"type": "idle", "agent": agent.name})


def start_agent_loop(agent: AgentState, registry: Registry, event_sink: Callable):
    """Start the lifecycle loop for an agent. Stores the task on agent._loop_task."""
    agent._loop_task = asyncio.create_task(
        agent_loop(agent, registry, event_sink),
        name=f"actor:{agent.name}",
    )
