"""Seed demo lawyers, document links, and one guaranteed-hit parliament item.

    python scripts/seed_demo.py [--date YYYY-MM-DD]

Real Hansard sittings probably touch none of the firm's documents in any given
week - the dashboard would be empty and the demo would show nothing. This
script plants one fictional Bill (`sprs_id` prefixed `demo-`, per
DECISIONS.md 2026-09-05 "A planted guaranteed-hit parliamentary item") that
provably affects the firm's tenancy/lease clauses, alongside seeding four demo
lawyers and linking them to documents. Idempotent: re-running upserts in place
and creates no duplicate rows.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.db import init_db, session_scope  # noqa: E402
from app.models import Concept, Document, DocumentUser, ParliamentItem, User  # noqa: E402
from app.scraper.normalize import item_slug, persist_items, summarize  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

DEFAULT_SITTING_DATE = "2026-09-02"

# (name, role, initials, email local-part) - Singaporean-plausible demo lawyers.
DEMO_USERS: tuple[tuple[str, str, str, str], ...] = (
    ("Wei Ling Tan", "Partner", "WLT", "wei.ling.tan"),
    ("Marcus Ong", "Senior Associate", "MO", "marcus.ong"),
    ("Priya Nair", "Associate", "PN", "priya.nair"),
    ("Farid Rahman", "Associate", "FR", "farid.rahman"),
)

DEMO_SPRS_ID = "demo-tenancy-notice-period-amendment"
DEMO_TITLE = (
    "Residential and Commercial Tenancies (Notice Periods) (Amendment) Bill - "
    "Second Reading"
)
DEMO_SPEAKER = "Minister for National Development"
# Only concepts this vault actually has get attached, so wikilinks never dangle.
DEMO_CANDIDATE_CONCEPTS: tuple[str, ...] = (
    "notice-period",
    "termination",
    "lease-term",
    "tenancy",
    "renewal",
)

DEMO_BODY_PARAGRAPHS: tuple[str, ...] = (
    "Mr Speaker, I beg to move, \"That the Residential and Commercial Tenancies "
    "(Notice Periods) (Amendment) Bill be now read a second time.\" Under the law "
    "as it stands today, a landlord who wishes to terminate a tenancy, or who does "
    "not wish to renew a lease at its expiry, need only give the tenant one month's "
    "written notice. Members would have heard from constituents, particularly "
    "young families and small business tenants, that one month is simply not "
    "enough time to find alternative premises in the current rental market. This "
    "Bill lengthens that notice period so that tenants are not left scrambling.",
    "Clause 4 is the heart of the Bill. It substitutes 'three months' for 'one "
    "month' wherever a notice period for termination of a tenancy, or for a "
    "landlord declining to renew a lease, is currently prescribed. This applies "
    "uniformly across residential and commercial tenancies alike, so that no "
    "tenant, whether a family in a HDB rental flat or a hawker leasing a stall, is "
    "given less than three months to plan ahead. Clause 5 further requires that "
    "such notice must be given in writing and served in a manner prescribed by "
    "regulations - by registered post, or by electronic means acknowledged by the "
    "tenant - so that a landlord and tenant are never left disputing whether "
    "notice of termination was actually given at all.",
    "I recognise that many landlords and tenants have existing tenancies and "
    "leases already running under the old regime. Clause 7 therefore provides a "
    "six-month transition period from the date of commencement. During those six "
    "months, a tenancy or lease already in force may still be terminated on one "
    "month's notice, as agreed. After the transition period lapses, the three "
    "month statutory notice period applies to every tenancy and lease then "
    "subsisting, including one entered into before this Bill was passed, so that "
    "landlords have fair warning to adjust their practices without being caught "
    "out overnight.",
    "Finally, Clause 9 closes an obvious loophole: a landlord and tenant cannot "
    "simply agree, in the tenancy agreement or lease itself, to a notice period "
    "for termination or non-renewal shorter than the statutory minimum. Any such "
    "contractual notice period that falls short of three months is void, and the "
    "three month notice period prescribed by this Act will apply to that tenancy "
    "automatically. Without this safeguard, a landlord could simply insert a "
    "shorter notice period into every new lease and defeat the purpose of the "
    "amendment entirely.",
    "Sir, this Bill strikes a fair balance. Tenants gain the security of a longer "
    "notice period before termination, giving them real time to search for a new "
    "home or new business premises. Landlords, in turn, gain certainty: a clear, "
    "written notice period that cannot be shortened by contract, and a six-month "
    "runway to bring existing tenancies into line. I beg to move.",
)


def upsert_users(session: Session) -> list[User]:
    """Upsert the four demo lawyers by email. Returns them in `DEMO_USERS` order."""
    users: list[User] = []
    for name, role, initials, local in DEMO_USERS:
        email = f"{local}@lexsentinel.demo"
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(name=name, email=email, role=role, initials=initials)
            session.add(user)
        else:
            user.name = name
            user.role = role
            user.initials = initials
        users.append(user)
    session.flush()
    return users


def link_users_to_documents(session: Session, users: list[User]) -> int:
    """Attach 2 users per document, round-robin, so every lawyer gets documents.

    Skips pairs that already exist, so re-running creates nothing new. Prints a
    warning and does nothing if there are no documents yet.
    """
    documents = list(session.exec(select(Document).order_by(Document.slug)).all())
    if not documents:
        print("Warning: no documents found - run scripts/ingest.py first.")
        return 0
    existing = {(link.document_id, link.user_id) for link in session.exec(select(DocumentUser))}
    created = 0
    for i, doc in enumerate(documents):
        for offset in (0, 1):
            user = users[(i + offset) % len(users)]
            pair = (doc.id, user.id)
            if pair in existing:
                continue
            session.add(DocumentUser(document_id=doc.id, user_id=user.id))
            existing.add(pair)
            created += 1
    session.flush()
    return created


def build_planted_item(sitting_date: str) -> ParliamentItem:
    """The fictional, guaranteed-hit second-reading speech. Not a real Act."""
    body_text = "\n\n".join(DEMO_BODY_PARAGRAPHS)
    return ParliamentItem(
        sprs_id=DEMO_SPRS_ID,
        slug=item_slug(DEMO_TITLE),
        title=DEMO_TITLE,
        sitting_date=sitting_date,
        item_type="bill",
        legislation_type="amendment",
        speaker=DEMO_SPEAKER,
        url="",
        summary=summarize(body_text),
        body_text=body_text,
        vault_path="",
    )


def available_demo_concepts(session: Session) -> list[str]:
    """Subset of `DEMO_CANDIDATE_CONCEPTS` that actually exist, so wikilinks
    in the planted item's vault file never dangle."""
    existing = set(session.exec(select(Concept.slug)).all())
    return [slug for slug in DEMO_CANDIDATE_CONCEPTS if slug in existing]


def seed_planted_item(
    session: Session, sitting_date: str
) -> tuple[ParliamentItem, bool, list[str]]:
    """Persist the planted item. Returns (item, created, concept_slugs).

    `item` is re-read from the database after persisting: on an update,
    `persist_items` writes onto the existing row, not the fresh one built here,
    so the fresh instance's `vault_path` would otherwise stay stale ("").
    """
    item = build_planted_item(sitting_date)
    concepts = available_demo_concepts(session)
    created, _updated = persist_items(session, [item], {item.sprs_id: concepts})
    persisted = session.exec(
        select(ParliamentItem).where(ParliamentItem.sprs_id == item.sprs_id)
    ).one()
    return persisted, bool(created), concepts


def run(session: Session, sitting_date: str) -> dict:
    """Run every seeding step against `session`. Returns a summary dict for `main`."""
    users = upsert_users(session)
    links_created = link_users_to_documents(session, users)
    item, item_created, concepts = seed_planted_item(session, sitting_date)
    return {
        "users": users,
        "links_created": links_created,
        "item": item,
        "item_created": item_created,
        "concepts": concepts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo users and the planted parliament item.")
    parser.add_argument(
        "--date", default=DEFAULT_SITTING_DATE, help="planted item sitting date (ISO)"
    )
    args = parser.parse_args()

    init_db()
    with session_scope() as session:
        summary = run(session, args.date)
        # Read everything the summary needs while the session is still open -
        # session_scope() closes (and expires) it on exit.
        user_emails = [u.email for u in summary["users"]]
        links_created = summary["links_created"]
        item_created = summary["item_created"]
        item_sprs_id = summary["item"].sprs_id
        item_vault_path = summary["item"].vault_path
        concepts = summary["concepts"]

    print(f"Users: {len(user_emails)} ({', '.join(user_emails)})")
    print(f"Document links created: {links_created}")
    status = "created" if item_created else "already present (updated)"
    print(f"Planted item ({item_sprs_id}): {status}")
    print(f"  vault path: {item_vault_path}")
    print(f"  concepts attached: {concepts or '(none matched)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
