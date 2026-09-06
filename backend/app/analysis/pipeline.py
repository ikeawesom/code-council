"""The M3 stage: fresh parliament items -> tasks with clause proposals.

Runs after the scrape, from the 07:00 job and from scripts/run_daily.py. The
work queue is every ParliamentItem with no Task. Each run:

1. builds the clause index once,
2. ranks every queued item by its best candidate clause (cheap, no LLM),
3. keeps items that clear the gate, best first, up to a per-run judge budget,
4. judges each survivor in one LLM call and writes Task -> TaskDocument ->
   Proposal for whatever came back impacted.

An item the judge could not assess (LLMError) is left untasked and is
retried next run; the content-addressed cache makes re-judging free. An item
that was gated out or judged not impacted is also left untasked - ranking it
again tomorrow costs nothing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import frontmatter
from sqlalchemy import func
from sqlmodel import Session, select

from app.analysis.impact import assess
from app.analysis.proposal import create_proposals
from app.analysis.retrieve import Candidate, ClauseIndex, passes_gate
from app.config import settings
from app.llm.base import LLMProvider, get_provider
from app.models import LEGISLATION_TYPES, ParliamentItem, Task
from app.scraper.normalize import persist_items

logger = logging.getLogger(__name__)


@dataclass
class AnalysisSummary:
    """What one run_analysis() call did, for logging and the CLI summary."""

    already_tasked: int = 0  # items skipped: a Task already exists for them
    considered: int = 0  # untasked items examined
    gated_out: int = 0  # failed passes_gate
    over_budget: int = 0  # passed the gate but the per-run judge budget was spent
    judged: int = 0  # sent to assess()
    judge_failures: int = 0  # assess returned [] - item left untasked for retry
    no_impact: int = 0  # judged, nothing impacted
    tasks_created: int = 0
    proposals_created: int = 0
    task_references: list[str] = field(default_factory=list)
    provider: str = ""


def untasked_items(session: Session) -> list[ParliamentItem]:
    """Parliament items with no Task row, newest sitting first."""
    tasked = select(Task.parliament_item_id)
    return list(
        session.exec(
            select(ParliamentItem)
            .where(ParliamentItem.id.not_in(tasked))  # type: ignore[union-attr]
            .order_by(ParliamentItem.sitting_date.desc(), ParliamentItem.id)  # type: ignore[union-attr]
        ).all()
    )


def run_analysis(
    session: Session,
    *,
    provider: LLMProvider | None = None,
    limit: int | None = None,
) -> AnalysisSummary:
    """Retrieve -> gate -> judge -> propose over the untasked items. Caller commits."""
    active_provider = provider or get_provider()
    budget = settings.analysis_max_items if limit is None else limit
    summary = AnalysisSummary(provider=getattr(active_provider, "name", "?"))

    index = ClauseIndex.build(session)
    if len(index) == 0:
        logger.warning("analysis skipped: no clauses ingested yet")
        return summary

    queue = untasked_items(session)
    summary.considered = len(queue)
    total_items = session.exec(select(func.count()).select_from(ParliamentItem)).one()
    summary.already_tasked = total_items - len(queue)
    ranked: list[tuple[ParliamentItem, list[Candidate]]] = []
    for item in queue:
        candidates = index.candidates(item)
        if passes_gate(candidates):
            ranked.append((item, candidates))
        else:
            summary.gated_out += 1
    ranked.sort(key=lambda pair: -pair[1][0].score)

    for item, candidates in ranked:
        if summary.judged >= budget:
            summary.over_budget += 1
            continue
        summary.judged += 1
        assessments = assess(item, candidates, active_provider)
        if not assessments:
            summary.judge_failures += 1
            continue

        _apply_legislation_override(session, item, assessments)

        task = create_proposals(session, item, assessments, candidates)
        if task is None:
            summary.no_impact += 1
            session.flush()
            continue
        proposal_count = sum(1 for a in assessments if a.impacted and a.clause_ref in
                             {c.clause.ref for c in candidates})
        summary.tasks_created += 1
        summary.proposals_created += proposal_count
        summary.task_references.append(task.reference)
        session.flush()
        logger.info(
            "task %s: %r severity=%s documents=%d proposals=%d",
            task.reference,
            item.title,
            task.severity,
            task.document_count,
            proposal_count,
        )

    logger.info(
        "analysis done: %d already tasked, %d considered, %d gated out, %d over budget, "
        "%d judged (%d failed, %d no impact), %d tasks, %d proposals (provider=%s)",
        summary.already_tasked,
        summary.considered,
        summary.gated_out,
        summary.over_budget,
        summary.judged,
        summary.judge_failures,
        summary.no_impact,
        summary.tasks_created,
        summary.proposals_created,
        summary.provider,
    )
    return summary


def _apply_legislation_override(session: Session, item: ParliamentItem, assessments) -> None:
    """Let the judge overwrite the scraper's legislation_type heuristic.

    Goes through `persist_items()` like every other writer of parliament items,
    so the vault file is rewritten too; the item's existing frontmatter
    concepts are read back first so the planted item keeps its tags.
    """
    override = next(
        (a.legislation_type for a in assessments if a.legislation_type in LEGISLATION_TYPES),
        None,
    )
    if override is None or override == item.legislation_type:
        return
    logger.info(
        "legislation_type for %s: %s -> %s (judge)", item.sprs_id, item.legislation_type, override
    )
    item.legislation_type = override
    persist_items(session, [item], {item.sprs_id: _existing_concepts(item)})


def _existing_concepts(item: ParliamentItem) -> list[str]:
    if not item.vault_path:
        return []
    path = settings.vault_dir.parent / item.vault_path
    if not path.exists():
        return []
    try:
        concepts = frontmatter.load(path).get("concepts") or []
    except (OSError, ValueError):
        return []
    return [c for c in concepts if isinstance(c, str)]
