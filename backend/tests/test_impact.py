"""Tests for analysis/impact.py (the judge) and the mock provider's judge mode.

No network, no subprocess. Candidates are built by hand - retrieval has its
own tests.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.analysis.impact import (
    CANDIDATE_HEADER,
    ITEM_HEADER,
    PROMPT_HEADER,
    RESPONSE_SCHEMA,
    ImpactAssessment,
    apply_edits,
    assess,
    build_prompt,
    parse_response,
)
from app.analysis.retrieve import Candidate
from app.config import settings
from app.llm.base import LLMError
from app.llm.mock import MockProvider
from app.models import Clause, Document, ParliamentItem

LEASE = Document(id=1, slug="lease", title="Warehouse Lease", sector="real-estate")

NOTICE_CLAUSE = Clause(
    id=1, document_id=1, anchor="7-2", ref="lease#7-2", number="7.2",
    heading="Termination by Notice",
    text="Either party may terminate this lease by giving one (1) month's written notice.",
)
RENT_CLAUSE = Clause(
    id=2, document_id=1, anchor="3", ref="lease#3", number="3", heading="Rent",
    text="The tenant shall pay the rent monthly in advance by bank transfer.",
)
GOVERNING_CLAUSE = Clause(
    id=3, document_id=1, anchor="12", ref="lease#12", number="12", heading="Governing law",
    text="This lease is governed by the laws of Singapore.",
)

BILL = ParliamentItem(
    id=1, sprs_id="demo-x", slug="x", title="Tenancies (Notice Periods) (Amendment) Bill",
    sitting_date="2026-08-05", item_type="bill", legislation_type="amendment",
    speaker="Minister",
    body_text=(
        "This Bill amends the law so that a landlord must give three months' written "
        "notice to terminate a tenancy. Any shorter notice period is void."
    ),
)


def _cand(clause: Clause, score: float = 10.0) -> Candidate:
    return Candidate(clause=clause, document=LEASE, score=score, bm25=score, concept_overlap=0)


CANDIDATES = [_cand(NOTICE_CLAUSE, 20), _cand(RENT_CLAUSE, 8), _cand(GOVERNING_CLAUSE, 4)]


@pytest.fixture(autouse=True)
def temp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "llm_cache_dir", tmp_path / "llm_cache")
    monkeypatch.setattr(settings, "offline", False)


class _RaisingProvider:
    name = "raising"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise LLMError("boom")


class _CannedProvider:
    name = "canned"

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(prompt)
        return self.response


# --- prompt shape -----------------------------------------------------------


def test_prompt_markers_are_load_bearing():
    prompt = build_prompt(BILL, CANDIDATES)
    assert prompt.startswith(PROMPT_HEADER)
    assert ITEM_HEADER in prompt
    assert prompt.count(CANDIDATE_HEADER) == 3
    assert f"{CANDIDATE_HEADER}lease#7-2\nDocument: Warehouse Lease (real-estate)" in prompt
    assert "Heading: 7.2 Termination by Notice" in prompt
    assert prompt.index(ITEM_HEADER) < prompt.index(CANDIDATE_HEADER)


def test_prompt_truncates_long_item_body():
    long_item = ParliamentItem(
        sprs_id="l", slug="l", title="Long", sitting_date="2026-08-05", body_text="word " * 5000
    )
    assert len(build_prompt(long_item, CANDIDATES[:1])) < 10000


# --- assess() with the mock ---------------------------------------------------


def test_assess_with_mock_returns_one_per_candidate():
    results = assess(BILL, CANDIDATES, MockProvider())
    assert [r.clause_ref for r in results] == ["lease#7-2", "lease#3", "lease#12"]
    notice, rent, law = results
    assert notice.impacted and notice.severity == "high"
    assert notice.suggested_text and notice.suggested_text != NOTICE_CLAUSE.text
    assert "three (3) months'" in notice.suggested_text
    assert "Notice Period" in notice.rationale or "Termination" in notice.rationale
    assert not rent.impacted and rent.suggested_text == ""
    assert not law.impacted
    assert all(r.legislation_type == "amendment" for r in results)


def test_assess_mock_is_deterministic():
    first = assess(BILL, CANDIDATES, MockProvider())
    second = assess(BILL, CANDIDATES, MockProvider())
    assert first == second


def test_assess_llm_error_degrades_to_empty(caplog):
    with caplog.at_level("WARNING"):
        assert assess(BILL, CANDIDATES, _RaisingProvider()) == []
    assert "impact assessment failed" in caplog.text


def test_assess_no_candidates_makes_no_call():
    provider = _CannedProvider({"assessments": []})
    assert assess(BILL, [], provider) == []
    assert provider.prompts == []


def test_assess_passes_schema_and_prompt_to_provider():
    provider = _CannedProvider({"assessments": []})
    assess(BILL, CANDIDATES[:1], provider)
    assert len(provider.prompts) == 1
    assert RESPONSE_SCHEMA["required"] == ["assessments"]


# --- parse_response() defensiveness ----------------------------------------------


def test_parse_response_fills_missing_and_drops_unknown():
    response = {
        "legislation_type": "new_legislation",
        "assessments": [
            {"clause_ref": "lease#7-2", "impacted": True, "severity": "medium",
             "rationale": "r", "suggested_text": None},
            {"clause_ref": "other#1", "impacted": True, "severity": "high", "rationale": "x"},
        ],
    }
    results = parse_response(response, CANDIDATES)
    assert [r.clause_ref for r in results] == ["lease#7-2", "lease#3", "lease#12"]
    assert results[0] == ImpactAssessment(
        clause_ref="lease#7-2", impacted=True, severity="medium", rationale="r",
        suggested_text="", legislation_type="new_legislation",
    )
    assert results[1].impacted is False and results[1].rationale == "not assessed"


def test_parse_response_bad_severity_and_type_are_normalised():
    response = {
        "legislation_type": "repeal",
        "assessments": [
            {"clause_ref": "lease#3", "impacted": "yes", "severity": "critical", "rationale": 1}
        ],
    }
    results = parse_response(response, [_cand(RENT_CLAUSE)])
    assert results[0].severity == "low"
    assert results[0].impacted is True
    assert results[0].legislation_type is None
    assert results[0].rationale == "1"


def test_apply_edits_happy_path_and_rejections():
    text = "give one (1) month's notice. Rent is due monthly. Notice must be written."
    good = [{"find": "one (1) month's", "replace": "three (3) months'"}]
    assert apply_edits(text, good) == text.replace("one (1) month's", "three (3) months'")
    assert apply_edits(text, [{"find": "month", "replace": "x"}]) == ""  # ambiguous (x2)
    assert apply_edits(text, [{"find": "absent", "replace": "x"}]) == ""
    assert apply_edits(text, [{"find": "Rent", "replace": "Rent"}]) == ""  # no change
    assert apply_edits(text, None) == "" and apply_edits(text, []) == ""
    assert apply_edits(text, [{"find": "", "replace": "x"}]) == ""
    assert apply_edits(text, ["not a dict"]) == ""


def test_parse_response_applies_edits_to_full_clause():
    response = {
        "assessments": [
            {"clause_ref": "lease#7-2", "impacted": True, "severity": "high", "rationale": "r",
             "suggested_text": None,
             "edits": [{"find": "one (1) month's", "replace": "three (3) months'"}]}
        ]
    }
    result = parse_response(response, [_cand(NOTICE_CLAUSE)])[0]
    assert result.suggested_text == NOTICE_CLAUSE.text.replace(
        "one (1) month's", "three (3) months'"
    )


def test_parse_response_tolerates_garbage_shape():
    results = parse_response({"assessments": "nope"}, [_cand(RENT_CLAUSE)])
    assert len(results) == 1 and not results[0].impacted


# --- mock provider keeps its tagging behaviour ---------------------------------------


def test_mock_tagging_mode_unchanged():
    prompt = (
        'Identify legal concepts present in each clause of "Lease".\n\n'
        "## Clause 7-2: Termination\nEither party may terminate on one month's written notice.\n"
    )
    assert MockProvider().complete_json(prompt, {}) == {"7-2": ["Notice Period", "Termination"]}


def test_mock_judge_fallback_sentence_when_no_period_phrase():
    cand = _cand(Clause(id=9, document_id=1, anchor="9", ref="lease#9",
                        text="The tenant may terminate this lease at any time."))
    result = assess(BILL, [cand], MockProvider())[0]
    assert result.impacted
    assert result.severity == "medium"
    assert result.suggested_text.startswith(cand.clause.text)
    assert "minimum prescribed by written law" in result.suggested_text
