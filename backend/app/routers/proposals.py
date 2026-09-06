"""proposals API routes - approve/reject the judge's suggested redlines.

Approve is the write path that matters for the demo: it rewrites the vault
markdown via the existing writer (never hand-rolled), bumps the document
version, records an Edit, and fans out a Notification to every user linked to
the document. Reject only flips the proposal's status.

Both paths also call `_refresh_task_state()`, which rolls the proposal-level
decision up to `TaskDocument.review_state` and `Task.status`. Without it a
proposal could be approved forever while `/tasks` kept showing the task as
"new" - the roll-up is what makes the task list reflect real progress.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.analysis.proposal import render_diff
from app.db import get_session
from app.models import (
    Clause,
    ClauseConcept,
    Concept,
    Document,
    DocumentUser,
    Edit,
    Notification,
    Proposal,
    Task,
    TaskDocument,
)
from app.vault.writer import write_document

router = APIRouter(prefix="/api/proposals", tags=["proposals"])

SessionDep = Annotated[Session, Depends(get_session)]


class ApprovalBody(BaseModel):
    user_id: int


def _proposal_payload(session: Session, proposal: Proposal) -> dict:
    clause = session.get(Clause, proposal.clause_id)
    before_text = clause.text if clause else ""
    return {
        "id": proposal.id,
        "clause_ref": proposal.clause_ref,
        "status": proposal.status,
        "severity": proposal.severity,
        "rationale": proposal.rationale,
        "suggested_text": proposal.suggested_text,
        "clause": (
            {
                "anchor": clause.anchor,
                "number": clause.number,
                "heading": clause.heading,
                "text": clause.text,
            }
            if clause
            else None
        ),
        "diff": render_diff(before_text, proposal.suggested_text),
    }


def _document_clause_concepts(
    session: Session, document_id: int
) -> dict[str, list[tuple[str, str]]]:
    """`<clause.ref>` -> [(concept slug, concept name), ...] for the whole document."""
    clauses = session.exec(select(Clause).where(Clause.document_id == document_id)).all()
    concepts_by_ref: dict[str, list[tuple[str, str]]] = {c.ref: [] for c in clauses}
    ref_by_id = {c.id: c.ref for c in clauses}
    if clauses:
        links = session.exec(
            select(ClauseConcept, Concept)
            .where(ClauseConcept.concept_id == Concept.id)
            .where(ClauseConcept.clause_id.in_(list(ref_by_id)))  # type: ignore[attr-defined]
        ).all()
        for link, concept in links:
            concepts_by_ref[ref_by_id[link.clause_id]].append((concept.slug, concept.name))
    return concepts_by_ref


def _refresh_task_state(session: Session, task_document_id: int | None) -> None:
    """Roll proposal decisions up to `TaskDocument.review_state` and `Task.status`.

    Call after a proposal's status is set and before commit. A task document is
    "reviewed" once none of its proposals are still pending. A task is "new"
    while every proposal across all its task documents is pending, "in_progress"
    once some but not all are decided, and - once all are decided - "approved"
    if at least one was approved, else "dismissed".
    """
    if task_document_id is None:
        return
    task_document = session.get(TaskDocument, task_document_id)
    if task_document is None:
        return

    doc_proposals = session.exec(
        select(Proposal).where(Proposal.task_document_id == task_document_id)
    ).all()
    task_document.review_state = (
        "pending" if any(p.status == "pending" for p in doc_proposals) else "reviewed"
    )
    session.add(task_document)

    task = session.get(Task, task_document.task_id)
    if task is None:
        return
    sibling_ids = session.exec(
        select(TaskDocument.id).where(TaskDocument.task_id == task.id)
    ).all()
    all_proposals = session.exec(
        select(Proposal).where(Proposal.task_document_id.in_(sibling_ids))  # type: ignore[attr-defined]
    ).all()
    if not all_proposals:
        return
    if all(p.status == "pending" for p in all_proposals):
        task.status = "new"
    elif any(p.status == "pending" for p in all_proposals):
        task.status = "in_progress"
    elif any(p.status == "approved" for p in all_proposals):
        task.status = "approved"
    else:
        task.status = "dismissed"
    session.add(task)


@router.post("/{proposal_id}/approve")
def approve_proposal(proposal_id: int, body: ApprovalBody, session: SessionDep) -> dict:
    """Rewrite the vault clause, bump the version, record an Edit, notify."""
    proposal = session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"no proposal with id {proposal_id}")

    clause = session.get(Clause, proposal.clause_id)
    if clause is None:
        raise HTTPException(status_code=404, detail=f"no clause with id {proposal.clause_id}")
    document = session.get(Document, clause.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"no document with id {clause.document_id}")

    before_text = clause.text
    after_text = proposal.suggested_text

    all_clauses = session.exec(
        select(Clause).where(Clause.document_id == document.id).order_by(Clause.order_index)
    ).all()
    clause_concepts = _document_clause_concepts(session, document.id)
    for c in all_clauses:
        if c.id == clause.id:
            c.text = after_text
    # Bump before writing: the vault markdown carries the version in its
    # frontmatter, and the vault is the source of truth for document content.
    # Writing first left the file on v1 while the database said v2.
    document.version += 1
    write_document(document, all_clauses, clause_concepts)

    clause.text = after_text
    document.updated_at = datetime.now(UTC)
    session.add(clause)
    session.add(document)

    edit = Edit(
        proposal_id=proposal.id,
        document_id=document.id,
        clause_ref=proposal.clause_ref,
        before_text=before_text,
        after_text=after_text,
        user_id=body.user_id,
        version_after=document.version,
    )
    session.add(edit)
    session.flush()

    proposal.status = "approved"
    session.add(proposal)
    _refresh_task_state(session, proposal.task_document_id)

    task_document = session.get(TaskDocument, proposal.task_document_id)
    task = session.get(Task, task_document.task_id) if task_document else None

    linked_user_ids = session.exec(
        select(DocumentUser.user_id).where(DocumentUser.document_id == document.id)
    ).all()
    message = f"{proposal.clause_ref} was updated"
    if task is not None:
        message += f" for {task.reference}"
    for user_id in linked_user_ids:
        session.add(
            Notification(
                user_id=user_id,
                task_id=task.id if task else None,
                document_id=document.id,
                edit_id=edit.id,
                message=message,
            )
        )

    session.commit()
    session.refresh(proposal)
    return _proposal_payload(session, proposal)


@router.post("/{proposal_id}/reject")
def reject_proposal(proposal_id: int, body: ApprovalBody, session: SessionDep) -> dict:
    """Set the proposal's status to rejected and refresh the task roll-up."""
    proposal = session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"no proposal with id {proposal_id}")

    proposal.status = "rejected"
    session.add(proposal)
    _refresh_task_state(session, proposal.task_document_id)
    session.commit()
    session.refresh(proposal)
    return _proposal_payload(session, proposal)
