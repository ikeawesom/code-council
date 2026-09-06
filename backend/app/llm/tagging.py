"""M1 consumer of the LLM layer: batch concept-tagging for a document's clauses.

One LLM call per document, not per clause - clauses are batched into a single
prompt and the model returns anchor -> concept-name mapping. A tagging failure
must degrade the vault (every clause gets no concepts), never crash ingest.
"""
from __future__ import annotations

import logging
from typing import Any

from app.llm.base import LLMError, LLMProvider, get_provider
from app.textutil import slugify

logger = logging.getLogger(__name__)

_MAX_CLAUSE_CHARS = 600

# Not a strict JSON Schema validator - passed through to the provider (and the
# cache key) so it can steer/describe the expected shape.
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "Map of clause anchor -> list of concept names.",
    "additionalProperties": {"type": "array", "items": {"type": "string"}},
}


def tag_document_clauses(
    doc_title: str,
    clauses: list[tuple[str, str, str]],
    provider: LLMProvider | None = None,
) -> dict[str, list[tuple[str, str]]]:
    """Tag every clause of a document with legal concepts in one LLM call.

    `clauses` is `(anchor, heading, text)`. Returns anchor -> list of
    `(concept_slug, concept_name)`. Unknown anchors in the provider's
    response are dropped; anchors missing from the response map to `[]`.
    On `LLMError` every anchor maps to `[]` rather than raising.
    """
    if not clauses:
        return {}

    active_provider = provider or get_provider()
    prompt = _build_prompt(doc_title, clauses)
    known_anchors = {anchor for anchor, _heading, _text in clauses}

    try:
        response = active_provider.complete_json(prompt, _RESPONSE_SCHEMA)
    except LLMError:
        logger.warning(
            "concept tagging failed for %r via provider %r; degrading to no concepts",
            doc_title,
            getattr(active_provider, "name", "?"),
        )
        return {anchor: [] for anchor in known_anchors}

    result: dict[str, list[tuple[str, str]]] = {anchor: [] for anchor in known_anchors}

    for anchor, names in response.items():
        if anchor not in known_anchors or not isinstance(names, list):
            continue
        result[anchor] = [
            (slugify(name), _title_case(name)) for name in names if isinstance(name, str) and name
        ]

    return result


def _title_case(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split())


# The concept hubs that make retrieval work. Seeded into every tagging prompt
# so the model reuses one name per idea instead of minting near-synonyms: after
# the first ingest 115 of 219 concepts hung off a single clause, and a hub that
# spans documents is what lets one parliamentary item find every affected
# contract. Drawn from the names that already spanned two or more documents,
# plus the tenancy/data-protection hubs the demo relies on. A prompt change,
# not a schema: adding a name here needs no migration, just a re-ingest.
CONTROLLED_VOCABULARY: tuple[str, ...] = (
    "Acceptance Of Offer",
    "Additional Services",
    "Appointment",
    "Arbitration",
    "Assignment",
    "Commencement",
    "Completion",
    "Completion Date",
    "Compulsory Acquisition",
    "Condition Of Property",
    "Conditions Precedent",
    "Confidentiality",
    "Conflict Of Interest",
    "Costs And Expenses",
    "Damages",
    "Default",
    "Defects Liability",
    "Definitions",
    "Delay",
    "Deposit",
    "Dispute Resolution",
    "Encumbrances",
    "Exclusivity",
    "Extension Of Time",
    "Force Majeure",
    "Forfeiture Of Deposit",
    "Goods And Services Tax",
    "Governing Law",
    "Indemnity",
    "Insolvency",
    "Insurance",
    "Intellectual Property",
    "Interpretation",
    "Joint And Several Liability",
    "Jurisdiction",
    "Licence",
    "Limitation Of Liability",
    "Mediation",
    "Notice Period",
    "Notices",
    "Parties",
    "Payment Terms",
    "Permitted Use",
    "Personal Data",
    "Purchase Price",
    "Refund Of Deposit",
    "Regulatory Compliance",
    "Remuneration",
    "Renewal",
    "Rent",
    "Rent Review",
    "Requisitions",
    "Rescission",
    "Scope Of Services",
    "Standard Of Care",
    "Statutory Compliance",
    "Subletting",
    "Survival Of Terms",
    "Tenancy",
    "Term",
    "Termination",
    "Third Party Rights",
    "Title",
    "Vacant Possession",
    "Variation",
    "Waiver",
    "Warranties",
)


def _build_prompt(doc_title: str, clauses: list[tuple[str, str, str]]) -> str:
    lines = [
        f'Identify legal concepts present in each clause of "{doc_title}".',
        "Respond with a JSON object mapping each clause anchor to a list of "
        'concept names, e.g. {"7-2": ["Notice Period", "Termination"]}. Use '
        "[] when a clause has no notable concepts.",
        "",
        "Prefer these concept names whenever one fits, spelled exactly as given; "
        "coin a new name only when no listed concept applies, and never a "
        "near-synonym of a listed one:",
        ", ".join(CONTROLLED_VOCABULARY),
        "",
    ]
    for anchor, heading, text in clauses:
        lines.append(f"## Clause {anchor}: {heading}")
        lines.append(text[:_MAX_CLAUSE_CHARS])
        lines.append("")
    return "\n".join(lines)
