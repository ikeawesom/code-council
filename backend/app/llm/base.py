"""Provider interface.

The demo runs on `claude_cli`. The production story is `local` - a strong
on-prem model so privileged client documents never leave the firm. Both satisfy
the same contract, so swapping is a config change, not a rewrite.
"""
from typing import Any, Protocol


class LLMProvider(Protocol):
    name: str

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object conforming to `schema`. Must raise LLMError on
        malformed output rather than returning a partial dict."""
        ...


class LLMError(RuntimeError):
    pass


def get_provider(name: str | None = None) -> LLMProvider:
    """Factory dispatching on settings.llm_provider."""
    # TODO(M3): claude_cli | local | mock
    raise NotImplementedError
