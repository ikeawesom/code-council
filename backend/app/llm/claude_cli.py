"""Demo provider: shells out to the Claude Code CLI in headless mode.

    claude -p "<prompt>" --model <alias> --output-format json

Verified flags: -p/--print, --model, --output-format json. Every call goes
through cache.py first, so a rehearsed demo makes zero live calls. When
`settings.offline` is set the provider refuses to spawn at all - the daily
run must be fully replayable with no network.
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from app.config import settings
from app.llm import cache
from app.llm.base import LLMError

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class ClaudeCliProvider:
    """Runs `claude -p ... --output-format json` as a subprocess."""

    name = "claude_cli"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        key = cache.make_key(self.name, settings.claude_model, prompt, schema)
        cached = cache.get(key)
        if cached is not None:
            return cached

        if settings.offline:
            raise LLMError("claude_cli provider unavailable while offline (LEX_OFFLINE=1)")

        try:
            # The prompt goes in on stdin, never as an argv element: Windows caps
            # a command line at 32,767 characters and a batched tagging prompt for
            # a 100+ clause contract is several times that. As an argument it
            # would fail as an OSError -> LLMError -> silently untagged vault.
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    "--model",
                    settings.claude_model,
                    "--output-format",
                    "json",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=settings.claude_timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise LLMError(f"claude CLI failed to run: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise LLMError(f"claude CLI exited {result.returncode}: {stderr}")

        text = _extract_assistant_text(result.stdout)
        parsed = _extract_json_object(text)
        cache.set(key, parsed)
        return parsed


def _extract_assistant_text(stdout: str) -> str:
    """Pull the assistant's reply text out of the CLI's JSON envelope."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise LLMError(f"claude CLI returned a non-JSON envelope: {exc}") from exc

    if isinstance(envelope, dict):
        result = envelope.get("result")
        if isinstance(result, str):
            return result

        for key in ("content", "message"):
            node = envelope.get(key)
            if key == "message" and isinstance(node, dict):
                node = node.get("content")
            if isinstance(node, list):
                parts = [block.get("text", "") for block in node if isinstance(block, dict)]
                text = "\n".join(part for part in parts if part)
                if text:
                    return text

    raise LLMError("claude CLI envelope did not contain assistant text")


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract a JSON object from assistant text, tolerating fences/prose."""
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else None

    if candidate is None:
        obj_match = _JSON_OBJECT_RE.search(text)
        candidate = obj_match.group(0) if obj_match else None

    if candidate is None:
        raise LLMError("no JSON object found in claude CLI output")

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMError(f"malformed JSON from claude CLI: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMError("claude CLI JSON was not an object")

    return parsed
