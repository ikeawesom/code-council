"""Hybrid retrieval: BM25 over clause text + concept-tag overlap. The cost filter.

A sitting is ~167 items and the firm has ~300 clauses. Sending every pair to
the judge is the cost problem, so this module does two cheap things first:

1. `ClauseIndex.candidates()` ranks every clause against one parliament item
   (BM25 on clause text, plus a bonus per concept the item and clause share)
   and keeps the top-K. Only those K clauses ever reach the LLM.
2. `passes_gate()` decides whether the item is worth judging at all: if even
   the best candidate scores below `settings.retrieve_min_score`, the item is
   dropped before any model call.

Item concepts are derived without an LLM: the names of the firm's own
concepts (from the `concepts` table) are matched lexically against the item's
title and body, unioned with any `concepts:` already in the item's vault
frontmatter (the planted demo item carries three). See DECISIONS.md.

CONTRACT (frozen for M3; pipeline.py and the tests code against it):
    ClauseIndex.build(session) -> ClauseIndex
    ClauseIndex.candidates(item, k=None) -> list[Candidate]   # sorted, best first
    item_concepts(index, item) -> set[str]                    # concept slugs
    passes_gate(candidates, threshold=None) -> bool
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import frontmatter
from rank_bm25 import BM25Okapi
from sqlmodel import Session, select

from app.config import settings
from app.models import Clause, ClauseConcept, Concept, Document, ParliamentItem

logger = logging.getLogger(__name__)

# Score added per concept the item and the clause share. With the idf cap
# below, a capped term contributes at most ~5 to BM25, so one shared hub
# concept is worth about one strong term match - a tiebreaker, not a trump.
CONCEPT_BONUS = 3.0

# Cap on a term's idf. On a 300-clause corpus a word seen in one clause has
# idf ~5.3 and a single coincidental hit ("clashes", "salary") outscored a
# genuine match on ten ordinary terms. Capping at 2.5 makes every term seen
# in <=25 clauses equal, so the score measures how many of the item's terms a
# clause covers rather than how rare its luckiest one is. Tuned 2026-09-05 on
# the real 5 Aug 2026 sitting; see DECISIONS.md.
IDF_CAP = 2.5

# Concepts attached to fewer clauses than this are the fragmented tail (115 of
# 219 after M1) and never match lexically in item text - "Land Transport
# Authority" on one clause was pulling in every bus-service question.
_MIN_CONCEPT_CLAUSES = 2

_TOKEN_RE = re.compile(r"[a-z]+")

# English stopwords plus the boilerplate that every contract clause and every
# Hansard section contains - words that carry no signal about *which* clause.
STOPWORDS: frozenset[str] = frozenset(
    """
    the and for are but not you all any can had her was one our out has his
    have from this that with they will would there their what which when who
    whom been being were into than then them these those such other some
    more most also only over under upon each may might must does did doing
    should could shall about after before between both during further here
    where why how its itself own same very too just now off per via yes
    cent percent
    party parties agreement clause clauses section sections sub subsection paragraph
    provision provisions hereof herein hereby hereto thereof therein whereas
    pursuant accordance respect thereto including include includes without
    within whether either neither otherwise notwithstanding
    member members minister ministers speaker sir madam house parliament
    government ministry ministries singapore singaporeans bill act acts
    question questions answer answers asked ask reply mrs
    said say says year years time times number numbers new
    """.split()
)

# A concept name is matched lexically in item text only when it is specific
# enough not to fire on ordinary prose: at least two words, or a single word
# of six or more characters. "Rent" would match every housing debate; "Rent
# Review" and "Subletting" would not.
_MIN_SINGLE_WORD_LEN = 6


def tokenize(text: str) -> list[str]:
    """Lowercase alphabetic tokens of length >= 3, stopwords removed."""
    return [
        tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) >= 3 and tok not in STOPWORDS
    ]


@dataclass
class Candidate:
    """One clause ranked against one parliament item."""

    clause: Clause
    document: Document
    score: float  # hybrid score the gate and ordering use
    bm25: float
    concept_overlap: int
    shared_concepts: list[str] = field(default_factory=list)  # concept slugs


@dataclass
class _ConceptPattern:
    slug: str
    regex: re.Pattern[str]


class ClauseIndex:
    """BM25 index over every clause in the database, built once per run."""

    def __init__(
        self,
        clauses: list[Clause],
        documents: dict[int, Document],
        clause_concepts: dict[int, set[str]],
        concept_patterns: list[_ConceptPattern],
    ) -> None:
        self.clauses = clauses
        self.documents = documents
        self.clause_concepts = clause_concepts
        self.concept_patterns = concept_patterns
        self._bm25: BM25Okapi | None = None
        if clauses:
            self._bm25 = BM25Okapi([tokenize(c.text) for c in clauses])
            self._bm25.idf = {tok: min(v, IDF_CAP) for tok, v in self._bm25.idf.items()}

    def __len__(self) -> int:
        return len(self.clauses)

    @classmethod
    def build(cls, session: Session) -> ClauseIndex:
        """Load every readable clause with its document and concept slugs."""
        documents = {
            doc.id: doc
            for doc in session.exec(select(Document)).all()
            if doc.parse_error is None and doc.id is not None
        }
        clauses = [
            clause
            for clause in session.exec(select(Clause).order_by(Clause.ref)).all()
            if clause.document_id in documents and clause.text.strip()
        ]
        concept_slugs = {c.id: c.slug for c in session.exec(select(Concept)).all()}
        clause_concepts: dict[int, set[str]] = {}
        for edge in session.exec(select(ClauseConcept)).all():
            slug = concept_slugs.get(edge.concept_id)
            if slug is None:
                continue
            clause_concepts.setdefault(edge.clause_id, set()).add(slug)

        clause_counts: dict[str, int] = {}
        for slugs in clause_concepts.values():
            for slug in slugs:
                clause_counts[slug] = clause_counts.get(slug, 0) + 1

        patterns: list[_ConceptPattern] = []
        for concept in session.exec(select(Concept).order_by(Concept.slug)).all():
            if clause_counts.get(concept.slug, 0) < _MIN_CONCEPT_CLAUSES:
                continue
            regex = _concept_regex(concept.name)
            if regex is not None:
                patterns.append(_ConceptPattern(concept.slug, regex))

        logger.info(
            "clause index: %d clauses, %d documents, %d matchable concepts",
            len(clauses),
            len(documents),
            len(patterns),
        )
        return cls(clauses, documents, clause_concepts, patterns)

    def candidates(self, item: ParliamentItem, k: int | None = None) -> list[Candidate]:
        """Top-k clauses for `item`, best first. Empty when the corpus is empty."""
        if self._bm25 is None:
            return []
        if k is None:
            k = settings.retrieve_top_k

        query = self._query_terms(item)
        scores = self._bm25.get_scores(query) if query else [0.0] * len(self.clauses)
        concepts = item_concepts(self, item)

        ranked: list[Candidate] = []
        for clause, bm25 in zip(self.clauses, scores, strict=True):
            shared = sorted(concepts & self.clause_concepts.get(clause.id or -1, set()))
            score = float(bm25) + CONCEPT_BONUS * len(shared)
            ranked.append(
                Candidate(
                    clause=clause,
                    document=self.documents[clause.document_id],
                    score=score,
                    bm25=float(bm25),
                    concept_overlap=len(shared),
                    shared_concepts=shared,
                )
            )
        ranked.sort(key=lambda c: (-c.score, c.clause.ref))
        return ranked[:k]


    def _query_terms(self, item: ParliamentItem) -> list[str]:
        """The item's most informative terms: tf in the item x idf in the corpus.

        A Hansard section runs to hundreds of distinct words, and summing BM25
        over all of them rewards length, not relevance - every clause shares
        some common vocabulary with a long enough speech. Keeping only the top
        `settings.retrieve_query_terms` weighted terms bounds the score and
        leaves off-topic items (exam incidents, healthcare) with almost nothing
        the clause corpus has ever seen.
        """
        assert self._bm25 is not None
        body = (item.body_text or item.summary or "")[: settings.retrieve_query_chars]
        counts: dict[str, int] = {}
        for tok in tokenize(f"{item.title}\n{body}"):
            counts[tok] = counts.get(tok, 0) + 1
        idf = self._bm25.idf
        weighted = [
            (counts[tok] * idf.get(tok, 0.0), tok) for tok in counts if idf.get(tok, 0.0) > 0
        ]
        weighted.sort(key=lambda pair: (-pair[0], pair[1]))
        return [tok for _weight, tok in weighted[: settings.retrieve_query_terms]]


def item_concepts(index: ClauseIndex, item: ParliamentItem) -> set[str]:
    """Concept slugs for a parliament item: vault frontmatter + lexical matches."""
    slugs: set[str] = set(_frontmatter_concepts(item))
    haystack = f"{item.title}\n{item.body_text}"
    for pattern in index.concept_patterns:
        if pattern.regex.search(haystack):
            slugs.add(pattern.slug)
    return slugs


def passes_gate(candidates: list[Candidate], threshold: float | None = None) -> bool:
    """True when the best candidate clears `threshold` (default from settings)."""
    if threshold is None:
        threshold = settings.retrieve_min_score
    return bool(candidates) and candidates[0].score >= threshold


def _concept_regex(name: str) -> re.Pattern[str] | None:
    words = re.findall(r"[A-Za-z]+", name.lower())
    if not words:
        return None
    if len(words) == 1 and len(words[0]) < _MIN_SINGLE_WORD_LEN:
        return None
    # Words joined by any whitespace/punctuation run; trailing "s" tolerated so
    # "Notice Period" also matches "notice periods".
    body = r"\W+".join(re.escape(w) for w in words)
    return re.compile(rf"\b{body}s?\b", re.IGNORECASE)


def _frontmatter_concepts(item: ParliamentItem) -> list[str]:
    if not item.vault_path:
        return []
    path = settings.vault_dir.parent / item.vault_path
    if not path.exists():
        return []
    try:
        post = frontmatter.load(path)
    except (OSError, ValueError):
        return []
    concepts = post.get("concepts") or []
    return [c for c in concepts if isinstance(c, str)]
