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


def _validate_api_messages(api_messages):
    """Fix orphaned tool_use/tool_result in already-converted API messages.

    Operates on the exact format Anthropic receives, so nothing slips through.
    """
    # Step 1: Collect all tool_use IDs and tool_result IDs
    tool_use_ids = set()
    tool_result_ids = set()
    for msg in api_messages:
        if not isinstance(msg.get("content"), list):
            continue
        for block in msg["content"]:
            if block.get("type") == "tool_use":
                tool_use_ids.add(block["id"])
            elif block.get("type") == "tool_result":
                tool_result_ids.add(block["tool_use_id"])

    # Step 2: Find orphans
    orphaned_uses = tool_use_ids - tool_result_ids
    orphaned_results = tool_result_ids - tool_use_ids

    if not orphaned_uses and not orphaned_results:
        return api_messages

    log.warning(
        "Validating API messages: %d orphaned tool_use, %d orphaned tool_result",
        len(orphaned_uses), len(orphaned_results),
    )

    # Step 3: Strip orphaned blocks
    cleaned = []
    for msg in api_messages:
        if not isinstance(msg.get("content"), list):
            cleaned.append(msg)
            continue

        new_blocks = []
        for block in msg["content"]:
            if block.get("type") == "tool_use" and block["id"] in orphaned_uses:
                continue
            if block.get("type") == "tool_result" and block["tool_use_id"] in orphaned_results:
                continue
            new_blocks.append(block)

        if new_blocks:
            cleaned.append({**msg, "content": new_blocks})
        # else: drop empty message entirely

    # Step 4: Merge consecutive same-role messages
    merged = []
    for msg in cleaned:
        if merged and merged[-1]["role"] == msg["role"]:
            prev = merged[-1]
            # Normalize both to list-of-blocks
            prev_content = prev["content"] if isinstance(prev["content"], list) else [{"type": "text", "text": prev["content"]}]
            cur_content = msg["content"] if isinstance(msg["content"], list) else [{"type": "text", "text": msg["content"]}]
            merged[-1] = {**prev, "content": prev_content + cur_content}
        else:
            merged.append(msg)

    return merged


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

    # Validate: fix orphaned tool_use/tool_result pairs in the final API format.
    # This self-heals corrupted history from interrupted sessions or truncated context.
    api_messages = _validate_api_messages(api_messages)

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
