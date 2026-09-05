"""Tests for the LLM provider layer.

No network calls, no subprocess spawns, no live Claude CLI. Every test gets
an isolated temp cache dir via the autouse fixture below.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import settings
from app.llm.base import LLMError, get_provider
from app.llm.claude_cli import ClaudeCliProvider
from app.llm.tagging import tag_document_clauses

NOTICE_CLAUSE = (
    "7-2",
    "Termination by Notice",
    "Either party may terminate this Tenancy Agreement by giving the other "
    "party not less than sixty (60) days' written notice. Notice under this "
    "clause shall be delivered in accordance with clause 12.",
)

INDEMNITY_CLAUSE = (
    "9-1",
    "Indemnity",
    "The Tenant shall indemnify and hold harmless the Landlord against any "
    "loss, damage, cost or expense arising from the Tenant's breach of this "
    "Agreement or negligence in the use of the premises.",
)


@pytest.fixture(autouse=True)
def temp_cache_dir(tmp_path, monkeypatch):
    """Every test gets its own cache dir and an online (non-offline) setting."""
    monkeypatch.setattr(settings, "llm_cache_dir", tmp_path / "llm_cache")
    monkeypatch.setattr(settings, "offline", False)
    yield


def test_get_provider_mock_round_trip():
    provider = get_provider("mock")
    assert provider.name == "mock"
    assert provider.complete_json("no clause markers in here", {}) == {}


def test_get_provider_unknown_name_raises():
    with pytest.raises(LLMError):
        get_provider("not-a-real-provider")


def test_tag_document_clauses_notice_and_indemnity():
    mapping = tag_document_clauses(
        "Warehouse Lease",
        [NOTICE_CLAUSE, INDEMNITY_CLAUSE],
        provider=get_provider("mock"),
    )

    notice_concepts = dict(mapping["7-2"])
    indemnity_concepts = dict(mapping["9-1"])

    assert notice_concepts["notice-period"] == "Notice Period"
    assert "termination" in notice_concepts

    assert indemnity_concepts["indemnity"] == "Indemnity"


def test_tag_document_clauses_empty_list_short_circuits():
    calls = {"count": 0}

    class CountingProvider:
        name = "counting"

        def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
            calls["count"] += 1
            return {}

    assert tag_document_clauses("Empty Doc", [], provider=CountingProvider()) == {}
    assert calls["count"] == 0


def test_tag_document_clauses_degrades_on_llm_error():
    class RaisingProvider:
        name = "raising"

        def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
            raise LLMError("boom")

    mapping = tag_document_clauses(
        "Warehouse Lease",
        [NOTICE_CLAUSE, INDEMNITY_CLAUSE],
        provider=RaisingProvider(),
    )
    assert mapping == {"7-2": [], "9-1": []}


def test_cache_hit_avoids_second_provider_call(monkeypatch):
    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1

        class FakeResult:
            returncode = 0
            stdout = json.dumps({"result": '{"7-2": ["Notice Period"]}'})
            stderr = ""

        return FakeResult()

    monkeypatch.setattr("app.llm.claude_cli.subprocess.run", fake_run)

    provider = ClaudeCliProvider()
    first = provider.complete_json("some prompt", {})
    second = provider.complete_json("some prompt", {})

    assert first == {"7-2": ["Notice Period"]}
    assert second == first
    assert calls["count"] == 1


def test_malformed_provider_output_raises_llm_error(monkeypatch):
    def fake_run(*args, **kwargs):
        class FakeResult:
            returncode = 0
            stdout = "not json at all"
            stderr = ""

        return FakeResult()

    monkeypatch.setattr("app.llm.claude_cli.subprocess.run", fake_run)

    provider = ClaudeCliProvider()
    with pytest.raises(LLMError):
        provider.complete_json("some other prompt", {})


def test_offline_claude_cli_raises_without_spawning(monkeypatch):
    monkeypatch.setattr(settings, "offline", True)

    def fake_run(*args, **kwargs):
        raise AssertionError("should not spawn a subprocess while offline")

    monkeypatch.setattr("app.llm.claude_cli.subprocess.run", fake_run)

    provider = ClaudeCliProvider()
    with pytest.raises(LLMError):
        provider.complete_json("unique offline prompt", {})
