"""documents API routes - read-only M1 slice.

Enough to inspect what `scripts/ingest.py` produced without opening SQLite by
hand. The full documents/tasks/proposals surface the dashboard needs is M4;
these two endpoints are deliberately minimal and will be extended, not replaced.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Clause, ClauseConcept, Concept, Document

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Annotated form rather than a `Depends(...)` default - the default-argument
# style is a function call in a default, which ruff's B008 rejects.
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("")
def list_documents(session: SessionDep) -> list[dict]:
    """Every ingested document, newest schema fields included."""
    documents = session.exec(select(Document).order_by(Document.sector, Document.slug)).all()
    return [
        {
            "slug": doc.slug,
            "title": doc.title,
            "sector": doc.sector,
            "file_type": doc.file_type,
            "version": doc.version,
            "clause_count": doc.clause_count,
            "parse_error": doc.parse_error,
        }
        for doc in documents
    ]


@router.get("/{slug}")
def get_document(slug: str, session: SessionDep) -> dict:
    """One document with its clauses and each clause's concepts."""
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

    return {
        "slug": doc.slug,
        "title": doc.title,
        "sector": doc.sector,
        "version": doc.version,
        "parse_error": doc.parse_error,
        "clauses": [
            {
                "ref": c.ref,
                "anchor": c.anchor,
                "number": c.number,
                "heading": c.heading,
                "text": c.text,
                "concepts": sorted(concepts_by_clause[c.id]),
            }
            for c in clauses
        ],
    }
