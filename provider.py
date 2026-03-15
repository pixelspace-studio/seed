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


def _sanitize_messages(messages):
    """Fix orphaned tool_use/tool_result pairs anywhere in the message history.

    Anthropic requires:
    - Every tool_use must have a tool_result immediately after
    - Every tool_result must reference a tool_use in the previous message

    This function handles both cases by collecting all IDs and patching gaps.
    """
    # Collect all tool_use IDs and all tool_result IDs
    tool_use_ids = set()
    tool_result_ids = set()
    for msg in messages:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                tool_use_ids.add(tc["id"])
        elif msg.get("role") == "tool_result":
            tool_result_ids.add(msg.get("tool_use_id"))

    # Find orphaned tool_uses (no matching tool_result)
    orphaned_uses = tool_use_ids - tool_result_ids
    # Find orphaned tool_results (no matching tool_use)
    orphaned_results = tool_result_ids - tool_use_ids

    if not orphaned_uses and not orphaned_results:
        return messages

    log.warning(f"Sanitizing messages: {len(orphaned_uses)} orphaned tool_uses, {len(orphaned_results)} orphaned tool_results")

    cleaned = []
    for msg in messages:
        role = msg.get("role", "user")

        if role == "tool_result" and msg.get("tool_use_id") in orphaned_results:
            # Drop tool_results with no matching tool_use
            continue

        if role == "assistant" and msg.get("tool_calls"):
            # Check if ALL tool_calls in this message are orphaned
            msg_tc_ids = {tc["id"] for tc in msg.get("tool_calls", [])}
            if msg_tc_ids.issubset(orphaned_uses):
                # Every tool_call is orphaned — keep only the text content
                if msg.get("content"):
                    cleaned.append({"role": "assistant", "content": msg["content"]})
                continue
            elif msg_tc_ids & orphaned_uses:
                # Some tool_calls are orphaned — remove only those
                good_tcs = [tc for tc in msg["tool_calls"] if tc["id"] not in orphaned_uses]
                new_msg = dict(msg)
                new_msg["tool_calls"] = good_tcs
                cleaned.append(new_msg)
                continue

        cleaned.append(msg)

    # Strip leading tool_results or assistant+tool_calls from the start
    while cleaned and cleaned[0].get("role") == "tool_result":
        cleaned = cleaned[1:]
    if cleaned and cleaned[0].get("role") == "assistant" and cleaned[0].get("tool_calls"):
        cleaned = cleaned[1:]
        while cleaned and cleaned[0].get("role") == "tool_result":
            cleaned = cleaned[1:]

    return cleaned


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

    # Sanitize messages: fix orphaned tool_use/tool_result pairs anywhere in history.
    # This can happen when a session is interrupted mid-tool-call, context is truncated,
    # or the user sends input that breaks a tool exchange.
    messages = _sanitize_messages(messages)

    # Convert messages to Anthropic format
    api_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool_result":
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
