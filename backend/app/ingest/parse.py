"""PDF/DOCX -> plain text with structure hints.

pdfplumber for PDF, python-docx for DOCX. Scanned/image-only PDFs are detected
(no extractable text layer) and reported at ingest rather than silently
producing an empty document - OCR is explicitly out of scope for the demo.

Never raises: any unexpected failure from a parser library is caught and
surfaced as `ParsedDoc.parse_error` instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import docx
import pdfplumber
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.textutil import collapse_whitespace

_UPPER_RATIO_THRESHOLD = 0.7
_MAX_HEADING_LEN = 90

# A short line that opens with a clause-number-shaped token: "7.2", "7(a)",
# "Clause 14", "Schedule 2", "Article 3". Used only as a heading *hint* for
# PDF text - the authoritative number parsing happens in chunk.py.
_HEADING_LEAD_RE = re.compile(
    r"^(clause\s+\d+(\.\d+)*|schedule\s+\d+|article\s+\d+|\d+(\.\d+)*\.?\s|\d+\([a-z0-9]+\))",
    re.IGNORECASE,
)

_STYLE_LEVEL_RE = re.compile(r"heading\s*(\d+)", re.IGNORECASE)

# Cover-page form fields ("NAME: ______", "UEN/FIN No: ______") are laid out
# as short, uppercase-ish lines that would otherwise pass the heading heuristic
# above. A run of 3+ underscores is always a fill line, never a heading; a
# line that is mostly non-alphanumeric filler (underscores, dots, dashes) is
# treated the same way. The text itself is kept - it becomes a paragraph block
# instead - only its heading-ness is rejected.
_FILL_RUN_RE = re.compile(r"_{3,}")
_FILL_ALNUM_RATIO_THRESHOLD = 0.3

# Leading filename numbering kept for slug purposes elsewhere ("01. ", "04 ")
# but stripped from the human-facing title: "01. Tenancy Agreement (Pte)" ->
# "Tenancy Agreement (Pte)".
_LEADING_NUMBER_RE = re.compile(r"^\d+[.\s]+")


@dataclass
class Block:
    kind: str  # "heading" | "paragraph"
    text: str
    level: int = 0  # heading depth if known, else 0


@dataclass
class ParsedDoc:
    title: str  # filename stem, leading "NN." numbering stripped - see _title_from_filename
    blocks: list[Block] = field(default_factory=list)
    file_type: str = ""  # "pdf" | "docx" | "doc" | other extension, no dot
    parse_error: str | None = None


def _is_fill_line(line: str) -> bool:
    """A signature-block/form-field line: mostly underscores, dots or dashes.

    Never a heading, but its content (e.g. "NAME: ____") still matters
    legally and is kept as a paragraph block by the caller.
    """
    if _FILL_RUN_RE.search(line):
        return True
    non_space = [c for c in line if not c.isspace()]
    if not non_space:
        return False
    alnum = sum(1 for c in non_space if c.isalnum())
    return (alnum / len(non_space)) < _FILL_ALNUM_RATIO_THRESHOLD


def _looks_like_heading(line: str) -> bool:
    """Heuristic only - under-detecting is fine, garbage detection is not."""
    if not line or len(line) > _MAX_HEADING_LEN:
        return False
    if _is_fill_line(line):
        return False
    if _HEADING_LEAD_RE.match(line):
        return True
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 3:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio >= _UPPER_RATIO_THRESHOLD


def _title_from_filename(path: Path) -> str:
    """Deterministic title: filename stem, leading 'NN.'/'NN ' stripped.

    Content-derived titles (first heading, docx core title) were dropped -
    they picked up cover-page noise ("BETWEEN") and made same-named siblings
    ("Option To Purchase") indistinguishable. The filename is what a lawyer
    already recognises the document by.
    """
    stem = _LEADING_NUMBER_RE.sub("", path.stem, count=1)
    return collapse_whitespace(stem)


def _docx_heading_level(style_name: str) -> int | None:
    if not style_name:
        return None
    if style_name.strip().lower() == "title":
        return 1
    match = _STYLE_LEVEL_RE.search(style_name)
    if match:
        return int(match.group(1))
    return None


def _iter_docx_body(document):
    """Yield Paragraph/Table objects in true document order (tables included)."""
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


_TABLE_LABEL_MAX_LEN = 60


def _table_row_blocks(table: Table) -> list[Block]:
    """Two-column term-sheet tables ("Term | Description") are common in the
    real inbox documents and carry no Word heading styles at all. Treat a
    short first cell as a heading and the rest of the row as its body, so a
    table-only document still yields clauses at a useful granularity instead
    of one undifferentiated blob."""
    blocks: list[Block] = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        cells = list(dict.fromkeys(c for c in cells if c))  # dedupe merged cells
        if not cells:
            continue
        if len(cells) >= 2 and len(cells[0]) <= _TABLE_LABEL_MAX_LEN:
            blocks.append(Block(kind="heading", text=cells[0]))
            rest = " ".join(cells[1:])
            if rest:
                blocks.append(Block(kind="paragraph", text=rest))
        else:
            blocks.append(Block(kind="paragraph", text=" | ".join(cells)))
    return blocks


def _parse_pdf(path: Path) -> ParsedDoc:
    title = _title_from_filename(path)
    try:
        blocks: list[Block] = []
        any_text = False
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    any_text = True
                for raw_line in page_text.splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    if _looks_like_heading(line):
                        blocks.append(Block(kind="heading", text=line))
                    else:
                        blocks.append(Block(kind="paragraph", text=line))
    except Exception as exc:  # pdfplumber/pdfminer can raise a wide range of types
        return ParsedDoc(
            title=title, blocks=[], file_type="pdf", parse_error=f"Failed to parse PDF: {exc}"
        )

    if not any_text:
        return ParsedDoc(
            title=title,
            blocks=[],
            file_type="pdf",
            parse_error=(
                "No extractable text layer found (likely an image-only/scanned "
                "PDF). OCR is out of scope - re-export the PDF with a text layer."
            ),
        )

    return ParsedDoc(title=title, blocks=blocks, file_type="pdf")


def _parse_docx(path: Path) -> ParsedDoc:
    title = _title_from_filename(path)
    try:
        document = docx.Document(str(path))
        blocks: list[Block] = []
        for item in _iter_docx_body(document):
            if isinstance(item, Paragraph):
                text = item.text.strip()
                if not text:
                    continue
                style_name = item.style.name if item.style is not None else ""
                level = _docx_heading_level(style_name)
                if level is not None:
                    blocks.append(Block(kind="heading", text=text, level=level))
                else:
                    blocks.append(Block(kind="paragraph", text=text))
            else:
                blocks.extend(_table_row_blocks(item))
    except Exception as exc:
        return ParsedDoc(
            title=title, blocks=[], file_type="docx", parse_error=f"Failed to parse DOCX: {exc}"
        )

    if not blocks:
        return ParsedDoc(
            title=title,
            blocks=[],
            file_type="docx",
            parse_error="Document contains no readable paragraph or table text.",
        )
    return ParsedDoc(title=title, blocks=blocks, file_type="docx")


def parse_document(path: Path) -> ParsedDoc:
    path = Path(path)
    suffix = path.suffix.lower().lstrip(".")

    if suffix == "doc":
        return ParsedDoc(
            title=_title_from_filename(path),
            blocks=[],
            file_type="doc",
            parse_error=(
                "Legacy binary .doc format is not supported - convert to .docx "
                "(e.g. via Word or LibreOffice 'Save As') and re-ingest."
            ),
        )

    if suffix == "pdf":
        return _parse_pdf(path)

    if suffix == "docx":
        return _parse_docx(path)

    return ParsedDoc(
        title=_title_from_filename(path),
        blocks=[],
        file_type=suffix or "unknown",
        parse_error=f"Unsupported file type '.{suffix}': no parser registered.",
    )
