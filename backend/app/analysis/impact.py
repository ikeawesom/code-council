"""The LLM judge: one `complete_json` call per surviving parliament item.

Input:  the parliament item (title, type, speaker, body) and its top-K
        candidate clauses with document context.
Output: one `ImpactAssessment` per candidate clause. Only impacted ones become
        proposals. The rationale is what the lawyer reads first, so it must cite
        the specific part of the parliamentary item that bites.

The judge may also override `legislation_type` (amendment / new_legislation);
the scraper's value is a heuristic. A user never can.

Every call goes through `app.llm` (provider + cache). An `LLMError` degrades to
an empty list and a warning - the item stays untasked and is retried next run.

CONTRACT (frozen for M3):
    assess(item, candidates, provider=None) -> list[ImpactAssessment]

    RESPONSE_SCHEMA is the JSON object the provider must return:
    {
      "legislation_type": "amendment" | "new_legislation" | null,
      "assessments": [
        {"clause_ref": "<doc-slug>#<anchor>", "impacted": bool,
         "severity": "high" | "medium" | "low", "rationale": str,
         "suggested_text": str | null,
         "edits": [{"find": str, "replace": str}, ...] | null}
      ]
    }

    `edits` is the long-clause alternative to `suggested_text`: the judge
    applies them to the full clause here, so downstream code only ever sees
    a complete `ImpactAssessment.suggested_text`.

Prompt markers are load-bearing: the first line is `# Impact assessment`, the
item sits under `## Parliamentary item`, and each candidate under
`## Candidate clause <ref>`. `llm/mock.py` dispatches on them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.analysis.retrieve import Candidate
from app.llm.base import LLMError, LLMProvider, get_provider
from app.models import LEGISLATION_TYPES, SEVERITIES, ParliamentItem

logger = logging.getLogger(__name__)

PROMPT_HEADER = "# Impact assessment"
ITEM_HEADER = "## Parliamentary item"
CANDIDATE_HEADER = "## Candidate clause "

_MAX_ITEM_CHARS = 6000
# Clauses are sent whole. The M1 chunker leaves some documents with a single
# 16 KB "clause" for an entire section, and a truncated clause would come back
# as a truncated rewrite that M5 would then apply. Long clauses use the `edits`
# form instead of a full rewrite, so the model's output stays small.
_MAX_CLAUSE_CHARS = 20000
_EDITS_PREFERRED_OVER = 1500

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "legislation_type": {
            "type": ["string", "null"],
            "enum": ["amendment", "new_legislation", None],
        },
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause_ref": {"type": "string"},
                    "impacted": {"type": "boolean"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "rationale": {"type": "string"},
                    "suggested_text": {"type": ["string", "null"]},
                    "edits": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "object",
                            "properties": {
                                "find": {"type": "string"},
                                "replace": {"type": "string"},
                            },
                            "required": ["find", "replace"],
                        },
                    },
                },
                "required": ["clause_ref", "impacted", "severity", "rationale"],
            },
        },
    },
    "required": ["assessments"],
}


@dataclass
class ImpactAssessment:
    """The judge's verdict on one (parliament item x clause) pair."""

    clause_ref: str  # `<doc-slug>#<anchor>`, matches Clause.ref
    impacted: bool
    severity: str  # one of models.SEVERITIES
    rationale: str
    suggested_text: str = ""  # "" when not impacted or no rewrite proposed
    legislation_type: str | None = None  # judge override for the item, or None to keep


def assess(
    item: ParliamentItem,
    candidates: list[Candidate],
    provider: LLMProvider | None = None,
) -> list[ImpactAssessment]:
    """Judge every candidate clause in one call. Empty list on LLMError."""
    if not candidates:
        return []

    active_provider = provider or get_provider()
    prompt = build_prompt(item, candidates)

    try:
        response = active_provider.complete_json(prompt, RESPONSE_SCHEMA)
    except LLMError as exc:
        # Carry the provider's own reason through: "offline, cold cache" and
        # "the CLI is not installed" are very different problems and the
        # operator cannot tell them apart from a bare failure count.
        logger.warning(
            "impact assessment failed for %r via provider %r: %s; item left unprocessed",
            item.sprs_id,
            getattr(active_provider, "name", "?"),
            exc,
        )
        return []

    return parse_response(response, candidates)


def build_prompt(item: ParliamentItem, candidates: list[Candidate]) -> str:
    """The judge prompt. Markers are fixed - see the module docstring."""
    lines = [
        PROMPT_HEADER,
        "",
        "You are counsel at a Singapore law firm. Parliament has just debated the item "
        "below. For each candidate clause from the firm's own documents, decide whether "
        "the item changes, or is likely to change, the law that clause relies on.",
        "",
        "For every candidate clause return one assessment object:",
        '- "clause_ref": copy the reference from the "Candidate clause" heading exactly.',
        '- "impacted": true only if the clause would need review or amendment because '
        "of what was said; false for tangential overlap in vocabulary.",
        '- "severity": "high" when the clause becomes non-compliant, void or must be '
        'amended before the next renewal; "medium" when it should be revisited or '
        'carries commercial exposure; "low" when the link is tangential and worth '
        "monitoring only.",
        '- "rationale": two or three sentences a lawyer reads first. Cite the specific '
        "part of the parliamentary item (the clause of the Bill, the Minister's "
        "statement) that bites on this clause.",
        '- "suggested_text": for an impacted clause, the complete rewritten clause text '
        "ready to paste into the document, preserving its numbering style and defined "
        "terms; null when not impacted or when no rewrite is appropriate.",
        f'- "edits": for a clause longer than about {_EDITS_PREFERRED_OVER} characters, '
        'give targeted changes instead of "suggested_text": a list of {"find": <exact '
        'passage copied verbatim from the clause>, "replace": <its replacement>} objects. '
        "Each find string must appear in the clause exactly once. Use one of "
        '"suggested_text" or "edits", never both.',
        "",
        'Also return "legislation_type": "amendment" if the item changes law already on '
        'the books, "new_legislation" if it introduces something new, or null if unsure.',
        "",
        'Respond with a single JSON object: {"legislation_type": ..., "assessments": '
        "[...]}. No prose outside the JSON.",
        "",
        ITEM_HEADER,
        f"Title: {item.title}",
        f"Type: {item.item_type or 'unknown'}; sitting date: {item.sitting_date}",
        f"Speaker: {item.speaker or 'unknown'}",
        f"Current legislation_type (heuristic): {item.legislation_type or 'unknown'}",
        "",
        (item.body_text or item.summary or "").strip()[:_MAX_ITEM_CHARS],
        "",
    ]
    for cand in candidates:
        clause = cand.clause
        heading = " ".join(part for part in (clause.number, clause.heading) if part).strip()
        lines.extend(
            [
                f"{CANDIDATE_HEADER}{clause.ref}",
                f"Document: {cand.document.title} ({cand.document.sector})",
                f"Heading: {heading or '(none)'}",
                "Text:",
                clause.text.strip()[:_MAX_CLAUSE_CHARS],
                "",
            ]
        )
    return "\n".join(lines)


def parse_response(response: dict[str, Any], candidates: list[Candidate]) -> list[ImpactAssessment]:
    """Map a provider response onto the candidates, defensively.

    Unknown clause_refs are dropped; a candidate the model skipped is returned as
    not impacted; an unknown severity becomes "low"; a null suggested_text
    becomes "". The item-level legislation_type is copied onto every assessment.
    """
    override = response.get("legislation_type")
    if override not in LEGISLATION_TYPES:
        override = None

    by_ref: dict[str, dict[str, Any]] = {}
    raw = response.get("assessments")
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and isinstance(entry.get("clause_ref"), str):
                by_ref.setdefault(entry["clause_ref"], entry)

    results: list[ImpactAssessment] = []
    for cand in candidates:
        entry = by_ref.get(cand.clause.ref)
        if entry is None:
            results.append(
                ImpactAssessment(
                    clause_ref=cand.clause.ref,
                    impacted=False,
                    severity="low",
                    rationale="not assessed",
                    legislation_type=override,
                )
            )
            continue
        severity = entry.get("severity")
        if severity not in SEVERITIES:
            severity = "low"
        suggested = entry.get("suggested_text")
        if not isinstance(suggested, str) or not suggested:
            suggested = apply_edits(cand.clause.text, entry.get("edits"))
        results.append(
            ImpactAssessment(
                clause_ref=cand.clause.ref,
                impacted=bool(entry.get("impacted", False)),
                severity=severity,
                rationale=str(entry.get("rationale") or ""),
                suggested_text=suggested,
                legislation_type=override,
            )
        )
    return results


def apply_edits(clause_text: str, edits: Any) -> str:
    """Apply `[{"find", "replace"}, ...]` to the full clause text.

    Returns "" (no rewrite) unless every find string occurs exactly once and at
    least one edit changes something - a partial patch is worse than none,
    because M5 applies `suggested_text` wholesale.
    """
    if not isinstance(edits, list) or not edits:
        return ""
    text = clause_text
    for edit in edits:
        if not isinstance(edit, dict):
            return ""
        find, replace = edit.get("find"), edit.get("replace")
        if not isinstance(find, str) or not find or not isinstance(replace, str):
            return ""
        if text.count(find) != 1:
            logger.warning("edit rejected: find string occurs %d times", text.count(find))
            return ""
        text = text.replace(find, replace, 1)
    return text if text != clause_text else ""
