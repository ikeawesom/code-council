"""Read vault markdown back into structured objects (python-frontmatter).

Round-trips what `writer.py` produces. The anchor is always parsed from the
`<!-- anchor: ... -->` comment, never from the heading text (§3). The heading
line itself (`## <n> <heading>`) is split back into `number`/`heading` using
the same convention the writer uses to build it: if the first
whitespace-delimited token starts with a digit, it is the clause number and
the rest is the heading; otherwise the whole line is the heading and the
number is empty. This is a documented convention of this module, not part of
the frozen anchor scheme.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

import frontmatter

from app.config import settings

_ANCHOR_RE = re.compile(r"<!--\s*anchor:\s*(?P<anchor>[a-z0-9-]+)\s*-->")
_CONCEPT_LINK_RE = re.compile(r"\[\[([^|\]]+)\|")
_CLAUSE_HEADING_RE = re.compile(r"(?m)^## (.*)$")


def _split_heading(heading_line: str) -> tuple[str, str]:
    heading_line = heading_line.strip()
    if not heading_line:
        return "", ""
    first, _, rest = heading_line.partition(" ")
    if first and first[0].isdigit():
        return first, rest.strip()
    return "", heading_line


def _parse_clauses(content: str) -> list[dict]:
    parts = _CLAUSE_HEADING_RE.split(content)
    clauses: list[dict] = []
    # parts[0] is the preamble (the `# Title` line); clauses alternate
    # heading/body starting at index 1.
    for i in range(1, len(parts), 2):
        heading_line = parts[i]
        block = parts[i + 1] if i + 1 < len(parts) else ""

        anchor_match = _ANCHOR_RE.search(block)
        anchor = anchor_match.group("anchor") if anchor_match else ""
        remaining = _ANCHOR_RE.sub("", block, count=1)

        lines = remaining.split("\n")
        while lines and lines[0].strip() == "":
            lines.pop(0)
        while lines and lines[-1].strip() == "":
            lines.pop()

        concepts: list[str] = []
        if lines and lines[-1].strip().startswith("**Concepts:**"):
            concept_line = lines.pop()
            concepts = _CONCEPT_LINK_RE.findall(concept_line)
            while lines and lines[-1].strip() == "":
                lines.pop()

        text = "\n".join(lines).strip()
        number, heading = _split_heading(heading_line)
        clauses.append(
            {
                "anchor": anchor,
                "number": number,
                "heading": heading,
                "text": text,
                "concepts": concepts,
            }
        )
    return clauses


def read_document(slug: str) -> tuple[dict, list[dict]]:
    """Read `vault/documents/<slug>.md` -> (frontmatter, clauses)."""
    path = settings.vault_dir / "documents" / f"{slug}.md"
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    return dict(post.metadata), _parse_clauses(post.content)


def iter_documents() -> Iterator[tuple[dict, list[dict]]]:
    """Yield (frontmatter, clauses) for every document in the vault, sorted by slug."""
    doc_dir = settings.vault_dir / "documents"
    if not doc_dir.exists():
        return
    for path in sorted(doc_dir.glob("*.md")):
        yield read_document(path.stem)


def read_clause(ref: str) -> dict | None:
    """Look up one clause by `<doc-slug>#<anchor>`. `None` if not found."""
    if "#" not in ref:
        return None
    doc_slug, anchor = ref.split("#", 1)
    path = settings.vault_dir / "documents" / f"{doc_slug}.md"
    if not path.exists():
        return None
    _, clauses = read_document(doc_slug)
    for clause in clauses:
        if clause["anchor"] == anchor:
            return clause
    return None
