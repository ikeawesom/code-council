"""Shared text helpers - FROZEN 2026-09-05 alongside `models.py`.

`slugify` lives here rather than in `ingest/` or `vault/` because both packages
need it and neither owns it. Slugs and anchors are an API (see
`docs/VAULT_FORMAT.md`); changing this function changes every vault filename and
every stored clause ref.
"""
from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 80) -> str:
    """Lowercase ASCII slug: non-alphanumerics collapse to a single hyphen.

    "01. Tenancy Agreement (Pte)" -> "01-tenancy-agreement-pte"
    """
    normalised = unicodedata.normalize("NFKD", text)
    ascii_text = normalised.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALNUM.sub("-", ascii_text).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug


def collapse_whitespace(text: str) -> str:
    """Squash runs of whitespace to single spaces and strip. Keeps clause text
    comparable across re-ingest, which is what makes ingest idempotent."""
    return " ".join(text.split())
