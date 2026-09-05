"""Write the Obsidian-compatible markdown vault.

Layout:
  vault/documents/<slug>.md    frontmatter + `## <n> <heading>` per clause
  vault/concepts/<slug>.md     graph hubs, e.g. "Notice Period"
  vault/parliament/<date>-<slug>.md
  vault/index.md

Clauses link to concepts with [[wikilinks]] so the vault opens natively in
Obsidian - the knowledge base is plain files, not a database blob.

Format is frozen in `docs/VAULT_FORMAT.md`. Frontmatter is hand-serialised
(not via a generic YAML dumper) so key order and plain-scalar style match the
doc exactly; values are quoted only when a bare scalar would be ambiguous.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.models import Clause, Concept, Document, ParliamentItem

_YAML_RESERVED = {"null", "true", "false", "yes", "no", "~", ""}
_UNSAFE_LEADING = tuple("-?:,[]{}#&*!|>'\"%@`")


def _now_iso() -> str:
    """Current UTC time, second precision, matching `docs/VAULT_FORMAT.md` §3."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _is_plain_safe(value: str) -> bool:
    if value.lower() in _YAML_RESERVED:
        return False
    if value != value.strip():
        return False
    if value.startswith(_UNSAFE_LEADING):
        return False
    if ": " in value or value.endswith(":"):
        return False
    if "\n" in value or "#" in value:
        return False
    return True


def _yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if _is_plain_safe(text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _frontmatter(pairs: list[tuple[str, object]]) -> str:
    lines = ["---"]
    for key, value in pairs:
        if isinstance(value, list):
            lines.append(f"{key}: {_yaml_list(value)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def _finalize(text: str) -> str:
    """Strip trailing whitespace per line and collapse to exactly one final `\\n`."""
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_finalize(text), encoding="utf-8", newline="\n")
    return path


def _clause_heading_line(number: str, heading: str) -> str:
    """`## <n> <heading>` per §3. Number comes first so the reader can split on
    "first token starts with a digit" -> that token is the number."""
    parts = [p for p in ((number or "").strip(), (heading or "").strip()) if p]
    return " ".join(parts) if parts else "Clause"


def _document_body(title: str, clauses: list[Clause],
                    clause_concepts: dict[str, list[tuple[str, str]]]) -> str:
    lines = [f"# {title}", ""]
    for clause in clauses:
        lines.append(f"## {_clause_heading_line(clause.number, clause.heading)}")
        lines.append(f"<!-- anchor: {clause.anchor} -->")
        lines.append("")
        text = (clause.text or "").strip()
        lines.append(text)
        concepts = clause_concepts.get(clause.ref, [])
        if concepts:
            links = ", ".join(f"[[{slug}|{name}]]" for slug, name in concepts)
            lines.append("")
            lines.append(f"**Concepts:** {links}")
        lines.append("")
    return "\n".join(lines)


def _document_body_error(title: str, parse_error: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"This document could not be parsed automatically ({parse_error}). "
        "Convert it to a supported format (PDF or DOCX with extractable text) "
        "and re-run ingest.",
        "",
    ]
    return "\n".join(lines)


def write_document(
    doc: Document,
    clauses: list[Clause],
    clause_concepts: dict[str, list[tuple[str, str]]],
) -> Path:
    """Write `vault/documents/<slug>.md`. `doc.parse_error` still gets a file (§3)."""
    clauses_sorted = sorted(clauses, key=lambda c: c.order_index)
    concept_slugs = sorted({slug for pairs in clause_concepts.values() for slug, _ in pairs})
    fm = _frontmatter(
        [
            ("title", doc.title),
            ("slug", doc.slug),
            ("type", "document"),
            ("sector", doc.sector),
            ("source", doc.source_path),
            ("file_type", doc.file_type),
            ("version", doc.version),
            ("clause_count", len(clauses_sorted)),
            ("concepts", concept_slugs),
            ("ingested_at", _now_iso()),
            ("parse_error", doc.parse_error),
        ]
    )
    if doc.parse_error:
        body = _document_body_error(doc.title, doc.parse_error)
    else:
        body = _document_body(doc.title, clauses_sorted, clause_concepts)
    path = settings.vault_dir / "documents" / f"{doc.slug}.md"
    return _write(path, fm + "\n\n" + body)


def write_concept(concept: Concept, clause_rows: list[tuple[str, str, str]]) -> Path:
    """Write `vault/concepts/<slug>.md`. `clause_rows` is (doc_slug, anchor, heading)."""
    rows_sorted = sorted(clause_rows, key=lambda r: (r[0], r[1]))
    fm = _frontmatter(
        [
            ("title", concept.name),
            ("slug", concept.slug),
            ("type", "concept"),
            ("clause_count", len(rows_sorted)),
        ]
    )
    lines = [f"# {concept.name}", ""]
    if concept.description:
        lines.append(concept.description.strip())
        lines.append("")
    lines.append("## Clauses")
    for doc_slug, anchor, heading in rows_sorted:
        lines.append(f"- [[{doc_slug}]] - `{anchor}` - {heading}")
    body = "\n".join(lines)
    path = settings.vault_dir / "concepts" / f"{concept.slug}.md"
    return _write(path, fm + "\n\n" + body)


def write_parliament_item(item: ParliamentItem, concepts: list[str]) -> Path:
    """Write `vault/parliament/<date>-<slug>.md` per §5."""
    fm = _frontmatter(
        [
            ("title", item.title),
            ("slug", item.slug),
            ("type", "parliament_item"),
            ("sitting_date", item.sitting_date),
            ("sprs_id", item.sprs_id),
            ("item_type", item.item_type),
            ("legislation_type", item.legislation_type),
            ("speaker", item.speaker),
            ("url", item.url),
            ("concepts", sorted(concepts)),
        ]
    )
    lines = [f"# {item.title}", ""]
    body_text = (item.body_text or item.summary or "").strip()
    if body_text:
        lines.append(body_text)
        lines.append("")
    body = "\n".join(lines)
    path = settings.vault_dir / "parliament" / f"{item.sitting_date}-{item.slug}.md"
    return _write(path, fm + "\n\n" + body)


_GENERATED_BEGIN = "<!-- BEGIN GENERATED: documents and concepts (do not edit below) -->"
_GENERATED_END = "<!-- END GENERATED -->"

_DEFAULT_INDEX_INTRO = """---
title: Lex Sentinel vault
type: index
---

# Knowledge base

The firm's documents, the legal concepts that connect them, and the
parliamentary items being tracked. Plain markdown - open this folder directly
in Obsidian to browse the graph.

- `documents/` - contracts and policies, one file per document, clauses as `##` headings
- `concepts/` - the graph hubs (e.g. Notice Period, PDPA Consent)
- `parliament/` - scraped Hansard items, one file per item

Populated by `python scripts/ingest.py`."""


def write_index(documents: list[Document], concepts: list[Concept]) -> Path:
    """Rewrite `vault/index.md`: keep the prose intro, regenerate the listings.

    The intro is everything before the `_GENERATED_BEGIN` marker in the existing
    file (or a default intro if the file doesn't exist yet). Rerunning this
    regenerates only the marked block, so the file stays idempotent.
    """
    path = settings.vault_dir / "index.md"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        intro = existing.split(_GENERATED_BEGIN, 1)[0].rstrip("\n")
    else:
        intro = _DEFAULT_INDEX_INTRO

    docs_sorted = sorted(documents, key=lambda d: d.slug)
    concepts_sorted = sorted(concepts, key=lambda c: c.slug)

    lines = [_GENERATED_BEGIN, "", "## Documents"]
    if docs_sorted:
        for d in docs_sorted:
            note = f" (parse error: {d.parse_error})" if d.parse_error else ""
            lines.append(f"- [[{d.slug}]] - {d.title} ({d.sector}){note}")
    else:
        lines.append("- (none yet)")
    lines.append("")
    lines.append("## Concepts")
    if concepts_sorted:
        for c in concepts_sorted:
            lines.append(f"- [[{c.slug}]] - {c.name}")
    else:
        lines.append("- (none yet)")
    lines.append("")
    lines.append(_GENERATED_END)

    generated = "\n".join(lines)
    return _write(path, intro + "\n\n" + generated)
