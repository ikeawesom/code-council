"""Tests for the M1 vault writer/reader/graph builder (docs/VAULT_FORMAT.md).

All tests write into a temporary vault directory (`settings.vault_dir` is
monkeypatched) - never the real `vault/`.
"""
from __future__ import annotations

import json

import pytest

from app.config import settings
from app.graph import build
from app.models import Clause, Concept, Document
from app.vault import reader, writer


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vault_dir", tmp_path)
    return tmp_path


def _doc(**overrides) -> Document:
    fields = dict(
        slug="warehouse-lease",
        title="Warehouse Lease",
        sector="real-estate",
        source_path="data/inbox/real-estate/warehouse-lease.pdf",
        file_type="pdf",
        version=1,
        parse_error=None,
        clause_count=0,
    )
    fields.update(overrides)
    return Document(**fields)


def _clause(**overrides) -> Clause:
    fields = dict(
        document_id=0,
        anchor="7-2",
        ref="warehouse-lease#7-2",
        number="7.2",
        heading="Notice Period",
        text=(
            "Either party may terminate this Agreement by giving not less than "
            "two (2) months' written notice to the other party."
        ),
        order_index=0,
    )
    fields.update(overrides)
    return Clause(**fields)


def test_write_read_round_trip(vault):
    doc = _doc()
    clause1 = _clause()
    clause2 = _clause(
        anchor="14",
        ref="warehouse-lease#14",
        number="14",
        heading="Termination for Convenience",
        text="Either party may terminate for convenience.",
        order_index=1,
    )
    clause_concepts = {
        clause1.ref: [("notice-period", "Notice Period")],
        clause2.ref: [("notice-period", "Notice Period"), ("termination", "Termination")],
    }
    writer.write_document(doc, [clause2, clause1], clause_concepts)  # out of order on purpose

    fm, clauses = reader.read_document(doc.slug)

    assert fm["slug"] == "warehouse-lease"
    assert fm["title"] == "Warehouse Lease"
    assert fm["sector"] == "real-estate"
    assert fm["parse_error"] is None
    assert fm["clause_count"] == 2
    assert fm["concepts"] == ["notice-period", "termination"]

    assert len(clauses) == 2
    c1, c2 = clauses  # writer sorts by order_index regardless of input order
    assert c1 == {
        "anchor": "7-2",
        "number": "7.2",
        "heading": "Notice Period",
        "text": clause1.text,
        "concepts": ["notice-period"],
    }
    assert c2 == {
        "anchor": "14",
        "number": "14",
        "heading": "Termination for Convenience",
        "text": clause2.text,
        "concepts": ["notice-period", "termination"],
    }

    looked_up = reader.read_clause("warehouse-lease#14")
    assert looked_up is not None
    assert looked_up["heading"] == "Termination for Convenience"
    assert reader.read_clause("warehouse-lease#missing") is None
    assert reader.read_clause("no-such-doc#14") is None
    assert reader.read_clause("no-hash-ref") is None


def test_unnumbered_clause_round_trips_as_heading_only(vault):
    doc = _doc(slug="nda-template", title="NDA Template")
    clause = _clause(
        document_id=0,
        anchor="confidential-information",
        ref="nda-template#confidential-information",
        number="",
        heading="Confidential Information",
        text="Information disclosed under this agreement.",
        order_index=0,
    )
    writer.write_document(doc, [clause], {})

    _, clauses = reader.read_document("nda-template")
    assert len(clauses) == 1
    assert clauses[0]["number"] == ""
    assert clauses[0]["heading"] == "Confidential Information"
    assert clauses[0]["anchor"] == "confidential-information"
    assert clauses[0]["concepts"] == []


def test_parse_error_document_still_written(vault):
    doc = _doc(
        slug="legacy-doc",
        title="Legacy Doc",
        parse_error="unsupported legacy .doc binary format",
        clause_count=0,
    )
    writer.write_document(doc, [], {})

    fm, clauses = reader.read_document("legacy-doc")
    assert fm["parse_error"] == "unsupported legacy .doc binary format"
    assert fm["clause_count"] == 0
    assert clauses == []

    path = settings.vault_dir / "documents" / "legacy-doc.md"
    assert path.exists()
    assert "could not be parsed" in path.read_text(encoding="utf-8")


def test_rewrite_is_identical_except_ingested_at(vault):
    doc = _doc()
    clause = _clause()
    concepts = {clause.ref: [("notice-period", "Notice Period")]}

    path = settings.vault_dir / "documents" / "warehouse-lease.md"

    writer.write_document(doc, [clause], concepts)
    first = path.read_text(encoding="utf-8")
    writer.write_document(doc, [clause], concepts)
    second = path.read_text(encoding="utf-8")

    def strip_ingested_at(text: str) -> str:
        return "\n".join(line for line in text.split("\n") if not line.startswith("ingested_at:"))

    assert strip_ingested_at(first) == strip_ingested_at(second)
    # every line is trimmed and the file ends with exactly one trailing newline
    assert all(line == line.rstrip() for line in first.split("\n"))
    assert first.endswith("\n") and not first.endswith("\n\n")


def test_write_concept(vault):
    concept = Concept(
        slug="notice-period", name="Notice Period", description="Advance warning periods."
    )
    rows = [
        ("warehouse-lease", "14", "Termination for Convenience"),
        ("warehouse-lease", "7-2", "Notice Period"),
    ]
    path = writer.write_concept(concept, rows)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "clause_count: 2" in content
    # rows are sorted deterministically by (doc_slug, anchor) - string-sorted,
    # so "14" comes before "7-2"
    assert content.index("`14`") < content.index("`7-2`")
    assert "[[warehouse-lease]] - `7-2` - Notice Period" in content


def test_write_index_preserves_intro_and_is_idempotent(vault):
    doc = _doc()
    concept = Concept(slug="notice-period", name="Notice Period")

    index_path = writer.write_index([doc], [concept])
    text = index_path.read_text(encoding="utf-8")
    assert "# Knowledge base" in text
    assert "[[warehouse-lease]]" in text
    assert "[[notice-period]]" in text

    # user prose intro survives a rewrite
    custom = text.split("<!-- BEGIN GENERATED")[0] + "extra lawyer note\n"
    stale_block = (
        "<!-- BEGIN GENERATED: documents and concepts (do not edit below) -->\n"
        "stale\n"
        "<!-- END GENERATED -->\n"
    )
    index_path.write_text(custom + stale_block, encoding="utf-8")

    writer.write_index([doc], [concept])
    text2 = index_path.read_text(encoding="utf-8")
    assert "extra lawyer note" in text2
    assert "stale" not in text2
    assert text2.count("<!-- BEGIN GENERATED") == 1
    assert "[[warehouse-lease]]" in text2


def test_build_graph_shape(vault):
    doc = _doc()
    clause = _clause()
    writer.write_document(doc, [clause], {clause.ref: [("notice-period", "Notice Period")]})
    writer.write_concept(
        Concept(slug="notice-period", name="Notice Period"),
        [("warehouse-lease", "7-2", "Notice Period")],
    )

    graph = build.build_graph(write=True)

    assert set(graph.keys()) == {"generated_at", "nodes", "edges"}
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == {
        "document:warehouse-lease",
        "clause:warehouse-lease#7-2",
        "concept:notice-period",
    }

    edges = {(e["source"], e["target"], e["type"]) for e in graph["edges"]}
    assert edges == {
        ("document:warehouse-lease", "clause:warehouse-lease#7-2", "contains"),
        ("clause:warehouse-lease#7-2", "concept:notice-period", "tagged"),
    }
    assert {e["type"] for e in graph["edges"]} <= {"contains", "tagged", "mentions"}

    graph_path = settings.vault_dir / "graph.json"
    assert graph_path.exists()
    on_disk = json.loads(graph_path.read_text(encoding="utf-8"))
    assert on_disk["nodes"] == graph["nodes"]
    assert on_disk["edges"] == graph["edges"]

    # nodes and edges are sorted deterministically
    assert [n["id"] for n in graph["nodes"]] == sorted(n["id"] for n in graph["nodes"])
