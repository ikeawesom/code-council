"""Tests for analysis/proposal.py - task references, the word-level redline and
the Task -> TaskDocument -> Proposal writer."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.analysis.impact import ImpactAssessment
from app.analysis.proposal import create_proposals, next_task_reference, render_diff
from app.analysis.retrieve import Candidate
from app.models import Clause, Document, ParliamentItem, Proposal, Task, TaskDocument


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed(session: Session):
    lease = Document(slug="lease", title="Lease", sector="real-estate")
    nda = Document(slug="nda", title="NDA", sector="general")
    session.add_all([lease, nda])
    session.flush()
    clauses = [
        Clause(document_id=lease.id, anchor="7-2", ref="lease#7-2", text="one month notice"),
        Clause(document_id=lease.id, anchor="3", ref="lease#3", text="rent monthly"),
        Clause(document_id=nda.id, anchor="1", ref="nda#1", text="keep it secret"),
    ]
    session.add_all(clauses)
    item = ParliamentItem(sprs_id="demo-x", slug="x", title="Bill", sitting_date="2026-08-05")
    session.add(item)
    session.flush()
    docs = {lease.id: lease, nda.id: nda}
    cands = [
        Candidate(clause=c, document=docs[c.document_id], score=1.0, bm25=1.0, concept_overlap=0)
        for c in clauses
    ]
    return item, cands


# --- next_task_reference -------------------------------------------------------


def test_next_task_reference_format_and_sequence(session):
    assert next_task_reference(session, year=2026) == "CC-2026-0001"
    session.add(Task(parliament_item_id=1, reference="CC-2026-0001"))
    session.add(Task(parliament_item_id=1, reference="CC-2025-0009"))
    session.flush()
    assert next_task_reference(session, year=2026) == "CC-2026-0002"


def test_next_task_reference_skips_collisions(session):
    session.add(Task(parliament_item_id=1, reference="CC-2026-0002"))
    session.flush()
    # one existing task -> sequence 2, which is taken -> 3
    assert next_task_reference(session, year=2026) == "CC-2026-0003"


# --- render_diff --------------------------------------------------------------


def test_render_diff_identical():
    assert render_diff("same text", "same text") == [("equal", "same text")]
    assert render_diff("", "") == []


def test_render_diff_insertion_and_replacement_round_trip():
    before = "give one (1) month's written notice"
    after = "give three (3) months' written notice to the other"
    ops = render_diff(before, after)
    kinds = [k for k, _ in ops]
    assert "delete" in kinds and "insert" in kinds and "equal" in kinds
    assert "".join(t for k, t in ops if k in ("equal", "insert")) == after
    assert "".join(t for k, t in ops if k in ("equal", "delete")) == before
    # adjacent runs are merged: no two consecutive ops share a kind
    assert all(a != b for a, b in zip(kinds, kinds[1:], strict=False))


# --- create_proposals ---------------------------------------------------------------


def test_create_proposals_builds_three_levels_with_rollups(session):
    item, cands = _seed(session)
    assessments = [
        ImpactAssessment("lease#7-2", True, "medium", "r1", "new text"),
        ImpactAssessment("lease#3", True, "high", "r2", "new rent"),
        ImpactAssessment("nda#1", True, "low", "r3", ""),
    ]
    task = create_proposals(session, item, assessments, cands)
    assert task is not None
    assert task.reference.startswith("CC-")
    assert task.status == "new"
    assert task.severity == "high"
    assert task.document_count == 2
    assert task.parliament_item_id == item.id

    task_docs = session.exec(select(TaskDocument).where(TaskDocument.task_id == task.id)).all()
    by_doc = {td.document_id: td for td in task_docs}
    lease_td = by_doc[cands[0].document.id]
    nda_td = by_doc[cands[2].document.id]
    assert lease_td.severity == "high" and lease_td.proposal_count == 2
    assert nda_td.severity == "low" and nda_td.proposal_count == 1
    assert all(td.review_state == "pending" for td in task_docs)

    proposals = session.exec(select(Proposal)).all()
    assert len(proposals) == 3
    p = next(p for p in proposals if p.clause_ref == "lease#7-2")
    assert p.task_document_id == lease_td.id
    assert p.clause_id == cands[0].clause.id
    assert (p.impacted, p.severity, p.rationale, p.suggested_text, p.status) == (
        True, "medium", "r1", "new text", "pending",
    )


def test_create_proposals_none_when_nothing_impacted(session):
    item, cands = _seed(session)
    assessments = [ImpactAssessment("lease#7-2", False, "low", "no")]
    assert create_proposals(session, item, assessments, cands) is None
    assert session.exec(select(Task)).all() == []
    assert session.exec(select(Proposal)).all() == []


def test_create_proposals_ignores_unknown_clause_refs(session):
    item, cands = _seed(session)
    assessments = [ImpactAssessment("ghost#1", True, "high", "r", "t")]
    assert create_proposals(session, item, assessments, cands) is None
    assert session.exec(select(Task)).all() == []
