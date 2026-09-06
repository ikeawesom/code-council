"""GET /api/tasks `sectors` field: a task spanning two documents in the same
sector must report that sector once, and `?sector=` filtering must still work.

Regression test for the sidebar bug where practice-area counts were summed
over documents.open_task_count and double-counted a task touching two
documents in the same sector. See docs/API_CONTRACT.md, 2026-09-05 note.

Runs against an in-memory sqlite engine (monkeypatched onto `app.db.engine`)
and a tmp_path vault dir - never the real `data/app.db` or `vault/`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import db as app_db
from app.config import settings
from app.main import app
from app.models import Document, ParliamentItem, Task, TaskDocument, User


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vault_dir", tmp_path / "vault")
    monkeypatch.setattr(settings, "fixtures_dir", tmp_path / "fixtures")
    monkeypatch.setattr(settings, "scheduler_enabled", False)

    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(app_db, "engine", test_engine)

    with Session(test_engine) as session:
        user = User(name="John Goh", email="john@codecouncil.demo", initials="JG")
        session.add(user)
        session.flush()

        # Two documents, both in energy-and-infrastructure - one task spans both.
        doc_a = Document(
            slug="consultancy-a", title="Consultancy Agreement A",
            sector="energy-and-infrastructure", version=1, clause_count=1,
        )
        doc_b = Document(
            slug="consultancy-b", title="Consultancy Agreement B",
            sector="energy-and-infrastructure", version=1, clause_count=1,
        )
        # A third document in a different sector - a second, separate task.
        doc_c = Document(
            slug="tenancy", title="Tenancy Agreement", sector="real-estate",
            version=1, clause_count=1,
        )
        session.add_all([doc_a, doc_b, doc_c])
        session.flush()

        item1 = ParliamentItem(
            sprs_id="demo-1", slug="item-1", title="Bill 1", sitting_date="2026-08-05",
            item_type="bill", legislation_type="amendment", speaker="Minister X",
            url="https://example.com/1", summary="summary text",
        )
        item2 = ParliamentItem(
            sprs_id="demo-2", slug="item-2", title="Bill 2", sitting_date="2026-08-05",
            item_type="bill", legislation_type="amendment", speaker="Minister Y",
            url="https://example.com/2", summary="summary text",
        )
        session.add_all([item1, item2])
        session.flush()

        task_energy = Task(
            parliament_item_id=item1.id, reference="CC-2026-0001", status="new",
            severity="high", document_count=2, assignee_id=user.id,
        )
        task_realestate = Task(
            parliament_item_id=item2.id, reference="CC-2026-0002", status="new",
            severity="high", document_count=1, assignee_id=user.id,
        )
        session.add_all([task_energy, task_realestate])
        session.flush()

        session.add_all(
            [
                TaskDocument(
                    task_id=task_energy.id, document_id=doc_a.id,
                    review_state="pending", severity="high", proposal_count=1,
                ),
                TaskDocument(
                    task_id=task_energy.id, document_id=doc_b.id,
                    review_state="pending", severity="high", proposal_count=1,
                ),
                TaskDocument(
                    task_id=task_realestate.id, document_id=doc_c.id,
                    review_state="pending", severity="high", proposal_count=1,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as c:
        yield c


def test_sectors_field_dedupes_within_a_task(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    tasks = resp.json()["tasks"]
    by_reference = {t["reference"]: t for t in tasks}

    # The task spanning two documents in the same sector reports that sector once.
    assert by_reference["CC-2026-0001"]["sectors"] == ["energy-and-infrastructure"]
    assert by_reference["CC-2026-0002"]["sectors"] == ["real-estate"]

    # Distinct-task counts per sector must be 1 each, not 2 for the energy task.
    counts: dict[str, int] = {}
    for t in tasks:
        for sector in t["sectors"]:
            counts[sector] = counts.get(sector, 0) + 1
    assert counts == {"energy-and-infrastructure": 1, "real-estate": 1}


def test_sector_filter_still_works(client):
    resp = client.get("/api/tasks", params={"sector": "real-estate"})
    assert resp.status_code == 200
    tasks = resp.json()["tasks"]
    assert [t["reference"] for t in tasks] == ["CC-2026-0002"]

    resp = client.get("/api/tasks", params={"sector": "energy-and-infrastructure"})
    assert resp.status_code == 200
    tasks = resp.json()["tasks"]
    assert [t["reference"] for t in tasks] == ["CC-2026-0001"]
