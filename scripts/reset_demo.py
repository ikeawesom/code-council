"""Rewind every approval so the dashboard is stage-ready again.

    python scripts/reset_demo.py [--task CC-2026-0002] [--dry-run] [--yes]

Rehearsing or QA-ing the demo means clicking "Approve and update document",
which is a one-way door: the clause text is rewritten in the vault, the
document version is bumped, an Edit is recorded and notifications fan out. Run
this the morning of the demo and every task goes back to `new` with pending
proposals and intact redlines - the money shot survives.

The original clause text is not guessed: it is read back from the *earliest*
Edit row for each clause, which stored `before_text` at the moment it was
applied. Nothing here re-runs the judge, so the proposals keep the real
`claude_cli` insert/delete redlines. Idempotent - a second run finds no edits
and does nothing. `--task` rewinds one task only, so the other task can keep a
real edit trail on its document pages.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.db import session_scope  # noqa: E402
from app.models import (  # noqa: E402
    Clause,
    Document,
    Edit,
    Notification,
    Proposal,
    Task,
    TaskDocument,
)
from app.routers.proposals import _document_clause_concepts  # noqa: E402
from app.vault.writer import write_document  # noqa: E402
from sqlmodel import Session, select  # noqa: E402


def _originals(edits: list[Edit]) -> tuple[dict[str, str], dict[int, int]]:
    """`clause_ref -> pristine text` and `document_id -> pristine version`.

    Edits are replayed oldest-first, so the first one seen for a clause holds
    the text as it was before anybody touched it. A document's pristine version
    is one below the lowest `version_after` it ever recorded.
    """
    text_by_ref: dict[str, str] = {}
    version_by_doc: dict[int, int] = {}
    for edit in sorted(edits, key=lambda e: e.created_at):
        text_by_ref.setdefault(edit.clause_ref, edit.before_text)
        lowest = version_by_doc.get(edit.document_id)
        candidate = max(edit.version_after - 1, 1)
        version_by_doc[edit.document_id] = min(lowest, candidate) if lowest else candidate
    return text_by_ref, version_by_doc


def _edits_for_task(session: Session, reference: str) -> list[Edit]:
    """Every Edit whose proposal hangs off the task with this reference."""
    task = session.exec(select(Task).where(Task.reference == reference)).first()
    if task is None:
        raise SystemExit(f"no task with reference {reference!r}")
    task_documents = session.exec(
        select(TaskDocument).where(TaskDocument.task_id == task.id)
    ).all()
    task_document_ids = [td.id for td in task_documents]
    proposal_ids = [
        p.id
        for p in session.exec(
            select(Proposal).where(Proposal.task_document_id.in_(task_document_ids))  # type: ignore[attr-defined]
        ).all()
    ]
    if not proposal_ids:
        return []
    return list(
        session.exec(select(Edit).where(Edit.proposal_id.in_(proposal_ids))).all()  # type: ignore[attr-defined]
    )


def reset_demo(
    session: Session, *, dry_run: bool = False, task_reference: str | None = None
) -> dict:
    """Revert clauses, versions, proposals and workflow state. Returns a summary."""
    edits = (
        _edits_for_task(session, task_reference)
        if task_reference
        else list(session.exec(select(Edit)).all())
    )
    text_by_ref, version_by_doc = _originals(edits)

    clauses_reverted = 0
    for ref, original in text_by_ref.items():
        clause = session.exec(select(Clause).where(Clause.ref == ref)).first()
        if clause is None or clause.text == original:
            continue
        clauses_reverted += 1
        if not dry_run:
            clause.text = original
            session.add(clause)

    documents: list[tuple[str, int, int]] = []
    for document_id, original_version in version_by_doc.items():
        document = session.get(Document, document_id)
        if document is None:
            continue
        documents.append((document.slug, document.version, original_version))
        if dry_run:
            continue
        document.version = original_version
        session.add(document)
        # Rewrite the markdown through the real writer - the vault is the source
        # of truth for document content, so a stale file would outlive the reset.
        doc_clauses = session.exec(
            select(Clause).where(Clause.document_id == document_id).order_by(Clause.order_index)
        ).all()
        write_document(document, list(doc_clauses), _document_clause_concepts(session, document_id))

    edited_proposal_ids = [e.proposal_id for e in edits if e.proposal_id is not None]
    proposal_query = select(Proposal).where(Proposal.status != "pending")
    if task_reference:
        proposal_query = proposal_query.where(Proposal.id.in_(edited_proposal_ids or [-1]))  # type: ignore[attr-defined]
    proposals = session.exec(proposal_query).all()
    touched_task_document_ids = {p.task_document_id for p in proposals}
    task_documents = [
        td
        for td in session.exec(
            select(TaskDocument).where(TaskDocument.review_state != "pending")
        ).all()
        if not task_reference or td.id in touched_task_document_ids
    ]
    touched_task_ids = {td.task_id for td in task_documents}
    tasks = [
        t
        for t in session.exec(select(Task).where(Task.status != "new")).all()
        if not task_reference or t.id in touched_task_ids
    ]
    edit_ids = [e.id for e in edits]
    notifications = (
        session.exec(select(Notification).where(Notification.edit_id.in_(edit_ids))).all()  # type: ignore[attr-defined]
        if edit_ids
        else []
    )

    if not dry_run:
        for proposal in proposals:
            proposal.status = "pending"
            session.add(proposal)
        for task_document in task_documents:
            task_document.review_state = "pending"
            session.add(task_document)
        for task in tasks:
            task.status = "new"
            session.add(task)
        for notification in notifications:
            session.delete(notification)
        for edit in edits:
            session.delete(edit)

    return {
        "clauses_reverted": clauses_reverted,
        "documents": documents,
        "proposals": len(proposals),
        "task_documents": len(task_documents),
        "tasks": [t.reference for t in tasks],
        "notifications": len(notifications),
        "edits": len(edits),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset the Code Council demo to pristine state.")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change, write nothing"
    )
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument(
        "--task", metavar="REFERENCE", help="rewind only this task, e.g. CC-2026-0002"
    )
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("This deletes every recorded edit and notification and reverts the vault.")
        if input("Reset the demo? [y/N] ").strip().lower() not in {"y", "yes"}:
            print("Aborted - nothing changed.")
            return 1

    with session_scope() as session:
        summary = reset_demo(session, dry_run=args.dry_run, task_reference=args.task)

    label = "Would revert" if args.dry_run else "Reverted"
    print(f"{label} {summary['clauses_reverted']} clause(s) to their pre-approval text.")
    for slug, was, now in summary["documents"]:
        print(f"  {slug}: v{was} -> v{now}")
    print(f"{label} {summary['proposals']} proposal(s) to pending.")
    print(f"{label} {summary['task_documents']} task document(s) to pending.")
    references = ", ".join(summary["tasks"]) or "(none)"
    print(f"{label} {len(summary['tasks'])} task(s) to new: {references}")
    print(
        f"{label} {summary['notifications']} notification(s) "
        f"and {summary['edits']} edit(s) removed."
    )
    if not summary["edits"]:
        print("Nothing to do - the demo is already pristine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
