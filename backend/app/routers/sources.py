"""sources API routes - reference data the dashboard reads but does not edit:
scraped Hansard items and the seeded lawyer list that powers the user switcher.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import ParliamentItem, Task, User
from app.scraper.fixtures import list_report_fixtures, load_fixture
from app.scraper.sprs_client import sprs_from_iso

parliament_router = APIRouter(prefix="/api/parliament", tags=["parliament"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

SessionDep = Annotated[Session, Depends(get_session)]


def _sitting_metadata(sitting_date_iso: str) -> dict | None:
    """Read `metadata` from the recorded `getHansardReport` fixture for a date.

    Never hard-coded: this is the exact payload the scraper saved to
    `data/fixtures/getHansardReport/<dd-mm-yyyy>.json`, or None if that sitting
    was never scraped/recorded.
    """
    payload = load_fixture("getHansardReport", sprs_from_iso(sitting_date_iso))
    if payload is None:
        return None
    meta = payload.get("metadata", {})
    return {
        "parliament_no": meta.get("parlimentNO"),
        "session_no": meta.get("sessionNO"),
        "volume_no": meta.get("volumeNO"),
        "sitting_no": meta.get("sittingNO"),
    }


@parliament_router.get("")
def list_parliament(session: SessionDep, date: str | None = None) -> dict:
    """Scraped Hansard items for one sitting date, plus that sitting's metadata.

    Defaults to the most recently recorded sitting when `date` is omitted.
    """
    if date is None:
        dates = list_report_fixtures()
        date = dates[0] if dates else None

    query = select(ParliamentItem)
    if date is not None:
        query = query.where(ParliamentItem.sitting_date == date)
    items = session.exec(
        query.order_by(ParliamentItem.sitting_date.desc(), ParliamentItem.id)
    ).all()

    tasks_by_item = {t.parliament_item_id: t for t in session.exec(select(Task)).all()}

    payload_items = [
        {
            "id": item.id,
            "title": item.title,
            "sitting_date": item.sitting_date,
            "item_type": item.item_type,
            "legislation_type": item.legislation_type,
            "speaker": item.speaker,
            "url": item.url,
            "summary": item.summary,
            "vault_path": item.vault_path,
            "task_id": getattr(tasks_by_item.get(item.id), "id", None),
            "task_reference": getattr(tasks_by_item.get(item.id), "reference", None),
        }
        for item in items
    ]

    return {
        "items": payload_items,
        "sitting": _sitting_metadata(date) if date is not None else None,
    }


@users_router.get("")
def list_users(session: SessionDep) -> dict:
    """Every seeded demo lawyer - powers the user switcher."""
    users = session.exec(select(User).order_by(User.id)).all()
    return {
        "users": [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "initials": u.initials,
            }
            for u in users
        ]
    }
