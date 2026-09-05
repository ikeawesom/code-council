"""On-prem provider: Ollama-compatible /api/chat with format=json.

This is the deployment target for a real firm - no client data leaves the
network. Kept in the demo repo so the architecture claim is verifiable: it is
a real HTTP implementation against Ollama's chat API, not a stub.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings
from app.llm import cache
from app.llm.base import LLMError


class LocalProvider:
    """Calls a local Ollama server's `/api/chat` endpoint."""

    name = "local"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        key = cache.make_key(self.name, settings.local_model, prompt, schema)
        cached = cache.get(key)
        if cached is not None:
            return cached

        try:
            response = httpx.post(
                f"{settings.local_base_url}/api/chat",
                json={
                    "model": settings.local_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "format": "json",
                    "stream": False,
                },
                timeout=settings.claude_timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"local provider request failed: {exc}") from exc

        try:
            envelope = response.json()
        except json.JSONDecodeError as exc:
            raise LLMError(f"local provider returned a non-JSON response: {exc}") from exc

        content = None
        if isinstance(envelope, dict):
            message = envelope.get("message")
            if isinstance(message, dict):
                content = message.get("content")

        if not isinstance(content, str):
            raise LLMError("local provider response missing message.content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"malformed JSON from local provider: {exc}") from exc

        if not isinstance(parsed, dict):
            raise LLMError("local provider content was not a JSON object")

        cache.set(key, parsed)
        return parsed
