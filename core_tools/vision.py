"""Core tool: vision — analyze images using the current model's provider."""

import base64
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

from config import config

MODELS_PATH = os.path.join(config.seed_dir, "models.json")


def _load_models():
    with open(MODELS_PATH, "r") as f:
        return json.load(f)


def _get_vision_model():
    """Get the current model if it supports vision, or find one that does."""
    models = _load_models()
    current = config.model

    # Current model supports vision? Use it.
    if current in models and "vision" in models[current].get("capabilities", []):
        info = models[current]
        return current, info["provider"]

    # Find any model that supports vision, prefer same provider
    current_provider = models.get(current, {}).get("provider")
    for mid, m in models.items():
        if "vision" in m.get("capabilities", []) and m["provider"] == current_provider:
            return mid, m["provider"]

    # Any vision model
    for mid, m in models.items():
        if "vision" in m.get("capabilities", []):
            return mid, m["provider"]

    return None, None


def _encode_image(path):
    """Read and base64-encode an image file."""
    suffix = Path(path).suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/png")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, media_type


async def _call_anthropic(image_data, media_type, prompt, api_key, model):
    """Call Anthropic vision API."""
    payload = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["content"][0]["text"]


async def _call_openai(image_data, media_type, prompt, api_key, model):
    """Call OpenAI vision API."""
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                },
                {"type": "text", "text": prompt},
            ],
        }],
        "max_completion_tokens": 1024,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]


async def execute(
    image_path: str = None,
    prompt: str = "Describe in detail what you see in this image.",
) -> str:
    if not image_path:
        return "Error: image_path is required. Take a screenshot first, then pass the path."

    if not os.path.isabs(image_path):
        image_path = os.path.join(config.working_dir, image_path)

    if not os.path.exists(image_path):
        return f"Error: file not found: {image_path}"

    # Find a vision-capable model
    vision_model, provider = _get_vision_model()
    if not vision_model:
        return "Error: no vision-capable model available in models.json"

    # Encode
    image_data, media_type = _encode_image(image_path)

    try:
        if provider == "anthropic":
            api_key = config.anthropic_api_key
            if not api_key:
                return "Error: ANTHROPIC_API_KEY not set"
            analysis = await _call_anthropic(image_data, media_type, prompt, api_key, vision_model)

        elif provider == "openai":
            api_key = config.openai_api_key
            if not api_key:
                return "Error: OPENAI_API_KEY not set"
            analysis = await _call_openai(image_data, media_type, prompt, api_key, vision_model)

        else:
            return f"Error: vision not supported for provider '{provider}' yet"

        return f"Image: {image_path}\nModel: {vision_model}\n\n{analysis}"

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:300]
        return f"Error: HTTP {e.code} — {body}"
    except Exception as e:
        return f"Error: {e}"


tool = {
    "name": "vision",
    "description": (
        "Analyze an image using AI vision. Uses the current model's provider "
        "(Anthropic or OpenAI). Requires an image_path — take a screenshot first if needed. "
        "Use this to understand what's on screen, read text from images, or analyze visual content."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image. If omitted, uses the most recent screenshot.",
            },
            "prompt": {
                "type": "string",
                "description": "What to analyze or ask about the image. Default: describe what you see.",
            },
        },
        "required": [],
    },
    "execute": execute,
}
