"""Provider interface.

The demo runs on `claude_cli`. The production story is `local` - a strong
on-prem model so privileged client documents never leave the firm. Both satisfy
the same contract, so swapping is a config change, not a rewrite.
"""
from typing import Any, Protocol

from app.config import settings


class LLMProvider(Protocol):
    name: str

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object conforming to `schema`. Must raise LLMError on
        malformed output rather than returning a partial dict."""
        ...


class LLMError(RuntimeError):
    pass


def get_provider(name: str | None = None) -> LLMProvider:
    """Factory dispatching on settings.llm_provider.

    Imports are local to avoid import cycles (each provider module imports
    `LLMError` from this module).
    """
    provider_name = name or settings.llm_provider

    if provider_name == "claude_cli":
        from app.llm.claude_cli import ClaudeCliProvider

        return ClaudeCliProvider()
    if provider_name == "local":
        from app.llm.local import LocalProvider

        return LocalProvider()
    if provider_name == "mock":
        from app.llm.mock import MockProvider

        return MockProvider()

    raise LLMError(f"unknown llm provider: {provider_name!r}")
