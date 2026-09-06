"""Deterministic provider for tests and a zero-risk stage demo.

No network, no subprocess. It understands two prompt shapes well enough to
answer plausibly, and the same prompt always produces the same output - there
is no randomness anywhere in this module:

* the concept-tagging prompt (`tagging.py`, `## Clause <anchor>: <heading>`
  blocks) - keyword-matches a fixed table of legal concepts per clause;
* the impact-assessment prompt (`analysis/impact.py`, first line
  `# Impact assessment`, `## Candidate clause <ref>` blocks) - a clause is
  "impacted" when it shares at least one concept with the parliamentary item,
  severity rises with the number shared, and the suggested text rewrites
  notice-period phrasings so a downstream redline is never empty.
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
    "Renewal": ("renew", "renewal", "option to renew"),
}

# --- judge mode -------------------------------------------------------------

_JUDGE_HEADER = "# Impact assessment"
_ITEM_HEADER = "## Parliamentary item"
_CANDIDATE_RE = re.compile(r"^## Candidate clause (\S+)\s*$", re.MULTILINE)

_MONTHS_RE = re.compile(
    r"\b(?:one|two|1|2)\s*(?:\(\s*[12]\s*\)\s*)?(?:calendar\s+)?months?(?P<poss>'s?)?",
    re.IGNORECASE,
)
_DAYS_RE = re.compile(
    r"\b(?:thirty|sixty|30|60)\s*(?:\(\s*(?:30|60)\s*\)\s*)?days(?P<poss>')?",
    re.IGNORECASE,
)
# "seven (7) days", "(_______) months", "3 months'" - the clause sets a period.
_PERIOD_RE = re.compile(
    r"(?:\(\s*[\d_]+\s*\)|\b\d+)\s*(?:calendar\s+)?(?:months?|days?|weeks?)\b", re.IGNORECASE
)
_FALLBACK_SENTENCE = (
    " Notwithstanding the foregoing, any notice period under this clause shall be "
    "no shorter than the minimum prescribed by written law."
)


class MockProvider:
    """No-op provider that keyword-matches known legal concepts."""

    name = "mock"

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if prompt.startswith(_JUDGE_HEADER):
            return _judge(prompt)
        clauses = _split_clauses(prompt)
        if not clauses:
            return {}
        return {anchor: _match_concepts(body) for anchor, body in clauses.items()}


# --- tagging mode -----------------------------------------------------------


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


# --- judge mode helpers -------------------------------------------------------


def _judge(prompt: str) -> dict[str, Any]:
    item_text, candidates = _split_judge_prompt(prompt)
    item_concepts = set(_match_concepts(item_text))
    assessments = []
    for ref, clause_text in candidates:
        shared = [name for name in _match_concepts(clause_text) if name in item_concepts]
        impacted = bool(shared)
        if not impacted:
            assessments.append(
                {
                    "clause_ref": ref,
                    "impacted": False,
                    "severity": "low",
                    "rationale": "The parliamentary item does not touch the subject matter "
                    "of this clause.",
                    "suggested_text": None,
                }
            )
            continue
        rewritten, period_changed = _rewrite(clause_text)
        # A clause that prescribes a time period the item overrides (a concrete
        # one rewritten above, or a template blank such as "(____) months")
        # must be amended: high. A merely related clause is revisited: medium.
        prescribes_period = bool(_PERIOD_RE.search(clause_text))
        severity = "high" if period_changed or prescribes_period or len(shared) >= 2 else "medium"
        assessments.append(
            {
                "clause_ref": ref,
                "impacted": True,
                "severity": severity,
                "rationale": _rationale(item_text, shared),
                "suggested_text": rewritten,
            }
        )
    return {"legislation_type": _legislation_type(item_text), "assessments": assessments}


def _split_judge_prompt(prompt: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (item text, [(clause_ref, clause text), ...])."""
    item_start = prompt.find(_ITEM_HEADER)
    headers = list(_CANDIDATE_RE.finditer(prompt))
    item_end = headers[0].start() if headers else len(prompt)
    item_text = prompt[item_start + len(_ITEM_HEADER) : item_end] if item_start >= 0 else ""

    candidates: list[tuple[str, str]] = []
    for i, match in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(prompt)
        block = prompt[match.end() : end]
        marker = block.find("Text:")
        text = block[marker + len("Text:") :] if marker >= 0 else block
        candidates.append((match.group(1), text.strip()))
    return item_text, candidates


def _rationale(item_text: str, shared: list[str]) -> str:
    keywords = [kw for name in shared for kw in _CONCEPT_KEYWORDS[name]]
    quote = ""
    for sentence in re.split(r"(?<=[.!?])\s+", item_text.strip()):
        lowered = sentence.lower()
        if any(kw in lowered for kw in keywords):
            quote = sentence.strip()
            break
    concepts = ", ".join(shared)
    rationale = f"The item bears on this clause's treatment of {concepts}."
    if quote:
        rationale += f' Parliament said: "{quote[:240]}"'
    return rationale


def _rewrite(clause_text: str) -> tuple[str, bool]:
    """Rewrite notice-period phrasings. Returns (text, a period was changed).

    The text always differs from the input so a downstream redline is never
    empty: when no period phrasing is present a statutory-minimum sentence is
    appended instead.
    """

    def to_three_months(match: re.Match[str]) -> str:
        return "three (3) months'" if match.group("poss") else "three (3) months"

    rewritten = _MONTHS_RE.sub(to_three_months, clause_text)
    rewritten = _DAYS_RE.sub(to_three_months, rewritten)
    if rewritten != clause_text:
        return rewritten, True
    return clause_text.rstrip() + _FALLBACK_SENTENCE, False


def _legislation_type(item_text: str) -> str | None:
    lowered = item_text.lower()
    if "amend" in lowered:
        return "amendment"
    if "new act" in lowered or "introduces" in lowered or "framework" in lowered:
        return "new_legislation"
    return None
