"""Tests for analysis/retrieve.py - the BM25 + concept-overlap cost filter.

Synthetic documents/clauses in an in-memory sqlite; never the real vault.
"""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.analysis import retrieve
from app.analysis.retrieve import ClauseIndex, item_concepts, passes_gate, tokenize
from app.config import settings
from app.models import Clause, ClauseConcept, Concept, Document, ParliamentItem

NOTICE_TEXT = (
    "Either party may terminate this tenancy by giving the other not less than one (1) "
    "month's written notice. The landlord shall not unreasonably withhold consent to "
    "renewal of the tenancy on expiry of the term."
)
RENT_TEXT = (
    "The tenant shall pay the monthly rent in advance on the first day of every month "
    "by bank transfer to the account nominated by the landlord."
)
GOVERNING_TEXT = (
    "This agreement is governed by the laws of Singapore and the parties submit to the "
    "exclusive jurisdiction of the Singapore courts."
)
EXAM_TEXT = (
    "The examiner shall mark the oral examination scripts within fourteen days and "
    "release results to candidates through the portal."
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed(session: Session, *, broken_doc: bool = False) -> dict[str, Clause]:
    lease = Document(slug="lease", title="Lease", sector="real-estate")
    misc = Document(slug="misc", title="Misc", sector="general")
    session.add(lease)
    session.add(misc)
    session.flush()
    clauses = {
        "lease#7-2": Clause(
            document_id=lease.id, anchor="7-2", ref="lease#7-2", heading="Termination",
            text=NOTICE_TEXT, order_index=0,
        ),
        "lease#3": Clause(
            document_id=lease.id, anchor="3", ref="lease#3", heading="Rent", text=RENT_TEXT,
            order_index=1,
        ),
        "misc#1": Clause(
            document_id=misc.id, anchor="1", ref="misc#1", heading="Law", text=GOVERNING_TEXT,
            order_index=0,
        ),
        "misc#2": Clause(
            document_id=misc.id, anchor="2", ref="misc#2", heading="Exam", text=EXAM_TEXT,
            order_index=1,
        ),
    }
    for clause in clauses.values():
        session.add(clause)
    notice = Concept(slug="notice-period", name="Notice Period")
    termination = Concept(slug="termination", name="Termination")
    rent = Concept(slug="rent", name="Rent")  # too short to match lexically
    session.add_all([notice, termination, rent])
    session.flush()
    # Hub concepts must sit on >= 2 clauses to be lexically matchable.
    session.add_all(
        [
            ClauseConcept(clause_id=clauses["lease#7-2"].id, concept_id=notice.id),
            ClauseConcept(clause_id=clauses["misc#1"].id, concept_id=notice.id),
            ClauseConcept(clause_id=clauses["lease#7-2"].id, concept_id=termination.id),
            ClauseConcept(clause_id=clauses["lease#3"].id, concept_id=termination.id),
            ClauseConcept(clause_id=clauses["lease#3"].id, concept_id=rent.id),
            ClauseConcept(clause_id=clauses["misc#2"].id, concept_id=rent.id),
        ]
    )
    if broken_doc:
        broken = Document(slug="broken", title="Broken", sector="general", parse_error="legacy")
        session.add(broken)
        session.flush()
        session.add(
            Clause(document_id=broken.id, anchor="s0", ref="broken#s0", text=NOTICE_TEXT)
        )
    session.commit()
    return clauses


def _item(title: str, body: str, vault_path: str = "") -> ParliamentItem:
    return ParliamentItem(
        sprs_id=f"test-{title[:10]}", slug="x", title=title, sitting_date="2026-08-05",
        body_text=body, vault_path=vault_path,
    )


NOTICE_BILL = _item(
    "Tenancies (Notice Periods) (Amendment) Bill",
    "This Bill lengthens the notice period a landlord must give to terminate a tenancy "
    "from one month to three months, and applies to renewal of any tenancy.",
)


def test_tokenize_drops_stopwords_and_short_tokens():
    tokens = tokenize("The Landlord shall, in accordance with clause 7, give NOTICE to it.")
    assert tokens == ["landlord", "give", "notice"]


def test_index_skips_unreadable_documents_and_empty_clauses(session):
    _seed(session, broken_doc=True)
    session.add(Clause(document_id=1, anchor="e", ref="lease#e", text="   "))
    session.commit()
    index = ClauseIndex.build(session)
    refs = {c.ref for c in index.clauses}
    assert "broken#s0" not in refs
    assert "lease#e" not in refs
    assert len(index) == 4


def test_candidates_rank_notice_clause_first_for_notice_bill(session):
    _seed(session)
    index = ClauseIndex.build(session)
    cands = index.candidates(NOTICE_BILL, k=3)
    assert [c.clause.ref for c in cands][0] == "lease#7-2"
    assert cands[0].document.slug == "lease"
    assert cands[0].score >= cands[1].score >= cands[2].score
    assert len(cands) == 3


def test_candidates_default_k_from_settings(session, monkeypatch):
    _seed(session)
    monkeypatch.setattr(settings, "retrieve_top_k", 2)
    assert len(ClauseIndex.build(session).candidates(NOTICE_BILL)) == 2


def test_item_concepts_lexical_only_for_specific_hub_names(session):
    _seed(session)
    index = ClauseIndex.build(session)
    found = item_concepts(index, NOTICE_BILL)
    assert "notice-period" in found  # two-word name, on two clauses
    assert "rent" not in found  # single short word: never matched lexically


def test_item_concepts_reads_vault_frontmatter(session, tmp_path, monkeypatch):
    _seed(session)
    monkeypatch.setattr(settings, "vault_dir", tmp_path / "vault")
    path = tmp_path / "vault" / "parliament" / "2026-08-05-x.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\ntitle: x\nconcepts:\n  - termination\n---\n# x\n", encoding="utf-8")
    item = _item(
        "Quiet item", "Nothing lexical here.", vault_path="vault/parliament/2026-08-05-x.md"
    )
    assert item_concepts(ClauseIndex.build(session), item) == {"termination"}


def test_concept_overlap_adds_bonus_and_is_reported(session):
    _seed(session)
    index = ClauseIndex.build(session)
    top = index.candidates(NOTICE_BILL, k=1)[0]
    assert top.concept_overlap >= 1
    assert "notice-period" in top.shared_concepts
    assert top.score == pytest.approx(top.bm25 + retrieve.CONCEPT_BONUS * top.concept_overlap)


def test_off_topic_item_scores_low(session):
    _seed(session)
    index = ClauseIndex.build(session)
    bill = index.candidates(NOTICE_BILL, k=1)[0]
    off = index.candidates(_item("Healthcare subsidies", "Subsidies for hospital patients."), k=1)
    assert off[0].score < bill.score / 2


def test_passes_gate_threshold(session, monkeypatch):
    _seed(session)
    cands = ClauseIndex.build(session).candidates(NOTICE_BILL)
    top = cands[0].score
    assert passes_gate(cands, threshold=top - 0.01)
    assert not passes_gate(cands, threshold=top + 0.01)
    monkeypatch.setattr(settings, "retrieve_min_score", top + 1)
    assert not passes_gate(cands)
    assert not passes_gate([])


def test_empty_corpus_returns_no_candidates(session):
    assert ClauseIndex.build(session).candidates(NOTICE_BILL) == []
