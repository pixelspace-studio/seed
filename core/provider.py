"""AI provider — routes to Anthropic, OpenAI, or Google based on model."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field

import anthropic
import openai
import google.genai as genai

log = logging.getLogger(__name__)

MODELS_PATH = None  # set lazily

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


def _get_provider(model: str) -> str:
    """Look up provider from models.json."""
    import os
    global MODELS_PATH
    if not MODELS_PATH:
        MODELS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "registry", "models.json")
    with open(MODELS_PATH) as f:
        models = json.load(f)
    info = models.get(model, {})
    return info.get("provider", "anthropic")


# ---------------------------------------------------------------------------
# Message validation (shared across providers)
# ---------------------------------------------------------------------------

def _validate_api_messages(api_messages):
    """Fix orphaned tool_use/tool_result in already-converted API messages."""
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

    orphaned_uses = tool_use_ids - tool_result_ids
    orphaned_results = tool_result_ids - tool_use_ids

    if not orphaned_uses and not orphaned_results:
        return api_messages

    log.warning(
        "Validating API messages: %d orphaned tool_use, %d orphaned tool_result",
        len(orphaned_uses), len(orphaned_results),
    )

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

    merged = []
    for msg in cleaned:
        if merged and merged[-1]["role"] == msg["role"]:
            prev = merged[-1]
            prev_content = prev["content"] if isinstance(prev["content"], list) else [{"type": "text", "text": prev["content"]}]
            cur_content = msg["content"] if isinstance(msg["content"], list) else [{"type": "text", "text": msg["content"]}]
            merged[-1] = {**prev, "content": prev_content + cur_content}
        else:
            merged.append(msg)

    return merged


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

async def _send_anthropic(messages, tools, model, system, api_key):
    client = anthropic.AsyncAnthropic(api_key=api_key)

    anthropic_tools = [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in tools
    ]

    api_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool_result":
            api_messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": msg["tool_use_id"], "content": str(msg.get("result", ""))}],
            })
        elif role == "assistant":
            content_blocks = []
            if msg.get("content"):
                content_blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls", []):
                content_blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["args"]})
            if content_blocks:
                api_messages.append({"role": "assistant", "content": content_blocks})
        else:
            api_messages.append({"role": "user", "content": msg.get("content", "")})

    api_messages = _validate_api_messages(api_messages)

    if api_messages and api_messages[0].get("role") != "user":
        api_messages = [{"role": "user", "content": "(continuing conversation)"}] + api_messages

    max_retries = 3
    for attempt in range(max_retries):
        try:
            kwargs = {"model": model, "max_tokens": 8192, "messages": api_messages}
            if system:
                kwargs["system"] = system
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            response = await client.messages.create(**kwargs)

            content = ""
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(id=block.id, name=block.name, args=dict(block.input)))

            return ProviderResponse(
                content=content,
                tool_calls=tool_calls,
                usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
            )

        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            log.warning(f"Anthropic error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
        except anthropic.APIError as e:
            log.error(f"Anthropic API error: {e}")
            raise


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

async def _send_openai(messages, tools, model, system, api_key):
    client = openai.AsyncOpenAI(api_key=api_key)

    openai_tools = [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
        for t in tools
    ]

    api_messages = []
    if system:
        api_messages.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool_result":
            api_messages.append({
                "role": "tool",
                "tool_call_id": msg["tool_use_id"],
                "content": str(msg.get("result", "")),
            })
        elif role == "assistant":
            m = {"role": "assistant"}
            if msg.get("content"):
                m["content"] = msg["content"]
            if msg.get("tool_calls"):
                m["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
                    }
                    for tc in msg["tool_calls"]
                ]
            api_messages.append(m)
        else:
            api_messages.append({"role": "user", "content": msg.get("content", "")})

    max_retries = 3
    for attempt in range(max_retries):
        try:
            kwargs = {"model": model, "messages": api_messages}
            if openai_tools:
                kwargs["tools"] = openai_tools

            response = await client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            content = choice.message.content or ""
            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        args=json.loads(tc.function.arguments),
                    ))

            return ProviderResponse(
                content=content,
                tool_calls=tool_calls,
                usage={
                    "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "output_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )

        except (openai.RateLimitError, openai.InternalServerError) as e:
            log.warning(f"OpenAI error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
        except openai.APIError as e:
            log.error(f"OpenAI API error: {e}")
            raise


# ---------------------------------------------------------------------------
# Google (Gemini)
# ---------------------------------------------------------------------------

async def _send_google(messages, tools, model, system, api_key):
    client = genai.Client(api_key=api_key)

    # Build tools
    google_tools = []
    for t in tools:
        google_tools.append(genai.types.Tool(
            function_declarations=[
                genai.types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["parameters"],
                )
            ]
        ))

    # Build contents
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool_result":
            contents.append(genai.types.Content(
                role="user",
                parts=[genai.types.Part(function_response=genai.types.FunctionResponse(
                    name=msg.get("tool", "unknown"),
                    response={"result": str(msg.get("result", ""))},
                ))],
            ))
        elif role == "assistant":
            parts = []
            if msg.get("content"):
                parts.append(genai.types.Part(text=msg["content"]))
            for tc in msg.get("tool_calls", []):
                parts.append(genai.types.Part(function_call=genai.types.FunctionCall(
                    name=tc["name"],
                    args=tc["args"],
                )))
            if parts:
                contents.append(genai.types.Content(role="model", parts=parts))
        else:
            contents.append(genai.types.Content(
                role="user",
                parts=[genai.types.Part(text=msg.get("content", ""))],
            ))

    config = genai.types.GenerateContentConfig(
        system_instruction=system if system else None,
        tools=google_tools if google_tools else None,
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
            )

            content = ""
            tool_calls = []
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        content += part.text
                    elif part.function_call:
                        fc = part.function_call
                        tool_calls.append(ToolCall(
                            id=f"call_{uuid.uuid4().hex[:12]}",
                            name=fc.name,
                            args=dict(fc.args) if fc.args else {},
                        ))

            usage_meta = getattr(response, "usage_metadata", None)
            return ProviderResponse(
                content=content,
                tool_calls=tool_calls,
                usage={
                    "input_tokens": getattr(usage_meta, "prompt_token_count", 0) or 0,
                    "output_tokens": getattr(usage_meta, "candidates_token_count", 0) or 0,
                },
            )

        except Exception as e:
            log.warning(f"Google error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

async def send(
    messages: list[dict],
    tools: list[dict],
    model: str,
    system: str = "",
    cfg=None,
) -> ProviderResponse:
    """Route to the correct provider based on the model."""
    provider = _get_provider(model)

    if provider == "openai":
        return await _send_openai(messages, tools, model, system, cfg.openai_api_key)
    elif provider == "google":
        return await _send_google(messages, tools, model, system, cfg.google_ai_api_key)
    else:
        return await _send_anthropic(messages, tools, model, system, cfg.anthropic_api_key)
