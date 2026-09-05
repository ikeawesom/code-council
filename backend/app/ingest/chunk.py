"""Split a parsed document into clauses with stable anchors.

Anchors must survive re-ingest and edits, because proposals, edits and graph
edges all reference them: "warehouse-lease#7-2".

Anchor derivation follows `docs/VAULT_FORMAT.md` section 2 literally - read
that table before changing anything here, it is an API.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.ingest.parse import ParsedDoc
from app.textutil import collapse_whitespace, slugify

# A "heading" line that repeats this often is a running page header/footer
# (e.g. "CONFIDENTIAL", "EXECUTION VERSION" printed on every PDF page), not a
# real section boundary - demote it to body noise instead of fragmenting
# clauses around it.
_REPEATED_HEADING_THRESHOLD = 3

_ANCHOR_HEADING_MAX_LEN = 40
_STRIP_CHARS = " .:-–—"

# "Schedule 2, para 3" / "Schedule 2" -> ("Schedule 2, para 3", "sch-2-3")
_SCHEDULE_RE = re.compile(
    r"^schedule\s+(?P<sch>\d+)\s*,?\s*(?:para(?:graph)?\.?\s*(?P<para>\d+))?",
    re.IGNORECASE,
)

# "7.2", "7.2.1", "7(a)", "Clause 14", "14." -> number + anchor pieces.
_NUM_RE = re.compile(
    r"^(?:clause\s+)?(?P<num>\d+(?:\.\d+)*)(?P<paren>\([a-z0-9]+\))?[.:)]?\s*",
    re.IGNORECASE,
)


@dataclass
class ParsedClause:
    anchor: str  # e.g. "7-2"
    number: str  # e.g. "7.2" ("" if unnumbered)
    heading: str
    text: str
    order_index: int


def _match_schedule(text: str) -> tuple[str, str, str] | None:
    match = _SCHEDULE_RE.match(text)
    if not match:
        return None
    sch = match.group("sch")
    para = match.group("para")
    number = f"Schedule {sch}" + (f", para {para}" if para else "")
    anchor = f"sch-{sch}" + (f"-{para}" if para else "")
    remainder = text[match.end() :].strip(_STRIP_CHARS)
    return number, anchor, remainder


def _match_number(text: str) -> tuple[str, str, str] | None:
    match = _NUM_RE.match(text)
    if not match:
        return None
    num = match.group("num")
    paren = match.group("paren")
    remainder = text[match.end() :].strip(_STRIP_CHARS)
    if paren:
        letter = paren.strip("()")
        number = f"{num}({letter})"
        anchor = f"{num.replace('.', '-')}-{letter.lower()}"
    else:
        number = num
        anchor = num.replace(".", "-")
    return number, anchor, remainder


def _new_section() -> dict:
    return {"number": "", "heading": "", "anchor_base": None, "parts": []}


def split_clauses(parsed: ParsedDoc, doc_slug: str) -> list[ParsedClause]:
    # doc_slug is part of the frozen signature (callers build `ref` from it);
    # anchors here are document-local and don't need it.
    del doc_slug
    if parsed.parse_error:
        return []

    heading_counts = Counter(
        b.text.strip() for b in parsed.blocks if b.kind == "heading" and b.text.strip()
    )
    noisy_headings = {t for t, n in heading_counts.items() if n >= _REPEATED_HEADING_THRESHOLD}

    sections: list[dict] = [_new_section()]

    for block in parsed.blocks:
        text = block.text.strip()
        if not text:
            continue
        is_heading = block.kind == "heading" and text not in noisy_headings

        matched = _match_schedule(text) or _match_number(text)
        if matched:
            number, anchor_base, remainder = matched
            # A numeric match inside ordinary body prose (e.g. "2 months'
            # notice...") should not start a new clause. Trust it when the
            # block was already flagged as a heading, or when what follows
            # the number reads like a title (empty or capitalised).
            is_confident = is_heading or remainder == "" or remainder[0].isupper()
            if is_confident:
                section = _new_section()
                section["number"] = number
                section["heading"] = remainder
                section["anchor_base"] = anchor_base
                sections.append(section)
                continue

        if is_heading:
            section = _new_section()
            section["heading"] = text
            sections.append(section)
            continue

        sections[-1]["parts"].append(text)

    # Drop the leading placeholder section if it never collected anything
    # (i.e. the document's first block was itself a clause/heading start).
    if not sections[0]["number"] and not sections[0]["heading"] and not sections[0]["parts"]:
        sections.pop(0)

    # A heading with no body after collapse_whitespace is not a clause (e.g.
    # an "Article 1. Definitions" super-heading immediately followed by its
    # own numbered "1.1" sub-clause, with nothing of its own in between).
    # Chosen behaviour: fold its label into the body of the NEXT surviving
    # clause rather than silently dropping it, so a lawyer still sees that
    # label instead of losing it - a bare drop reads as a gap in a legal
    # document, a folded lead-in sentence does not. Several consecutive
    # empty headings fold together, in order. A trailing empty heading with
    # no following clause to fold into (end of document) has nothing to
    # fold into and is dropped - there is no clause left for it to attach to.
    folded: list[dict] = []
    pending_labels: list[str] = []
    for section in sections:
        body = collapse_whitespace(" ".join(section["parts"]))
        if not body:
            label = section["heading"] or section["number"]
            if label:
                pending_labels.append(label)
            continue
        if pending_labels:
            body = collapse_whitespace(". ".join([*pending_labels, body]))
            pending_labels = []
        folded.append(
            {
                "number": section["number"],
                "heading": section["heading"],
                "anchor_base": section["anchor_base"],
                "text": body,
            }
        )

    clauses: list[ParsedClause] = []
    anchor_counts: dict[str, int] = {}

    for order_index, section in enumerate(folded):
        anchor_base = section["anchor_base"]
        if anchor_base is None:
            if section["heading"]:
                anchor_base = slugify(section["heading"], max_length=_ANCHOR_HEADING_MAX_LEN)
            if not anchor_base:
                anchor_base = f"s{order_index}"

        count = anchor_counts.get(anchor_base, 0)
        anchor_counts[anchor_base] = count + 1
        anchor = anchor_base if count == 0 else f"{anchor_base}-{count + 1}"

        clauses.append(
            ParsedClause(
                anchor=anchor,
                number=section["number"],
                heading=section["heading"],
                text=section["text"],
                order_index=order_index,
            )
        )

    return clauses
