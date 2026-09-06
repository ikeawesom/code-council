"""SQLModel tables - FROZEN 2026-09-05, the contract every module codes against.

The vault markdown is the source of truth for document *content*; this database
holds state, relations and workflow. Anything here that duplicates vault text
(clause `text`, proposal `suggested_text`) is a cache for querying, and the vault
wins on conflict.

Shape of the workflow, three levels, per DECISIONS.md 2026-09-05:

    ParliamentItem -> Task              one item, one status, one assignee
                        -> TaskDocument     one affected document
                             -> Proposal        one clause redline

Two invariants that must not be broken casually:

* Clause anchors are an API. `Clause.ref` is `<doc-slug>#<anchor>` and must stay
  stable across re-ingest - proposals, edits and graph edges all reference it.
  The practice sector is deliberately NOT part of the anchor, so re-filing a
  document between practice areas never invalidates a proposal.
* `Document.sector` is a plain string taken from the inbox sub-folder name. Never
  an enum, never a fixed list in code.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

# --- vocabularies -----------------------------------------------------------
# Plain strings in the database (SQLite has no enum, and the demo must tolerate
# an unseen value rather than crash). These tuples document the intent and are
# what validation and the UI read.

TASK_STATUSES: tuple[str, ...] = ("new", "in_progress", "approved", "dismissed")

SEVERITIES: tuple[str, ...] = ("high", "medium", "low")
SEVERITY_RANK: dict[str, int] = {"high": 3, "medium": 2, "low": 1}

# Badge 2 of the two-badge set. Set by the scraper's normalise step or the judge,
# never by a user. See DECISIONS.md 2026-09-05.
LEGISLATION_TYPES: tuple[str, ...] = ("amendment", "new_legislation")

REVIEW_STATES: tuple[str, ...] = ("pending", "reviewed")
PROPOSAL_STATUSES: tuple[str, ...] = ("pending", "approved", "rejected")


def _now() -> datetime:
    return datetime.now(UTC)


def max_severity(values: list[str]) -> str:
    """Roll clause severities up to a document or task. Empty -> "low"."""
    if not values:
        return "low"
    return max(values, key=lambda v: SEVERITY_RANK.get(v, 0))


# --- people -----------------------------------------------------------------


class User(SQLModel, table=True):
    """A seeded demo lawyer. No authentication - a switcher picks the active one."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    role: str = "Associate"
    initials: str = ""


class DocumentUser(SQLModel, table=True):
    """Which lawyers are linked to a document - the notification fan-out list."""

    __tablename__ = "document_users"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)


# --- the vault, mirrored ----------------------------------------------------


class Document(SQLModel, table=True):
    """One contract or policy. `slug` is the vault filename stem."""

    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    title: str
    # Plain string from the inbox sub-folder name. Never an enum.
    sector: str = Field(index=True)
    source_path: str = ""
    file_type: str = ""
    version: int = 1
    # Non-null when the parser could not read the file (e.g. legacy binary .doc).
    # Surfaced as plain text in the documents list, not as a badge.
    parse_error: str | None = None
    clause_count: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Clause(SQLModel, table=True):
    """One addressable clause. `ref` is the API: `<doc-slug>#<anchor>`."""

    __tablename__ = "clauses"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    # Anchor within the document, e.g. "7-2". Stable across re-ingest.
    anchor: str = Field(index=True)
    # Fully qualified `<doc-slug>#<anchor>`, e.g. "warehouse-lease#7-2".
    ref: str = Field(index=True, unique=True)
    number: str = ""
    heading: str = ""
    text: str = ""
    order_index: int = 0


class Concept(SQLModel, table=True):
    """A legal concept hub, e.g. "Notice Period". Makes retrieval cheap."""

    __tablename__ = "concepts"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    description: str = ""


class ClauseConcept(SQLModel, table=True):
    """Clause <-> concept edge. The hub that keeps retrieval off a full scan."""

    __tablename__ = "clause_concepts"

    id: int | None = Field(default=None, primary_key=True)
    clause_id: int = Field(foreign_key="clauses.id", index=True)
    concept_id: int = Field(foreign_key="concepts.id", index=True)


class ParliamentItem(SQLModel, table=True):
    """One scraped Hansard item."""

    __tablename__ = "parliament_items"

    id: int | None = Field(default=None, primary_key=True)
    sprs_id: str = Field(index=True, unique=True)
    slug: str = Field(index=True)
    title: str
    sitting_date: str = Field(index=True)  # ISO "YYYY-MM-DD"
    item_type: str = ""  # "oral answer", "bill", "written answer", ...
    # Badge 2. One of LEGISLATION_TYPES; blank only before normalisation.
    legislation_type: str = ""
    speaker: str = ""
    url: str = ""
    summary: str = ""
    body_text: str = ""
    vault_path: str = ""
    created_at: datetime = Field(default_factory=_now)


# --- workflow ---------------------------------------------------------------


class Task(SQLModel, table=True):
    """One parliament item's worth of work: status, assignee, rolled-up severity."""

    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    parliament_item_id: int = Field(foreign_key="parliament_items.id", index=True)
    reference: str = Field(index=True, unique=True)  # e.g. "CC-2026-0007"
    status: str = Field(default="new", index=True)  # one of TASK_STATUSES
    assignee_id: int | None = Field(default=None, foreign_key="users.id")
    # Badge 1. Max severity across this task's proposals; recomputed, never asked for.
    severity: str = "low"
    document_count: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class TaskDocument(SQLModel, table=True):
    """The middle level: one document affected by one task."""

    __tablename__ = "task_documents"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id", index=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    review_state: str = "pending"  # one of REVIEW_STATES
    severity: str = "low"  # max severity of this document's proposals
    proposal_count: int = 0


class Proposal(SQLModel, table=True):
    """One clause redline: the judge's verdict on (parliament item x clause)."""

    __tablename__ = "proposals"

    id: int | None = Field(default=None, primary_key=True)
    task_document_id: int = Field(foreign_key="task_documents.id", index=True)
    clause_id: int = Field(foreign_key="clauses.id", index=True)
    clause_ref: str = Field(index=True)  # denormalised `<doc-slug>#<anchor>`
    impacted: bool = True
    severity: str = "low"
    rationale: str = ""
    suggested_text: str = ""
    status: str = Field(default="pending", index=True)  # one of PROPOSAL_STATUSES
    created_at: datetime = Field(default_factory=_now)


class Edit(SQLModel, table=True):
    """An applied change. Written after the vault markdown is rewritten."""

    __tablename__ = "edits"

    id: int | None = Field(default=None, primary_key=True)
    proposal_id: int | None = Field(default=None, foreign_key="proposals.id", index=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    clause_ref: str = Field(index=True)
    before_text: str = ""
    after_text: str = ""
    user_id: int | None = Field(default=None, foreign_key="users.id")
    version_after: int = 1
    created_at: datetime = Field(default_factory=_now)


class Notification(SQLModel, table=True):
    """Fan-out to the other users linked to an edited document."""

    __tablename__ = "notifications"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    task_id: int | None = Field(default=None, foreign_key="tasks.id")
    document_id: int | None = Field(default=None, foreign_key="documents.id")
    edit_id: int | None = Field(default=None, foreign_key="edits.id")
    message: str = ""
    read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_now)
