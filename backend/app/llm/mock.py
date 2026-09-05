"""Deterministic provider for tests and a zero-risk stage demo.

No network, no subprocess. It understands the concept-tagging prompt shape
(see `tagging.py`'s `## Clause <anchor>: <heading>` blocks) well enough to
keyword-match a fixed table of legal concepts per clause, so offline ingest
and tests get genuinely plausible tags rather than placeholders. The same
prompt always produces the same output - there is no randomness anywhere
in this module.
"""
from __future__ import annotations

import re
from typing import Any

_CLAUSE_HEADER_RE = re.compile(r"^##\s*Clause\s+(\S+):")

# Concept name (Title Case, as returned to callers) -> substrings that,
# found in the lower-cased clause text, indicate the concept is present.
_CONCEPT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Notice Period": ("notice period", "days' notice", "days notice", "written notice"),
    "Termination": ("terminate", "termination"),
    "Confidentiality": ("confidential", "non-disclosure", "nda"),
    "Indemnity": ("indemnif",),
    "Payment Terms": ("payment terms", "invoice", "payable", "due within"),
    "Governing Law": ("governing law", "governed by the laws", "jurisdiction"),
    "Force Majeure": ("force majeure", "act of god"),
    "Assignment": ("assign",),
    "Dispute Resolution": ("dispute", "arbitration", "mediation"),
    "Personal Data": ("personal data", "pdpa", "data protection"),
    "Warranties": ("warrant",),
    "Subletting": ("sublet", "sub-let", "sub-letting"),
    "Rent Review": ("rent review", "revised rent", "review the rent"),
    "Insurance": ("insurance", "insured", "insurer"),
    "Liability Cap": ("liability cap", "limitation of liability", "cap on liability"),
    "Tenure": ("tenure", "lease term", "term of this lease", "term of this agreement"),
    "Exclusivity": ("exclusivity", "exclusive right", "sole and exclusive"),
    "Conditions Precedent": ("condition precedent", "conditions precedent"),
}


class MockProvider:
    """No-op provider that keyword-matches known legal concepts per clause."""

    name = "mock"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        clauses = _split_clauses(prompt)
        if not clauses:
            return {}
        return {anchor: _match_concepts(body) for anchor, body in clauses.items()}


def _split_clauses(prompt: str) -> dict[str, str]:
    """Split a tagging prompt into anchor -> clause body, by header line."""
    clauses: dict[str, str] = {}
    current_anchor: str | None = None
    current_lines: list[str] = []

    for line in prompt.splitlines():
        header = _CLAUSE_HEADER_RE.match(line)
        if header:
            if current_anchor is not None:
                clauses[current_anchor] = "\n".join(current_lines)
            current_anchor = header.group(1)
            current_lines = []
        elif current_anchor is not None:
            current_lines.append(line)

    if current_anchor is not None:
        clauses[current_anchor] = "\n".join(current_lines)

    return clauses


def _match_concepts(text: str) -> list[str]:
    lowered = text.lower()
    return [
        name
        for name, keywords in _CONCEPT_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
