"""Raw SPRS payloads -> `ParliamentItem` rows -> `vault/parliament/<date>-<slug>.md`.

Both `getHansardReport` (the daily sweep) and `getHansardTopic` (the ad-hoc,
keyword-driven path) land here before anything touches the database or the
vault. `takesSectionVOList` entries carry no id of their own (see
`app/scraper/sprs_client.py`), so `sprs_id` for a report item is derived
deterministically from the sitting date, section type and title - stable across
re-runs, which is what makes `persist_items` an upsert rather than a duplicate
factory.
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser
from sqlmodel import Session, select

from app.config import settings
from app.models import ParliamentItem
from app.scraper.sprs_client import iso_from_sprs, sprs_from_iso, topic_id
from app.textutil import collapse_whitespace, slugify
from app.vault.writer import write_parliament_item

SECTION_TYPE_LABELS: dict[str, str] = {
    "OA": "oral answer",
    "WA": "written answer",
    "WANA": "written answer (not answered)",
    "OS": "debate",
    "WS": "written statement",
}

# Block elements become paragraph breaks in `html_to_text`; everything else is
# an inline tag whose text is kept but whose markup is stripped. A private-use
# character (rather than "" or "\x00") is used as the paragraph sentinel: an
# empty separator makes `str.split` raise, and `\x00` corrupts selectolax's
# underlying C-string buffer and silently mangles the extracted text.
_BLOCK_TAG_RE = re.compile(r"</?(?:p|h[1-6]|li|div|br|tr)\b[^>]*/?>", re.I)
_PARA_SEP = ""

# Oral answers phrase this "<MP> asked the <Minister> ..."; written answers
# instead lead with "The following question stood in the name of <MP> ... To
# ask the <Minister> ..." - both name the answering minister after this phrase.
_ASKED_THE_RE = re.compile(r"(?:asked|to ask)\s+the\s+", re.I)
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*|[(),;.]")
# Lowercase function words that can appear inside a ministerial title
# ("Minister *for* Education", "Minister *of* State", "Coordinating Minister
# *and* Minister for Health"). Deliberately excludes "in" - "Minister-in-charge"
# is a single hyphenated token, and a bare "in" almost always starts a clause
# ("... in respect of ...", "... in light of ...") that must end the title.
_TITLE_CONNECTORS = {"for", "of", "the", "and", "to", "de"}
_TITLE_STOP_PUNCT = {"(", ",", ";", "."}


def html_to_text(html: str) -> str:
    """Hansard HTML -> plain text: paragraphs on blank lines, tags gone, entities decoded."""
    if not html:
        return ""
    marked = _BLOCK_TAG_RE.sub(_PARA_SEP, html)
    tree = HTMLParser(marked)
    node = tree.body if tree.body is not None else tree.root
    text = node.text(separator="") if node is not None else ""
    paragraphs = [collapse_whitespace(p) for p in text.split(_PARA_SEP)]
    return "\n\n".join(p for p in paragraphs if p)


def _consume_title(rest: str) -> str:
    """Walk tokens after "asked the " while they look like part of a title.

    A token continues the title if it's capitalised (a portfolio noun like
    "Education", "Manpower") or a connector ("for", "of", "and", ...); the walk
    stops at the first lowercase non-connector word or at title-ending
    punctuation, which is what turns "Minister for Education whether ..." into
    "Minister for Education" without needing "for" to always be a stop word
    (it can't be - "Minister for X" is the common case, not the exception).
    """
    out: list[str] = []
    for m in _TOKEN_RE.finditer(rest):
        tok = m.group(0)
        if tok in _TITLE_STOP_PUNCT:
            break
        if tok[0].isupper() or tok.lower() in _TITLE_CONNECTORS:
            out.append(tok)
        else:
            break
    return " ".join(out).strip()


def extract_speaker(html: str) -> str:
    """The answering minister, or else the first `<strong>` speaker name."""
    if not html:
        return ""
    tree = HTMLParser(html)
    node = tree.body if tree.body is not None else tree.root
    flat = collapse_whitespace(node.text(separator=" ")) if node is not None else ""
    asked = _ASKED_THE_RE.search(flat)
    if asked:
        candidate = _consume_title(flat[asked.end() :])
        if candidate:
            return candidate
    strong = tree.css_first("strong")
    if strong is not None:
        name = collapse_whitespace(strong.text()).rstrip(":").strip()
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
        return name
    return ""


_NEW_LEGISLATION_RE = re.compile(
    r"\b(new|introduc(?:e|es|ed|ing|tion of))\b.{0,40}"
    r"\b(bill|act|legislation|law|framework|scheme|regime)\b",
    re.I | re.S,
)
_BILL_RE = re.compile(r"\bbill\b", re.I)
_AMENDMENT_RE = re.compile(r"\bamendment\b", re.I)


def classify_legislation_type(title: str, text: str) -> str:
    """Badge 2: "new_legislation" or "amendment" (the default - most parliamentary
    activity touches law that already exists)."""
    if _BILL_RE.search(title) and not _AMENDMENT_RE.search(title):
        return "new_legislation"
    if _NEW_LEGISLATION_RE.search(title) or _NEW_LEGISLATION_RE.search(text):
        return "new_legislation"
    return "amendment"


_SLUG_MAX = 80


def item_slug(title: str) -> str:
    """Slug for a parliament item: `slugify`, but a title longer than the limit is
    cut at the last word boundary rather than mid-word, so filenames stay readable.
    `textutil.slugify` is frozen and truncates mid-word; this wraps it rather than
    changing it, because document slugs and anchors depend on its exact behaviour."""
    full = slugify(title, max_length=10_000)
    if len(full) <= _SLUG_MAX:
        return full
    cut = full[:_SLUG_MAX]
    if "-" in cut:
        cut = cut[: cut.rfind("-")]
    return cut.rstrip("-")


def report_sprs_id(sitting_iso: str, section_type: str, slug: str) -> str:
    """Deterministic id for a `takesSectionVOList` entry - sections carry no id."""
    return f"report:{sitting_iso}:{section_type.lower()}:{slug}"


def summarize(body_text: str, limit: int = 300) -> str:
    """First paragraph of `body_text`, truncated at the last space before `limit`."""
    first_para = body_text.split("\n\n", 1)[0].strip() if body_text else ""
    if len(first_para) <= limit:
        return first_para
    cut = first_para.rfind(" ", 0, limit)
    if cut <= 0:
        cut = limit
    return first_para[:cut].rstrip() + "..."


def normalize_report(payload: dict) -> list[ParliamentItem]:
    """`getHansardReport` payload -> one unsaved `ParliamentItem` per non-empty section.

    Only `takesSectionVOList` is read - `writtenAnswersVOList` and its siblings
    are decoys that stay empty even on a sitting with hundreds of written
    answers (see `app/scraper/sprs_client.py`).
    """
    sitting_iso = iso_from_sprs(payload["metadata"]["sittingDate"])
    url = f"https://sprs.parl.gov.sg/search/fullreport?sittingdate={sprs_from_iso(sitting_iso)}"
    seen_slugs: dict[str, int] = {}
    items: list[ParliamentItem] = []
    for section in payload.get("takesSectionVOList", []):
        content = section.get("content", "") or ""
        body_text = html_to_text(content)
        if not body_text:
            continue
        title = collapse_whitespace(section.get("title", ""))
        base_slug = item_slug(title)
        count = seen_slugs.get(base_slug, 0) + 1
        seen_slugs[base_slug] = count
        slug = base_slug if count == 1 else f"{base_slug}-{count}"
        section_type = section.get("sectionType", "")
        item_type = SECTION_TYPE_LABELS.get(section_type, section_type.lower())
        items.append(
            ParliamentItem(
                sprs_id=report_sprs_id(sitting_iso, section_type, slug),
                slug=slug,
                title=title,
                sitting_date=sitting_iso,
                item_type=item_type,
                legislation_type=classify_legislation_type(title, body_text),
                speaker=extract_speaker(content),
                url=url,
                summary=summarize(body_text),
                body_text=body_text,
                vault_path="",
            )
        )
    return items


_ITEM_TYPE_BY_PREFIX = {
    "oral-answer": "oral answer",
    "written-answer": "written answer",
    "written-answer-na": "written answer (not answered)",
}
_TRAILING_NUMBER_RE = re.compile(r"-\d+$")


def _item_type_from_report_id(sprs_id: str) -> str:
    prefix = _TRAILING_NUMBER_RE.sub("", sprs_id)
    return _ITEM_TYPE_BY_PREFIX.get(prefix, prefix.replace("-", " "))


def _first_heading_text(html: str) -> str:
    if not html:
        return ""
    tree = HTMLParser(html)
    heading = tree.css_first("h1, h2, h3, h4, h5, h6")
    return collapse_whitespace(heading.text()) if heading is not None else ""


def normalize_topic(payload: dict, report_id: str) -> ParliamentItem:
    """`getHansardTopic` payload -> one unsaved `ParliamentItem` (the ad-hoc path)."""
    sprs_id = topic_id(report_id)
    result_html = payload.get("resultHTML") or {}
    content = result_html.get("content", "") or ""
    # `resultData` is null on every real capture seen so far; `resultHTML.title`
    # is where the actual title lives, so it's tried before falling back to the
    # first heading in the body - without it, every ad-hoc fetch would title
    # itself after the ugly report id instead of the real Hansard title.
    title_source = payload.get("resultData") or result_html.get("title") or _first_heading_text(
        content
    )
    title = collapse_whitespace(str(title_source)) if title_source else sprs_id
    body_text = html_to_text(content)
    speaker = extract_speaker(content)
    if not speaker:
        mp_names = result_html.get("mpNames") or ""
        speaker = mp_names.split(",")[0].strip() if mp_names else ""
    return ParliamentItem(
        sprs_id=sprs_id,
        slug=item_slug(title),
        title=title,
        sitting_date=iso_from_sprs(payload["sittingDate"]),
        item_type=_item_type_from_report_id(sprs_id),
        legislation_type=classify_legislation_type(title, body_text),
        speaker=speaker,
        url=f"https://sprs.parl.gov.sg/search/topic?reportid={sprs_id}",
        summary=summarize(body_text),
        body_text=body_text,
        vault_path="",
    )


def persist_items(
    session: Session,
    items: list[ParliamentItem],
    concepts: dict[str, list[str]] | None = None,
) -> tuple[int, int]:
    """Upsert `items` by `sprs_id`, writing each one's vault file. Caller commits."""
    concepts = concepts or {}
    repo_root = settings.vault_dir.parent
    created = 0
    updated = 0
    for item in items:
        existing = session.exec(
            select(ParliamentItem).where(ParliamentItem.sprs_id == item.sprs_id)
        ).first()
        if existing is None:
            session.add(item)
            target = item
            created += 1
        else:
            existing.title = item.title
            existing.slug = item.slug
            existing.sitting_date = item.sitting_date
            existing.item_type = item.item_type
            existing.legislation_type = item.legislation_type
            existing.speaker = item.speaker
            existing.url = item.url
            existing.summary = item.summary
            existing.body_text = item.body_text
            target = existing
            updated += 1
        path = write_parliament_item(target, concepts.get(target.sprs_id, []))
        target.vault_path = path.relative_to(repo_root).as_posix()
    session.flush()
    return created, updated
