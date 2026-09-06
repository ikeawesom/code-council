"""Turn judge assessments into workflow rows, and render the redline the UI shows.

The three-level shape is fixed by models.py: one Task per parliament item,
one TaskDocument per affected document, one Proposal per impacted clause.
Severity is stored once per proposal and rolled up as the maximum - the judge
is never asked for three severities.
"""
from __future__ import annotations

import difflib
import re
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.analysis.impact import ImpactAssessment
from app.analysis.retrieve import Candidate
from app.models import ParliamentItem, Proposal, Task, TaskDocument, max_severity

_WORD_SPLIT_RE = re.compile(r"(\s+)")


def next_task_reference(session: Session, year: int | None = None) -> str:
    """`CC-<year>-<NNNN>`: the next unused sequence number for the year."""
    if year is None:
        year = datetime.now(UTC).year
    prefix = f"CC-{year}-"
    existing = set(
        session.exec(select(Task.reference).where(Task.reference.startswith(prefix))).all()
    )
    n = len(existing) + 1
    while f"{prefix}{n:04d}" in existing:
        n += 1
    return f"{prefix}{n:04d}"


def render_diff(before: str, after: str) -> list[tuple[str, str]]:
    """Word-level redline ops: `("equal" | "insert" | "delete", text)`.

    Tokens keep their whitespace, so joining the equal+insert texts reproduces
    `after` and equal+delete reproduces `before`. Adjacent runs of the same op
    are merged. Identical inputs give a single equal op.
    """
    if before == after:
        return [("equal", before)] if before else []
    a = [tok for tok in _WORD_SPLIT_RE.split(before) if tok]
    b = [tok for tok in _WORD_SPLIT_RE.split(after) if tok]
    ops: list[tuple[str, str]] = []

    def push(kind: str, text: str) -> None:
        if not text:
            return
        if ops and ops[-1][0] == kind:
            ops[-1] = (kind, ops[-1][1] + text)
        else:
            ops.append((kind, text))

    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            push("equal", "".join(a[i1:i2]))
        elif tag == "delete":
            push("delete", "".join(a[i1:i2]))
        elif tag == "insert":
            push("insert", "".join(b[j1:j2]))
        else:  # replace
            push("delete", "".join(a[i1:i2]))
            push("insert", "".join(b[j1:j2]))
    return ops


def create_proposals(
    session: Session,
    item: ParliamentItem,
    assessments: list[ImpactAssessment],
    candidates: list[Candidate],
) -> Task | None:
    """Write Task -> TaskDocument -> Proposal rows for the impacted assessments.

    Returns None and writes nothing when no assessment is impacted or none
    matches a candidate clause. Flushes; the caller commits.
    """
    by_ref = {cand.clause.ref: cand for cand in candidates}
    impacted = [
        (a, by_ref[a.clause_ref]) for a in assessments if a.impacted and a.clause_ref in by_ref
    ]
    if not impacted:
        return None

    task = Task(
        parliament_item_id=item.id,
        reference=next_task_reference(session),
        status="new",
        severity=max_severity([a.severity for a, _ in impacted]),
    )
    session.add(task)
    session.flush()

    by_document: dict[int, list[tuple[ImpactAssessment, Candidate]]] = {}
    for pair in impacted:
        by_document.setdefault(pair[1].clause.document_id, []).append(pair)

    for document_id, pairs in by_document.items():
        task_document = TaskDocument(
            task_id=task.id,
            document_id=document_id,
            review_state="pending",
            severity=max_severity([a.severity for a, _ in pairs]),
            proposal_count=len(pairs),
        )
        session.add(task_document)
        session.flush()
        for assessment, cand in pairs:
            session.add(
                Proposal(
                    task_document_id=task_document.id,
                    clause_id=cand.clause.id,
                    clause_ref=cand.clause.ref,
                    impacted=True,
                    severity=assessment.severity,
                    rationale=assessment.rationale,
                    suggested_text=assessment.suggested_text,
                    status="pending",
                )
            )

    task.document_count = len(by_document)
    session.flush()
    return task
