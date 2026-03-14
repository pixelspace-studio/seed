"""AI provider — Anthropic only for v0.1."""

import asyncio
import logging
from dataclasses import dataclass, field

import anthropic

log = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class ProviderResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


async def send(
    messages: list[dict],
    tools: list[dict],
    model: str,
    api_key: str,
    system: str = "",
) -> ProviderResponse:
    """Send messages to Anthropic, return structured response."""
    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Build Anthropic tool schemas
    anthropic_tools = []
    for t in tools:
        anthropic_tools.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        })

    # Skip leading tool_result messages (orphaned by context truncation)
    start = 0
    while start < len(messages) and messages[start].get("role") == "tool_result":
        start += 1
    messages = messages[start:]

    # Also skip if first message is an assistant with tool_calls (its results got cut)
    if messages and messages[0].get("role") == "assistant" and messages[0].get("tool_calls"):
        messages = messages[1:]
        # Skip any following tool_results from that assistant
        while messages and messages[0].get("role") == "tool_result":
            messages = messages[1:]

    # Collect all tool_use IDs present in assistant messages
    tool_use_ids = set()
    for msg in messages:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                tool_use_ids.add(tc["id"])

    # Convert messages to Anthropic format
    api_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool_result":
            # Skip orphaned tool_results whose tool_use is missing
            if msg.get("tool_use_id") not in tool_use_ids:
                continue
            api_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg["tool_use_id"],
                    "content": str(msg.get("result", "")),
                }],
            })
        elif role == "assistant":
            content_blocks = []
            if msg.get("content"):
                content_blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls", []):
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["args"],
                })
            if content_blocks:
                api_messages.append({"role": "assistant", "content": content_blocks})
        else:
            api_messages.append({"role": "user", "content": msg.get("content", "")})

    # Ensure first message is from user (Anthropic requirement)
    if api_messages and api_messages[0].get("role") != "user":
        api_messages = [{"role": "user", "content": "(continuing conversation)"}] + api_messages

    # Retry with exponential backoff
    max_retries = 3
    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": model,
                "max_tokens": 8192,
                "messages": api_messages,
            }
            if system:
                kwargs["system"] = system
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            response = await client.messages.create(**kwargs)

            # Parse response
            content = ""
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        args=dict(block.input),
                    ))

            return ProviderResponse(
                content=content,
                tool_calls=tool_calls,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            log.warning(f"Anthropic API error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            await asyncio.sleep(wait)
        except anthropic.APIError as e:
            log.error(f"Anthropic API error: {e}")
            raise

    raise RuntimeError("Max retries exceeded")
