"""The agent loop — Semillita's kernel. ~100 lines."""

import asyncio
import os
from typing import Callable

from core.agent_state import AgentState
from core.config import config
from core.registry import Registry
from core.provider import send as provider_send


async def run(
    message: str,
    source: str,
    agent_state: AgentState,
    registry: Registry,
    event_sink: Callable = None,
) -> str:
    """Run the agent loop for a single message. Returns final response text."""

    session = agent_state.session
    interrupt = agent_state.interrupt
    inject_queue = agent_state.inject_queue

    def emit(event: dict):
        if event_sink:
            event["agent"] = agent_state.name
            event_sink(event)

    # Load system prompt: shared protocol + agent identity
    parts = []
    shared_protocol = os.path.join(config.seed_dir, "agents", "shared", "protocol.md")
    if os.path.exists(shared_protocol):
        with open(shared_protocol, "r") as f:
            parts.append(f.read())
    identity = os.path.join(agent_state.agent_dir, "identity.md")
    if os.path.exists(identity):
        with open(identity, "r") as f:
            parts.append(f.read())
    system_prompt = "\n\n---\n\n".join(parts)

    # Build messages: history + new message
    # Build a lightweight cfg-like object for session's sliding window
    class _Cfg:
        max_context_tokens = agent_state.max_context_tokens
        context_keep_recent = config.context_keep_recent
        chars_per_token = config.chars_per_token
    messages = session.get_context(cfg=_Cfg())
    user_msg = {"role": "user", "content": message, "source": source}
    session.append(user_msg)
    messages.append(user_msg)

    emit({"type": "message_received", "source": source, "text": message})

    tools_schema = registry.get_tools_schema()
    last_respond = None

    for iteration in range(config.max_iterations):
        # Check interrupt
        if interrupt and interrupt.is_set():
            emit({"type": "interrupted"})
            return "[interrupted]"

        # Drain injected messages from queue
        if inject_queue:
            while not inject_queue.empty():
                try:
                    injected = inject_queue.get_nowait()
                    inject_msg = {
                        "role": "user",
                        "content": injected["text"],
                        "source": injected.get("source", "human"),
                    }
                    messages.append(inject_msg)
                    session.append(inject_msg)
                    emit({
                        "type": "message_received",
                        "source": inject_msg["source"],
                        "text": injected["text"],
                        "injected": True,
                    })
                except asyncio.QueueEmpty:
                    break

        # Check reload flag
        reload_flag = os.path.join(agent_state.data_dir, ".reload_flag")
        if os.path.exists(reload_flag):
            os.remove(reload_flag)
            registry.reload_custom()
            tools_schema = registry.get_tools_schema()

        emit({"type": "thinking", "model": agent_state.model, "iteration": iteration + 1})

        # Call provider
        response = await provider_send(
            messages=messages,
            tools=tools_schema,
            model=agent_state.model,
            system=system_prompt,
            cfg=config,
        )

        # No tool calls → check for injected messages before returning.
        # User may have typed while provider_send() was blocking.
        if not response.tool_calls:
            injected_msgs = []
            if inject_queue and not inject_queue.empty():
                while not inject_queue.empty():
                    try:
                        injected = inject_queue.get_nowait()
                        injected_msgs.append(injected)
                    except asyncio.QueueEmpty:
                        break
            if injected_msgs:
                # Save assistant response first, then append injected user
                # messages so the conversation ends with a user message.
                assistant_msg = {"role": "assistant", "content": response.content}
                messages.append(assistant_msg)
                session.append(assistant_msg)
                for injected in injected_msgs:
                    inject_msg = {
                        "role": "user",
                        "content": injected["text"],
                        "source": injected.get("source", "human"),
                    }
                    messages.append(inject_msg)
                    session.append(inject_msg)
                    emit({
                        "type": "message_received",
                        "source": inject_msg["source"],
                        "text": injected["text"],
                        "injected": True,
                    })
                continue

            text = response.content
            if not text and last_respond:
                text = last_respond
            assistant_msg = {"role": "assistant", "content": text}
            session.append(assistant_msg)
            emit({"type": "response_complete", "text": text, "usage": response.usage})
            return text

        # Has tool calls → execute them
        # Build assistant message with content + tool calls
        assistant_msg = {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "args": tc.args}
                for tc in response.tool_calls
            ],
        }
        messages.append(assistant_msg)
        session.append(assistant_msg)

        for tc in response.tool_calls:
            emit({"type": "tool_call", "tool": tc.name, "args": tc.args})

            try:
                result = await registry.execute(tc.name, tc.args)
            except (KeyboardInterrupt, asyncio.CancelledError):
                result = "[error: interrupted]"
            except Exception as exc:
                result = f"[error: {exc}]"

            if tc.name == "respond":
                last_respond = result
            emit({"type": "tool_result", "tool": tc.name, "result": result})

            tool_result_msg = {
                "role": "tool_result",
                "tool_use_id": tc.id,
                "tool": tc.name,
                "result": result,
            }
            messages.append(tool_result_msg)
            session.append(tool_result_msg)

    # Max iterations reached
    emit({"type": "error", "message": f"Max iterations ({config.max_iterations}) reached"})
    return f"[stopped: max iterations ({config.max_iterations}) reached]"
