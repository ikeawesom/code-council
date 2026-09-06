"""documents API routes.

Started as the M1 read-only slice; extended for M4 to the sector-grouped list,
per-document detail (clauses + edit history) that `docs/API_CONTRACT.md`
defines. Content still comes from the database cache of vault text - the vault
markdown itself is rewritten only by `routers/proposals.py::approve_proposal`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Clause, ClauseConcept, Concept, Document, Edit, Task, TaskDocument, User

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Annotated form rather than a `Depends(...)` default - the default-argument
# style is a function call in a default, which ruff's B008 rejects.
SessionDep = Annotated[Session, Depends(get_session)]

_OPEN_TASK_STATUSES = {"new", "in_progress"}


def _open_task_counts(session: Session) -> dict[int, int]:
    """document_id -> count of tasks (via task_documents) not approved/dismissed."""
    counts: dict[int, int] = {}
    rows = session.exec(
        select(TaskDocument, Task).where(TaskDocument.task_id == Task.id)
    ).all()
    for task_document, task in rows:
        if task.status in _OPEN_TASK_STATUSES:
            counts[task_document.document_id] = counts.get(task_document.document_id, 0) + 1
    return counts


def _document_payload(doc: Document, open_task_count: int) -> dict:
    return {
        "id": doc.id,
        "slug": doc.slug,
        "title": doc.title,
        "sector": doc.sector,
        "file_type": doc.file_type,
        "version": doc.version,
        "clause_count": doc.clause_count,
        "updated_at": doc.updated_at.isoformat(),
        "parse_error": doc.parse_error,
        "open_task_count": open_task_count,
    }


@router.get("")
def list_documents(session: SessionDep, sector: str | None = None) -> dict:
    """Every ingested document, grouped by sector."""
    query = select(Document)
    if sector:
        query = query.where(Document.sector == sector)
    documents = session.exec(query.order_by(Document.sector, Document.slug)).all()
    open_counts = _open_task_counts(session)

    sectors: dict[str, list[dict]] = {}
    for doc in documents:
        sectors.setdefault(doc.sector, []).append(
            _document_payload(doc, open_counts.get(doc.id, 0))
        )

    return {
        "sectors": [
            {"sector": sector_name, "count": len(docs), "documents": docs}
            for sector_name, docs in sorted(sectors.items())
        ]
    }


@router.get("/{slug}")
def get_document(slug: str, session: SessionDep) -> dict:
    """One document: its clauses (with concepts) and its edit history."""
    doc = session.exec(select(Document).where(Document.slug == slug)).first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no document with slug {slug!r}")

    clauses = session.exec(
        select(Clause).where(Clause.document_id == doc.id).order_by(Clause.order_index)
    ).all()

    concepts_by_clause: dict[int, list[str]] = {c.id: [] for c in clauses}
    if clauses:
        links = session.exec(
            select(ClauseConcept, Concept)
            .where(ClauseConcept.concept_id == Concept.id)
            .where(ClauseConcept.clause_id.in_(list(concepts_by_clause)))  # type: ignore[attr-defined]
        ).all()
        for link, concept in links:
            concepts_by_clause[link.clause_id].append(concept.slug)

    edits = session.exec(
        select(Edit).where(Edit.document_id == doc.id).order_by(Edit.created_at)
    ).all()
    history = []
    for edit in edits:
        user = session.get(User, edit.user_id) if edit.user_id is not None else None
        history.append(
            {
                "clause_ref": edit.clause_ref,
                "before_text": edit.before_text,
                "after_text": edit.after_text,
                "user": (
                    {"id": user.id, "name": user.name, "initials": user.initials}
                    if user
                    else None
                ),
                "created_at": edit.created_at.isoformat(),
                "version_after": edit.version_after,
            }
        )

    open_counts = _open_task_counts(session)
    payload = _document_payload(doc, open_counts.get(doc.id, 0))
    payload["clauses"] = [
        {
            "anchor": c.anchor,
            "number": c.number,
            "heading": c.heading,
            "text": c.text,
            "concepts": sorted(concepts_by_clause[c.id]),
        }
        for c in clauses
    ]
    payload["history"] = history
    return payload
