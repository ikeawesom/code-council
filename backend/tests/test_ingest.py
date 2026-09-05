"""Tests for app.ingest.parse and app.ingest.chunk.

Focus: anchor derivation (docs/VAULT_FORMAT.md section 2) since it's an API,
plus the collision-suffix rule and per-document anchor uniqueness.
"""
from __future__ import annotations

from pathlib import Path

from app.ingest.chunk import split_clauses
from app.ingest.parse import Block, ParsedDoc, _is_fill_line, _looks_like_heading, parse_document


def _doc(blocks: list[Block]) -> ParsedDoc:
    return ParsedDoc(title="Test Doc", blocks=blocks, file_type="pdf")


def test_anchor_dotted_number() -> None:
    doc = _doc(
        [
            Block(kind="heading", text="7.2 Notice Period"),
            Block(kind="paragraph", text="Either party may terminate on notice."),
        ]
    )
    clauses = split_clauses(doc, "warehouse-lease")
    assert len(clauses) == 1
    clause = clauses[0]
    assert clause.number == "7.2"
    assert clause.anchor == "7-2"
    assert clause.heading == "Notice Period"
    assert clause.text == "Either party may terminate on notice."


def test_anchor_nested_dotted_number() -> None:
    doc = _doc(
        [Block(kind="heading", text="7.2.1 Sub-clause"), Block(kind="paragraph", text="Body text.")]
    )
    clauses = split_clauses(doc, "warehouse-lease")
    assert clauses[0].number == "7.2.1"
    assert clauses[0].anchor == "7-2-1"


def test_anchor_paren_letter() -> None:
    doc = _doc(
        [Block(kind="heading", text="7(a) Definitions"), Block(kind="paragraph", text="Body text.")]
    )
    clauses = split_clauses(doc, "warehouse-lease")
    assert clauses[0].number == "7(a)"
    assert clauses[0].anchor == "7-a"


def test_anchor_clause_word_prefix() -> None:
    doc = _doc(
        [Block(kind="heading", text="Clause 14 Termination"), Block(kind="paragraph", text="Body.")]
    )
    clauses = split_clauses(doc, "warehouse-lease")
    assert clauses[0].number == "14"
    assert clauses[0].anchor == "14"
    assert clauses[0].heading == "Termination"


def test_anchor_schedule_with_paragraph() -> None:
    doc = _doc(
        [
            Block(kind="heading", text="Schedule 2, para 3 Special Conditions"),
            Block(kind="paragraph", text="Body."),
        ]
    )
    clauses = split_clauses(doc, "warehouse-lease")
    assert clauses[0].anchor == "sch-2-3"


def test_anchor_unnumbered_with_heading() -> None:
    doc = _doc(
        [
            Block(kind="heading", text="CONFIDENTIAL INFORMATION"),
            Block(kind="paragraph", text="Confidential information means..."),
        ]
    )
    clauses = split_clauses(doc, "nda-template")
    assert len(clauses) == 1
    assert clauses[0].number == ""
    assert clauses[0].anchor == "confidential-information"


def test_anchor_unnumbered_with_heading_truncated_to_40_chars() -> None:
    long_heading = "This Is A Very Long Heading That Goes On And On And Well Beyond Forty Chars"
    doc = _doc([Block(kind="heading", text=long_heading), Block(kind="paragraph", text="Body.")])
    clauses = split_clauses(doc, "some-doc")
    assert len(clauses[0].anchor) <= 40


def test_anchor_unnumbered_no_heading_falls_back_to_order_index() -> None:
    # No heading blocks at all - a single, heading-less body of prose.
    body_text = "Just a paragraph with no numbering or heading at all."
    doc = _doc([Block(kind="paragraph", text=body_text)])
    clauses = split_clauses(doc, "some-doc")
    assert len(clauses) == 1
    assert clauses[0].number == ""
    assert clauses[0].heading == ""
    assert clauses[0].anchor == "s0"


def test_collision_suffix_first_occurrence_stays_bare() -> None:
    # Only two repeats: three+ identical headings are treated as running
    # page-header/footer noise (see _REPEATED_HEADING_THRESHOLD in chunk.py)
    # rather than a legitimate recurring section, so this stays below that.
    doc = _doc(
        [
            Block(kind="heading", text="DEFINITIONS"),
            Block(kind="paragraph", text="First occurrence body."),
            Block(kind="heading", text="TERM"),
            Block(kind="paragraph", text="Middle section."),
            Block(kind="heading", text="DEFINITIONS"),
            Block(kind="paragraph", text="Second occurrence body."),
        ]
    )
    clauses = split_clauses(doc, "some-doc")
    anchors = [c.anchor for c in clauses]
    assert anchors == ["definitions", "term", "definitions-2"]


def test_anchors_unique_within_document() -> None:
    doc = _doc(
        [
            Block(kind="heading", text="7.2 Notice Period"),
            Block(kind="paragraph", text="Body one."),
            Block(kind="heading", text="7.2 Notice Period"),
            Block(kind="paragraph", text="Body two - a real re-numbering collision."),
            Block(kind="heading", text="TERM"),
            Block(kind="paragraph", text="Body three."),
        ]
    )
    clauses = split_clauses(doc, "some-doc")
    anchors = [c.anchor for c in clauses]
    assert len(anchors) == len(set(anchors))
    assert anchors == ["7-2", "7-2-2", "term"]


def test_parse_error_yields_no_clauses() -> None:
    doc = ParsedDoc(title="Bad", blocks=[], file_type="doc", parse_error="needs conversion")
    assert split_clauses(doc, "bad-doc") == []


def test_clause_text_is_whitespace_collapsed() -> None:
    doc = _doc(
        [
            Block(kind="heading", text="7.2 Notice Period"),
            Block(kind="paragraph", text="Line one.  "),
            Block(kind="paragraph", text="  Line two with   extra spaces."),
        ]
    )
    clauses = split_clauses(doc, "some-doc")
    assert clauses[0].text == "Line one. Line two with extra spaces."


# --- fill-line / cover-page form-field rule -------------------------------


def test_underscore_run_is_never_a_heading() -> None:
    assert _looks_like_heading("NAME: _________________________________________") is False
    assert _is_fill_line("NAME: _________________________________________") is True


def test_short_underscore_run_below_three_is_not_flagged_as_fill() -> None:
    # Sanity check the threshold itself is "3+", not "any underscore".
    assert _is_fill_line("well__known term") is False


def test_mostly_punctuation_line_is_never_a_heading() -> None:
    assert _looks_like_heading("....................................") is False
    assert _is_fill_line("....................................") is True


def test_genuine_uppercase_heading_still_detected() -> None:
    assert _looks_like_heading("CONFIDENTIAL INFORMATION") is True


def test_fill_line_becomes_body_text_not_a_dropped_heading() -> None:
    doc = _doc(
        [
            Block(kind="heading", text="PARTICULARS"),
            Block(kind="paragraph", text="NAME: ___________________________________"),
            Block(kind="paragraph", text="ADDRESS: ________________________________"),
        ]
    )
    clauses = split_clauses(doc, "some-doc")
    assert len(clauses) == 1
    assert "NAME:" in clauses[0].text
    assert "ADDRESS:" in clauses[0].text


# --- empty-body clauses are folded forward, never emitted -----------------


def test_heading_only_section_folds_into_next_clauses_body() -> None:
    # "Article 1. Definitions" carries no body of its own before the first
    # numbered sub-clause - it must not survive as its own empty clause.
    doc = _doc(
        [
            Block(kind="heading", text="Article 1. Definitions"),
            Block(kind="heading", text="1.1 Definitions"),
            Block(kind="paragraph", text="The terms defined in this Article shall apply."),
        ]
    )
    clauses = split_clauses(doc, "some-doc")
    assert all(c.text for c in clauses)
    assert len(clauses) == 1
    assert clauses[0].anchor == "1-1"
    assert "Article 1. Definitions" in clauses[0].text
    assert "The terms defined" in clauses[0].text


def test_no_empty_text_clauses_survive_even_with_trailing_empty_heading() -> None:
    doc = _doc(
        [
            Block(kind="heading", text="7.2 Notice Period"),
            Block(kind="paragraph", text="Either party may terminate on notice."),
            # A trailing heading-only line with nothing after it to fold into.
            Block(kind="heading", text="SCHEDULE OF PARTIES"),
        ]
    )
    clauses = split_clauses(doc, "some-doc")
    assert all(c.text for c in clauses)
    assert [c.heading for c in clauses] == ["Notice Period"]


# --- filename-derived titles (CONTRACT CHANGE) -----------------------------


def test_title_strips_leading_filename_number(tmp_path: Path) -> None:
    path = tmp_path / "01. Tenancy Agreement (Pte).doc"
    path.write_bytes(b"not a real ole file, just exercising the doc branch")
    parsed = parse_document(path)
    assert parsed.title == "Tenancy Agreement (Pte)"


def test_title_without_leading_number_is_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "NDA template.doc"
    path.write_bytes(b"not a real ole file")
    parsed = parse_document(path)
    assert parsed.title == "NDA template"


def test_titles_distinguish_similarly_named_siblings(tmp_path: Path) -> None:
    a = tmp_path / "04. Option To Purchase (Private Commercial).doc"
    b = tmp_path / "06. Option To Purchase (JTC Industrial).doc"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    title_a = parse_document(a).title
    title_b = parse_document(b).title
    assert title_a != title_b
    assert title_a == "Option To Purchase (Private Commercial)"
    assert title_b == "Option To Purchase (JTC Industrial)"


def test_title_ignores_document_content_uses_filename_only(tmp_path: Path) -> None:
    # An unsupported extension exercises the same title derivation without
    # needing a real parseable PDF/DOCX - title never depends on content.
    path = tmp_path / "01. Some Contract.xyz"
    path.write_bytes(b"whatever content lives in here is irrelevant")
    parsed = parse_document(path)
    assert parsed.title == "Some Contract"
    assert parsed.parse_error is not None
