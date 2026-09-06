"""Tests for analysis/pipeline.py - the queue, gate, budget, judge and
legislation_type override, with retrieval and the judge replaced by fakes.

In-memory sqlite; the vault dir is redirected to tmp_path wherever the
override rewrites a parliament item file.
"""
from __future__ import annotations

from typing import Any

import frontmatter
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.analysis import pipeline
from app.analysis.impact import ImpactAssessment
from app.analysis.retrieve import Candidate
from app.config import settings
from app.models import Clause, Document, ParliamentItem, Proposal, Task
from app.scraper.normalize import persist_items


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vault_dir", tmp_path / "vault")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class _Provider:
    name = "fake"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("pipeline tests never call the provider directly")


def _seed(session: Session, n_items: int = 3) -> tuple[Document, Clause, list[ParliamentItem]]:
    doc = Document(slug="lease", title="Lease", sector="real-estate")
    session.add(doc)
    session.flush()
    clause = Clause(document_id=doc.id, anchor="7-2", ref="lease#7-2", text="one month notice")
    session.add(clause)
    items = [
        ParliamentItem(
            sprs_id=f"report:2026-08-05:oa:item-{i}", slug=f"item-{i}", title=f"Item {i}",
            sitting_date="2026-08-05", legislation_type="amendment",
        )
        for i in range(n_items)
    ]
    session.add_all(items)
    session.commit()
    return doc, clause, items


class _FakeIndex:
    """Scores are keyed by item slug; anything else scores 0."""

    scores: dict[str, float] = {}
    doc: Document
    clause: Clause

    @classmethod
    def build(cls, session: Session) -> _FakeIndex:
        return cls()

    def __len__(self) -> int:
        return 1

    def candidates(self, item: ParliamentItem, k: int | None = None) -> list[Candidate]:
        score = self.scores.get(item.slug, 0.0)
        return [Candidate(clause=self.clause, document=self.doc, score=score, bm25=score,
                          concept_overlap=0)]


def _install_fakes(monkeypatch, doc, clause, scores, verdicts):
    """`verdicts` maps item slug -> list[ImpactAssessment] (or [] for a judge failure)."""
    _FakeIndex.scores = scores
    _FakeIndex.doc = doc
    _FakeIndex.clause = clause
    judged: list[str] = []

    def fake_assess(item, candidates, provider=None):
        judged.append(item.slug)
        return verdicts.get(item.slug, [])

    monkeypatch.setattr(pipeline, "ClauseIndex", _FakeIndex)
    monkeypatch.setattr(pipeline, "passes_gate", lambda cands, threshold=None: cands[0].score >= 10)
    monkeypatch.setattr(pipeline, "assess", fake_assess)
    return judged


IMPACTED = [ImpactAssessment("lease#7-2", True, "high", "bites", "three months notice")]
NOT_IMPACTED = [ImpactAssessment("lease#7-2", False, "low", "no")]


def test_untasked_items_excludes_tasked(session):
    _doc, _clause, items = _seed(session)
    session.add(Task(parliament_item_id=items[1].id, reference="CC-2026-0001"))
    session.commit()
    assert [i.slug for i in pipeline.untasked_items(session)] == ["item-0", "item-2"]


def test_gated_item_is_never_judged(session, monkeypatch):
    doc, clause, _items = _seed(session, n_items=1)
    judged = _install_fakes(monkeypatch, doc, clause, {"item-0": 3.0}, {})
    summary = pipeline.run_analysis(session, provider=_Provider())
    assert (summary.considered, summary.gated_out, summary.judged) == (1, 1, 0)
    assert judged == []
    assert session.exec(select(Task)).all() == []


def test_impacted_item_becomes_task_and_leaves_queue(session, monkeypatch):
    doc, clause, items = _seed(session, n_items=2)
    _install_fakes(monkeypatch, doc, clause, {"item-0": 30.0, "item-1": 1.0}, {"item-0": IMPACTED})
    summary = pipeline.run_analysis(session, provider=_Provider())
    session.commit()
    assert (summary.already_tasked, summary.considered) == (0, 2)
    assert summary.tasks_created == 1 and summary.proposals_created == 1
    assert len(summary.task_references) == 1
    assert summary.task_references[0].startswith("CC-")
    assert summary.provider == "fake"
    task = session.exec(select(Task)).one()
    assert task.parliament_item_id == items[0].id and task.severity == "high"
    proposal = session.exec(select(Proposal)).one()
    assert proposal.suggested_text == "three months notice"
    assert [i.slug for i in pipeline.untasked_items(session)] == ["item-1"]

    again = pipeline.run_analysis(session, provider=_Provider())
    assert (again.considered, again.tasks_created) == (1, 0)
    # The re-run reports the tasked item as skipped, not as a silent shortfall.
    assert again.already_tasked == 1


def test_judge_failure_leaves_item_for_retry(session, monkeypatch):
    doc, clause, _items = _seed(session, n_items=1)
    _install_fakes(monkeypatch, doc, clause, {"item-0": 30.0}, {"item-0": []})
    summary = pipeline.run_analysis(session, provider=_Provider())
    assert (summary.judged, summary.judge_failures, summary.tasks_created) == (1, 1, 0)
    assert len(pipeline.untasked_items(session)) == 1


def test_no_impact_creates_nothing(session, monkeypatch):
    doc, clause, _items = _seed(session, n_items=1)
    _install_fakes(monkeypatch, doc, clause, {"item-0": 30.0}, {"item-0": NOT_IMPACTED})
    summary = pipeline.run_analysis(session, provider=_Provider())
    assert (summary.judged, summary.no_impact, summary.tasks_created) == (1, 1, 0)


def test_budget_judges_best_items_first(session, monkeypatch):
    doc, clause, _items = _seed(session, n_items=3)
    judged = _install_fakes(
        monkeypatch, doc, clause, {"item-0": 12.0, "item-1": 40.0, "item-2": 25.0}, {}
    )
    summary = pipeline.run_analysis(session, provider=_Provider(), limit=2)
    assert judged == ["item-1", "item-2"]
    assert (summary.judged, summary.over_budget, summary.gated_out) == (2, 1, 0)


def test_budget_default_from_settings(session, monkeypatch):
    doc, clause, _items = _seed(session, n_items=3)
    monkeypatch.setattr(settings, "analysis_max_items", 1)
    judged = _install_fakes(monkeypatch, doc, clause, {f"item-{i}": 20.0 for i in range(3)}, {})
    pipeline.run_analysis(session, provider=_Provider())
    assert len(judged) == 1


def test_empty_corpus_skips_everything(session, monkeypatch):
    _seed(session, n_items=2)
    session.exec(select(Clause)).one()

    class _EmptyIndex(_FakeIndex):
        def __len__(self) -> int:
            return 0

    monkeypatch.setattr(pipeline, "ClauseIndex", _EmptyIndex)
    summary = pipeline.run_analysis(session, provider=_Provider())
    assert summary.considered == 0 and summary.judged == 0


def test_legislation_override_rewrites_item_and_keeps_frontmatter(session, monkeypatch):
    doc, clause, items = _seed(session, n_items=1)
    item = items[0]
    persist_items(session, [item], {item.sprs_id: ["notice-period"]})
    session.commit()
    path = settings.vault_dir.parent / item.vault_path
    assert frontmatter.load(path)["legislation_type"] == "amendment"

    verdict = [
        ImpactAssessment("lease#7-2", False, "low", "no", legislation_type="new_legislation")
    ]
    _install_fakes(monkeypatch, doc, clause, {"item-0": 30.0}, {"item-0": verdict})
    pipeline.run_analysis(session, provider=_Provider())
    session.commit()

    session.refresh(item)
    assert item.legislation_type == "new_legislation"
    post = frontmatter.load(path)
    assert post["legislation_type"] == "new_legislation"
    assert post["concepts"] == ["notice-period"]


def test_no_override_when_judge_agrees_or_abstains(session, monkeypatch):
    doc, clause, items = _seed(session, n_items=1)
    item = items[0]
    persist_items(session, [item], {})
    session.commit()
    path = settings.vault_dir.parent / item.vault_path
    before = path.read_text(encoding="utf-8")
    verdict = [ImpactAssessment("lease#7-2", False, "low", "no", legislation_type=None)]
    _install_fakes(monkeypatch, doc, clause, {"item-0": 30.0}, {"item-0": verdict})
    pipeline.run_analysis(session, provider=_Provider())
    assert path.read_text(encoding="utf-8") == before
