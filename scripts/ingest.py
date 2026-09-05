"""Ingest every document in data/inbox/ into the vault + database.

    python scripts/ingest.py [--llm mock|claude_cli|local] [--force] [--only SLUG]

parse -> chunk into clauses -> LLM-tag with legal concepts -> write vault
markdown -> rebuild graph.json. Idempotent: re-running updates in place, never
duplicates rows, and re-writes byte-identical markdown apart from `ingested_at`.

Concept tagging costs one LLM call per document, and is skipped entirely for a
document that already has concepts unless `--force` is given - so a re-run after
a crash is free.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.db import init_db, session_scope  # noqa: E402
from app.graph.build import build_graph  # noqa: E402
from app.ingest.chunk import split_clauses  # noqa: E402
from app.ingest.parse import parse_document  # noqa: E402
from app.llm.base import LLMProvider, get_provider  # noqa: E402
from app.llm.tagging import tag_document_clauses  # noqa: E402
from app.models import Clause, ClauseConcept, Concept, Document  # noqa: E402
from app.textutil import slugify  # noqa: E402
from app.vault.writer import write_concept, write_document, write_index  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc"}


def discover_inputs() -> list[tuple[Path, str]]:
    """Every file under data/inbox/<sector>/, paired with its sector slug.

    The sector is the sub-folder name, slugified - a plain string, never an enum.
    Files sitting directly in the inbox root get the sector "general".
    """
    found: list[tuple[Path, str]] = []
    for path in sorted(settings.inbox_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        parent = path.parent
        sector = "general" if parent == settings.inbox_dir else slugify(parent.name)
        found.append((path, sector))
    return found


def _upsert_document(session: Session, slug: str, sector: str, path: Path, parsed) -> Document:
    doc = session.exec(select(Document).where(Document.slug == slug)).first()
    if doc is None:
        doc = Document(slug=slug, title=parsed.title, sector=sector)
        session.add(doc)
    doc.title = parsed.title
    doc.sector = sector
    doc.source_path = path.relative_to(REPO_ROOT).as_posix()
    doc.file_type = parsed.file_type
    doc.parse_error = parsed.parse_error
    session.flush()
    return doc


def _upsert_clauses(session: Session, doc: Document, parsed_clauses: list) -> list[Clause]:
    """Upsert by `ref` so clause ids - and therefore proposals - survive re-ingest."""
    existing = {
        c.ref: c for c in session.exec(select(Clause).where(Clause.document_id == doc.id)).all()
    }
    rows: list[Clause] = []
    for pc in parsed_clauses:
        ref = f"{doc.slug}#{pc.anchor}"
        row = existing.pop(ref, None)
        if row is None:
            row = Clause(document_id=doc.id, anchor=pc.anchor, ref=ref)
            session.add(row)
        row.anchor = pc.anchor
        row.number = pc.number
        row.heading = pc.heading
        row.text = pc.text
        row.order_index = pc.order_index
        rows.append(row)
    # Anything left in `existing` no longer appears in the source document.
    for stale in existing.values():
        for link in session.exec(
            select(ClauseConcept).where(ClauseConcept.clause_id == stale.id)
        ).all():
            session.delete(link)
        session.delete(stale)
    session.flush()
    doc.clause_count = len(rows)
    return rows


def _existing_tags(session: Session, rows: list[Clause]) -> dict[str, list[tuple[str, str]]]:
    """Read back the concepts already recorded for these clauses."""
    tags: dict[str, list[tuple[str, str]]] = {row.anchor: [] for row in rows}
    by_id = {row.id: row for row in rows}
    if not by_id:
        return tags
    links = session.exec(
        select(ClauseConcept).where(ClauseConcept.clause_id.in_(list(by_id)))  # type: ignore[attr-defined]
    ).all()
    for link in links:
        concept = session.get(Concept, link.concept_id)
        if concept is not None:
            tags[by_id[link.clause_id].anchor].append((concept.slug, concept.name))
    return tags


def _apply_tags(
    session: Session, rows: list[Clause], tags: dict[str, list[tuple[str, str]]]
) -> None:
    """Rebuild the clause <-> concept edges for this document."""
    for row in rows:
        for link in session.exec(
            select(ClauseConcept).where(ClauseConcept.clause_id == row.id)
        ).all():
            session.delete(link)
        for concept_slug, concept_name in tags.get(row.anchor, []):
            concept = session.exec(select(Concept).where(Concept.slug == concept_slug)).first()
            if concept is None:
                concept = Concept(slug=concept_slug, name=concept_name)
                session.add(concept)
                session.flush()
            session.add(ClauseConcept(clause_id=row.id, concept_id=concept.id))
    session.flush()


def ingest_one(
    session: Session,
    path: Path,
    sector: str,
    provider: LLMProvider,
    force: bool,
) -> tuple[Document, list[Clause], dict[str, list[tuple[str, str]]], bool]:
    slug = slugify(path.stem)
    parsed = parse_document(path)
    parsed_clauses = split_clauses(parsed, slug)

    doc = _upsert_document(session, slug, sector, path, parsed)
    rows = _upsert_clauses(session, doc, parsed_clauses)

    previous = _existing_tags(session, rows)
    already_tagged = any(previous.values())
    tagged_now = False
    if rows and (force or not already_tagged):
        tags = tag_document_clauses(
            doc.title,
            [(pc.anchor, pc.heading, pc.text) for pc in parsed_clauses],
            provider=provider,
        )
        tagged_now = True
    else:
        tags = previous
    _apply_tags(session, rows, tags)

    by_ref = {f"{doc.slug}#{anchor}": pairs for anchor, pairs in tags.items()}
    return doc, rows, by_ref, tagged_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest data/inbox into the vault.")
    parser.add_argument(
        "--llm",
        default=None,
        help="provider override: mock | claude_cli | local (default: settings.llm_provider)",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-tag concepts even if already recorded"
    )
    parser.add_argument("--only", default=None, help="ingest just the document with this slug")
    args = parser.parse_args()

    init_db()
    provider = get_provider(args.llm)
    inputs = discover_inputs()
    if args.only:
        inputs = [(p, s) for p, s in inputs if slugify(p.stem) == args.only]
    if not inputs:
        print(f"No documents found under {settings.inbox_dir}")
        return 1

    print(f"Provider: {provider.name}   Documents: {len(inputs)}\n")

    ingested = 0
    with session_scope() as session:
        for path, sector in inputs:
            doc, rows, by_ref, tagged_now = ingest_one(session, path, sector, provider, args.force)
            write_document(doc, rows, by_ref)
            ingested += 1
            status = "tagged" if tagged_now else "cached tags"
            note = f"  !! {doc.parse_error}" if doc.parse_error else ""
            print(f"  {doc.slug:<45} {sector:<26} {doc.clause_count:>4} clauses  {status}{note}")

        # Concept files and the index span the WHOLE vault, so they are rebuilt
        # from the database rather than from this run's documents - otherwise
        # `--only` would strip every other document's rows out of a shared
        # concept file and out of index.md.
        documents = list(session.exec(select(Document).order_by(Document.slug)).all())
        concepts = list(session.exec(select(Concept).order_by(Concept.slug)).all())
        clause_by_id = {c.id: c for c in session.exec(select(Clause)).all()}
        doc_slug_by_id = {d.id: d.slug for d in documents}

        rows_by_concept: dict[int, list[tuple[str, str, str]]] = {c.id: [] for c in concepts}
        for link in session.exec(select(ClauseConcept)).all():
            clause = clause_by_id.get(link.clause_id)
            if clause is None or link.concept_id not in rows_by_concept:
                continue
            rows_by_concept[link.concept_id].append(
                (doc_slug_by_id.get(clause.document_id, ""), clause.anchor, clause.heading)
            )

        # A concept nothing links to is not a hub - it is a leftover from an
        # earlier tagging pass (e.g. re-tagging with a different provider). Drop
        # the row and its stale vault file rather than writing an empty one.
        live: list[Concept] = []
        pruned = 0
        for concept in concepts:
            if rows_by_concept[concept.id]:
                live.append(concept)
                continue
            stale_file = settings.vault_dir / "concepts" / f"{concept.slug}.md"
            stale_file.unlink(missing_ok=True)
            session.delete(concept)
            pruned += 1

        for concept in live:
            write_concept(concept, sorted(set(rows_by_concept[concept.id])))

        write_index(documents, live)
        totals = (ingested, len(documents), len(live), pruned)

    graph = build_graph(write=True)
    pruned_note = f" (pruned {totals[3]} orphaned)" if totals[3] else ""
    print(
        f"\nIngested {totals[0]} document(s). Vault now holds {totals[1]} documents, "
        f"{totals[2]} concepts{pruned_note}.  graph.json: {len(graph['nodes'])} nodes, "
        f"{len(graph['edges'])} edges."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
