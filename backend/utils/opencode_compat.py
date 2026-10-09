"""
OpenCode Go (https://opencode.ai/zen/go) compatibility helpers.

OpenCode Go endpoints are OpenAI-compatible but with extra requirements:
1. Every request must carry a stable ``x-opencode-session`` header
   (see https://opencode.ai/docs/go/#where-can-i-use-it).
2. Clients should identify themselves with a custom User-Agent instead of
   a generic SDK/HTTP-library name.
3. Some models (gpt-*-luna, grok-*, muse-spark-*) are only served through
   the OpenAI *Responses* API (``/responses``), not ``/chat/completions``.

This module centralises that protocol knowledge so both the config test
endpoint and the game runtime behave identically.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

APP_USER_AGENT = "killer-agent-game/1.0"


def is_opencode_go(base_url: Optional[str]) -> bool:
    """Whether the endpoint points at OpenCode (Go / Zen gateway)."""
    return bool(base_url) and "opencode.ai" in base_url


def needs_responses_api(model: Optional[str]) -> bool:
    """Whether a model id is only available via the OpenAI Responses API."""
    model_id = (model or "").lower().rpartition("/")[-1]
    if model_id.endswith("-luna"):
        return True
    if model_id.startswith(("grok-", "muse-spark")):
        return True
    return False


def build_opencode_headers(session_id: Optional[str] = None) -> Dict[str, str]:
    """Headers OpenCode Go requires on top of the standard ones."""
    return {
        "x-opencode-session": session_id or f"killer-{uuid.uuid4()}",
        "User-Agent": APP_USER_AGENT,
    }


def normalize_responses_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Responses API payload into a chat-completions-like dict.

    The rest of the codebase consumes chat-completions shaped responses
    (``choices[0].message.content`` + ``usage``), so normalising here keeps
    call sites unchanged.
    """
    content_parts: List[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                content_parts.append(part.get("text") or "")
    content = "".join(content_parts)

    usage = data.get("usage") or {}
    input_tokens = usage.get("input_tokens") or 0
    output_tokens = usage.get("output_tokens") or 0
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": usage.get("total_tokens") or (input_tokens + output_tokens),
        },
    }


def supports_temperature(model: Optional[str]) -> bool:
    """GPT-*-luna models (GPT-5 family) only support temperature=1.

    Sending any other temperature makes the gateway fail with an unhelpful
    ``{"model": ...}`` 400 body, so we omit the parameter instead.
    """
    model_id = (model or "").lower().rpartition("/")[-1]
    return not model_id.endswith("-luna")


def build_responses_payload(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    """Map chat-completions params onto the Responses API payload.

    The Responses API does not support frequency/presence penalties and uses
    ``max_output_tokens`` instead of ``max_tokens``.
    """
    payload: Dict[str, Any] = {"model": model, "input": messages}
    if temperature is not None and (temperature == 1 or supports_temperature(model)):
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_output_tokens"] = max_tokens
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    return payload
