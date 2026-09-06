"""tasks API routes - the three-level workflow surface the dashboard reads.

One Task per parliament item; GET here is the read side of
`analysis/proposal.py::create_proposals`. Shapes are frozen in
`docs/API_CONTRACT.md`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Clause, Document, ParliamentItem, Proposal, Task, TaskDocument, User

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

SessionDep = Annotated[Session, Depends(get_session)]


def _assignee_payload(session: Session, user_id: int | None) -> dict | None:
    if user_id is None:
        return None
    user = session.get(User, user_id)
    if user is None:
        return None
    return {"id": user.id, "name": user.name, "initials": user.initials, "role": user.role}


def _item_payload(item: ParliamentItem | None) -> dict | None:
    if item is None:
        return None
    return {
        "id": item.id,
        "title": item.title,
        "sitting_date": item.sitting_date,
        "item_type": item.item_type,
        "legislation_type": item.legislation_type,
        "speaker": item.speaker,
        "url": item.url,
        "summary": item.summary,
    }


def _proposal_count_for_task(session: Session, task_id: int) -> int:
    task_docs = session.exec(select(TaskDocument).where(TaskDocument.task_id == task_id)).all()
    return sum(td.proposal_count for td in task_docs)


def _sectors_for_task(session: Session, task_id: int) -> list[str]:
    """Sorted, de-duplicated sectors of every document this task touches."""
    task_docs = session.exec(select(TaskDocument).where(TaskDocument.task_id == task_id)).all()
    sectors = {
        doc.sector
        for td in task_docs
        if (doc := session.get(Document, td.document_id)) is not None
    }
    return sorted(sectors)


def _task_payload(session: Session, task: Task) -> dict:
    item = session.get(ParliamentItem, task.parliament_item_id)
    return {
        "id": task.id,
        "reference": task.reference,
        "status": task.status,
        "severity": task.severity,
        "document_count": task.document_count,
        "proposal_count": _proposal_count_for_task(session, task.id),
        "created_at": task.created_at.isoformat(),
        "assignee": _assignee_payload(session, task.assignee_id),
        "is_demo": bool(item and item.sprs_id.startswith("demo-")),
        "item": _item_payload(item),
        "sectors": _sectors_for_task(session, task.id),
    }


def _task_document_payload(
    session: Session, task_document: TaskDocument, document: Document
) -> dict:
    proposals = session.exec(
        select(Proposal)
        .where(Proposal.task_document_id == task_document.id)
        .order_by(Proposal.id)
    ).all()
    preview = None
    if proposals:
        top = proposals[0]
        clause = session.get(Clause, top.clause_id)
        preview = {
            "clause_ref": top.clause_ref,
            "heading": clause.heading if clause else "",
            "before": clause.text if clause else "",
            "after": top.suggested_text,
        }
    return {
        "id": task_document.id,
        "document_id": document.id,
        "slug": document.slug,
        "title": document.title,
        "sector": document.sector,
        "severity": task_document.severity,
        "review_state": task_document.review_state,
        "proposal_count": task_document.proposal_count,
        "version": document.version,
        "preview": preview,
    }


@router.get("")
def list_tasks(
    session: SessionDep,
    status: str | None = None,
    severity: str | None = None,
    sector: str | None = None,
) -> dict:
    """Every task, optionally filtered by status, severity and/or sector."""
    query = select(Task)
    if status:
        query = query.where(Task.status == status)
    if severity:
        query = query.where(Task.severity == severity)
    tasks = session.exec(query.order_by(Task.created_at.desc())).all()

    if sector:
        doc_ids = session.exec(select(Document.id).where(Document.sector == sector)).all()
        task_ids_ok = {
            td.task_id
            for td in session.exec(
                select(TaskDocument).where(TaskDocument.document_id.in_(doc_ids))
            ).all()
        }
        tasks = [t for t in tasks if t.id in task_ids_ok]

    return {"tasks": [_task_payload(session, t) for t in tasks]}


@router.get("/{task_id}")
def get_task(task_id: int, session: SessionDep) -> dict:
    """One task plus its affected documents, each with a one-clause preview."""
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"no task with id {task_id}")

    task_docs = session.exec(select(TaskDocument).where(TaskDocument.task_id == task_id)).all()
    documents = []
    for td in task_docs:
        doc = session.get(Document, td.document_id)
        if doc is None:
            continue
        documents.append(_task_document_payload(session, td, doc))

    return {**_task_payload(session, task), "documents": documents}


@router.get("/{task_id}/documents/{doc_slug}")
def get_task_document(task_id: int, doc_slug: str, session: SessionDep) -> dict:
    """One task's proposals for one affected document, with the word-level redline."""
    from app.analysis.proposal import render_diff  # local import: keeps analysis/ optional here

    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"no task with id {task_id}")

    doc = session.exec(select(Document).where(Document.slug == doc_slug)).first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no document with slug {doc_slug!r}")

    task_document = session.exec(
        select(TaskDocument)
        .where(TaskDocument.task_id == task_id)
        .where(TaskDocument.document_id == doc.id)
    ).first()
    if task_document is None:
        raise HTTPException(
            status_code=404, detail=f"document {doc_slug!r} is not part of task {task_id}"
        )

    proposal_rows = session.exec(
        select(Proposal)
        .where(Proposal.task_document_id == task_document.id)
        .order_by(Proposal.id)
    ).all()
    proposals = []
    for p in proposal_rows:
        clause = session.get(Clause, p.clause_id)
        before_text = clause.text if clause else ""
        proposals.append(
            {
                "id": p.id,
                "clause_ref": p.clause_ref,
                "status": p.status,
                "severity": p.severity,
                "rationale": p.rationale,
                "suggested_text": p.suggested_text,
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
                "diff": render_diff(before_text, p.suggested_text),
            }
        )

    return {
        "task": _task_payload(session, task),
        "document": _task_document_payload(session, task_document, doc),
        "proposals": proposals,
    }
