"""Build graph.json: document <-> clause <-> concept <-> parliament_item edges.

Concept nodes are the hubs that make retrieval cheap: a parliament item about
"notice period" reaches every clause tagged with that concept without a full scan.

Reads the vault files directly (via `app.vault.reader` for documents/clauses,
and `python-frontmatter` for concept/parliament files, which `reader.py` does
not expose a contract for) - never the database. Rewritten whole every run;
nodes and edges are sorted so the output is stable across runs (only
`generated_at` changes).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from app.config import settings
from app.vault import reader


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_frontmatter(path: Path) -> dict:
    return dict(frontmatter.loads(path.read_text(encoding="utf-8")).metadata)


def _concept_nodes() -> dict[str, dict]:
    nodes: dict[str, dict] = {}
    concept_dir = settings.vault_dir / "concepts"
    if not concept_dir.exists():
        return nodes
    for path in sorted(concept_dir.glob("*.md")):
        fm = _load_frontmatter(path)
        slug = fm.get("slug", path.stem)
        node_id = f"concept:{slug}"
        nodes[node_id] = {"id": node_id, "type": "concept", "label": fm.get("title", slug)}
    return nodes


def _parliament_frontmatter() -> list[dict]:
    parliament_dir = settings.vault_dir / "parliament"
    if not parliament_dir.exists():
        return []
    return [_load_frontmatter(path) for path in sorted(parliament_dir.glob("*.md"))]


def _clause_label(clause: dict) -> str:
    parts = [p for p in (clause["number"], clause["heading"]) if p]
    if parts:
        return " ".join(parts)
    return clause["heading"] or clause["anchor"]


def build_graph(write: bool = True) -> dict:
    """Read the vault and (re)build the graph. Returns the graph dict; writes
    `vault/graph.json` when `write` is True."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    nodes.update(_concept_nodes())

    for fm, clauses in reader.iter_documents():
        doc_slug = fm.get("slug")
        doc_id = f"document:{doc_slug}"
        nodes[doc_id] = {
            "id": doc_id,
            "type": "document",
            "label": fm.get("title", doc_slug),
            "sector": fm.get("sector", ""),
        }
        for clause in clauses:
            clause_id = f"clause:{doc_slug}#{clause['anchor']}"
            nodes[clause_id] = {
                "id": clause_id,
                "type": "clause",
                "label": _clause_label(clause),
                "document": doc_slug,
            }
            edges.append({"source": doc_id, "target": clause_id, "type": "contains"})
            for concept_slug in clause["concepts"]:
                concept_id = f"concept:{concept_slug}"
                nodes.setdefault(
                    concept_id, {"id": concept_id, "type": "concept", "label": concept_slug}
                )
                edges.append({"source": clause_id, "target": concept_id, "type": "tagged"})

    for fm in _parliament_frontmatter():
        slug = fm.get("slug")
        sitting_date = fm.get("sitting_date", "")
        item_id = f"parliament:{sitting_date}-{slug}"
        nodes[item_id] = {
            "id": item_id,
            "type": "parliament_item",
            "label": fm.get("title", slug),
            "sitting_date": sitting_date,
        }
        for concept_slug in fm.get("concepts") or []:
            concept_id = f"concept:{concept_slug}"
            nodes.setdefault(
                concept_id, {"id": concept_id, "type": "concept", "label": concept_slug}
            )
            edges.append({"source": item_id, "target": concept_id, "type": "mentions"})

    sorted_nodes = sorted(nodes.values(), key=lambda n: n["id"])
    sorted_edges = sorted(edges, key=lambda e: (e["source"], e["target"], e["type"]))
    graph = {"generated_at": _now_iso(), "nodes": sorted_nodes, "edges": sorted_edges}

    if write:
        path = settings.vault_dir / "graph.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8", newline="\n")

    return graph
