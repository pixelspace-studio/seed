"""The agent loop — Semillita's kernel. ~100 lines."""

import asyncio
import os
from typing import Callable

from config import config
from registry import Registry
from session import Session
from provider import send as provider_send


async def run(
    message: str,
    source: str,
    session: Session,
    registry: Registry,
    event_sink: Callable = None,
    interrupt: asyncio.Event = None,
    inject_queue: asyncio.Queue = None,
) -> str:
    """Run the agent loop for a single message. Returns final response text."""

    def emit(event: dict):
        if event_sink:
            event_sink(event)

    # Load system prompt
    prompt_path = os.path.join(config.seed_dir, "prompt.md")
    with open(prompt_path, "r") as f:
        system_prompt = f.read()

    # Build messages: history + new message
    messages = session.get_context(cfg=config)
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
        reload_flag = os.path.join(config.seed_dir, "data", ".reload_flag")
        if os.path.exists(reload_flag):
            os.remove(reload_flag)
            registry.reload_custom()
            tools_schema = registry.get_tools_schema()

        emit({"type": "thinking", "model": config.model, "iteration": iteration + 1})

        # Call provider
        response = await provider_send(
            messages=messages,
            tools=tools_schema,
            model=config.model,
            api_key=config.anthropic_api_key,
            system=system_prompt,
        )

        # No tool calls → final response
        if not response.tool_calls:
            text = response.content
            # If empty but we got a respond tool result, use that
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
            emit({"type": "tool_result", "tool": tc.name, "result": result[:500]})

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
