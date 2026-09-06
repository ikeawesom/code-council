"""Smoke tests for the M4 routers (tasks/proposals/documents/notifications/
parliament/users), plus one real test that approve rewrites the vault markdown
and fans out notifications.

Everything runs against an in-memory sqlite engine (monkeypatched onto
`app.db.engine`) and a tmp_path vault/fixtures dir - never the real
`data/app.db` or `vault/`.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import db as app_db
from app.config import settings
from app.main import app
from app.models import (
    Clause,
    Document,
    DocumentUser,
    ParliamentItem,
    Proposal,
    Task,
    TaskDocument,
    User,
)
from app.vault import reader, writer


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
        user1 = User(name="John Goh", email="john@codecouncil.demo", initials="JG")
        user2 = User(name="Marcus Ong", email="marcus@codecouncil.demo", initials="MO")
        session.add_all([user1, user2])
        session.flush()

        doc = Document(
            slug="lease", title="Warehouse Lease", sector="real-estate",
            version=1, clause_count=1,
        )
        session.add(doc)
        session.flush()

        clause = Clause(
            document_id=doc.id, anchor="7-2", ref="lease#7-2", number="7.2",
            heading="Notice Period", text="one month notice", order_index=0,
        )
        session.add(clause)
        session.add_all(
            [
                DocumentUser(document_id=doc.id, user_id=user1.id),
                DocumentUser(document_id=doc.id, user_id=user2.id),
            ]
        )

        item = ParliamentItem(
            sprs_id="demo-x", slug="x", title="Bill X", sitting_date="2026-08-05",
            item_type="bill", legislation_type="amendment", speaker="Minister X",
            url="https://example.com", summary="summary text",
        )
        session.add(item)
        session.flush()

        task = Task(
            parliament_item_id=item.id, reference="CC-2026-0001", status="new",
            severity="high", document_count=1, assignee_id=user1.id,
        )
        session.add(task)
        session.flush()

        task_doc = TaskDocument(
            task_id=task.id, document_id=doc.id, review_state="pending",
            severity="high", proposal_count=1,
        )
        session.add(task_doc)
        session.flush()

        proposal = Proposal(
            task_document_id=task_doc.id, clause_id=clause.id, clause_ref=clause.ref,
            impacted=True, severity="high", rationale="parliament changed notice periods",
            suggested_text="three months notice", status="pending",
        )
        session.add(proposal)
        session.commit()

        writer.write_document(doc, [clause], {})

        fixtures_dir = settings.fixtures_dir / "getHansardReport"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        (fixtures_dir / "05-08-2026.json").write_text(
            json.dumps(
                {
                    "metadata": {
                        "parlimentNO": 15,
                        "sessionNO": 1,
                        "volumeNO": 96,
                        "sittingNO": 34,
                        "sittingDate": "05-08-2026",
                    },
                    "takesSectionVOList": [],
                }
            ),
            encoding="utf-8",
        )

    with TestClient(app) as c:
        yield c


# --- tasks -----------------------------------------------------------------


def test_list_tasks_and_filters(client):
    body = client.get("/api/tasks").json()
    assert len(body["tasks"]) == 1
    task = body["tasks"][0]
    assert task["reference"] == "CC-2026-0001"
    assert task["severity"] == "high"
    assert task["proposal_count"] == 1
    assert task["assignee"]["name"] == "John Goh"
    assert task["is_demo"] is True
    assert task["item"]["title"] == "Bill X"

    assert client.get("/api/tasks", params={"status": "approved"}).json()["tasks"] == []
    assert len(client.get("/api/tasks", params={"sector": "real-estate"}).json()["tasks"]) == 1
    assert client.get("/api/tasks", params={"sector": "general"}).json()["tasks"] == []


def test_get_task_and_task_document(client):
    body = client.get("/api/tasks/1").json()
    assert body["reference"] == "CC-2026-0001"
    assert len(body["documents"]) == 1
    assert body["documents"][0]["slug"] == "lease"
    assert body["documents"][0]["preview"]["clause_ref"] == "lease#7-2"

    body2 = client.get("/api/tasks/1/documents/lease").json()
    assert body2["task"]["reference"] == "CC-2026-0001"
    assert body2["document"]["slug"] == "lease"
    assert len(body2["proposals"]) == 1
    assert body2["proposals"][0]["clause"]["text"] == "one month notice"
    assert any(op == "insert" for op, _ in body2["proposals"][0]["diff"])

    assert client.get("/api/tasks/999").status_code == 404
    assert client.get("/api/tasks/1/documents/no-such-doc").status_code == 404


# --- proposals ---------------------------------------------------------------


def test_reject_proposal_only_sets_status(client):
    resp = client.post("/api/proposals/1/reject", json={"user_id": 1})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert client.get("/api/documents/lease").json()["version"] == 1


def test_approve_proposal_rewrites_vault_and_notifies(client):
    resp = client.post("/api/proposals/1/approve", json={"user_id": 1})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # the vault markdown was actually rewritten via the shared writer
    clause = reader.read_clause("lease#7-2")
    assert clause is not None
    assert clause["text"] == "three months notice"

    doc = client.get("/api/documents/lease").json()
    assert doc["version"] == 2
    assert len(doc["history"]) == 1
    assert doc["history"][0]["after_text"] == "three months notice"

    # both users linked via DocumentUser were notified
    notif1 = client.get("/api/notifications", params={"user_id": 1}).json()
    notif2 = client.get("/api/notifications", params={"user_id": 2}).json()
    assert notif1["unread"] == 1
    assert notif2["unread"] == 1

    nid = notif1["notifications"][0]["id"]
    assert client.post(f"/api/notifications/{nid}/read").status_code == 200
    assert client.get("/api/notifications", params={"user_id": 1}).json()["unread"] == 0


# --- task roll-up (approve/reject propagating to TaskDocument/Task) --------


@pytest.fixture
def rollup_client(tmp_path, monkeypatch):
    """A second, independent app+db: one task with two proposals (for the
    progressive approve roll-up) and one task with a single proposal (for the
    reject-only roll-up). Separate from `client` so the shared fixture's
    single-proposal task keeps asserting `proposal_count == 1` etc. undisturbed.
    """
    monkeypatch.setattr(settings, "vault_dir", tmp_path / "vault")
    monkeypatch.setattr(settings, "fixtures_dir", tmp_path / "fixtures")
    monkeypatch.setattr(settings, "scheduler_enabled", False)

    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(app_db, "engine", test_engine)

    with Session(test_engine) as session:
        user1 = User(name="John Goh", email="john@codecouncil.demo", initials="JG")
        session.add(user1)
        session.flush()

        # Task A: two proposals under one task document, both pending at first.
        doc_a = Document(
            slug="lease-a", title="Lease A", sector="real-estate", version=1, clause_count=2,
        )
        session.add(doc_a)
        session.flush()

        clause_a1 = Clause(
            document_id=doc_a.id, anchor="1", ref="lease-a#1", number="1",
            heading="Clause 1", text="original one", order_index=0,
        )
        clause_a2 = Clause(
            document_id=doc_a.id, anchor="2", ref="lease-a#2", number="2",
            heading="Clause 2", text="original two", order_index=1,
        )
        session.add_all([clause_a1, clause_a2])
        session.flush()

        item_a = ParliamentItem(
            sprs_id="demo-a", slug="a", title="Bill A", sitting_date="2026-08-05",
            item_type="bill", legislation_type="amendment", speaker="Minister A",
            url="https://example.com", summary="summary a",
        )
        session.add(item_a)
        session.flush()

        task_a = Task(
            parliament_item_id=item_a.id, reference="CC-2026-0100", status="new",
            severity="high", document_count=1, assignee_id=user1.id,
        )
        session.add(task_a)
        session.flush()

        task_doc_a = TaskDocument(
            task_id=task_a.id, document_id=doc_a.id, review_state="pending",
            severity="high", proposal_count=2,
        )
        session.add(task_doc_a)
        session.flush()

        proposal_a1 = Proposal(
            task_document_id=task_doc_a.id, clause_id=clause_a1.id, clause_ref=clause_a1.ref,
            impacted=True, severity="high", rationale="r1", suggested_text="new one",
            status="pending",
        )
        proposal_a2 = Proposal(
            task_document_id=task_doc_a.id, clause_id=clause_a2.id, clause_ref=clause_a2.ref,
            impacted=True, severity="high", rationale="r2", suggested_text="new two",
            status="pending",
        )
        session.add_all([proposal_a1, proposal_a2])

        # Task B: a single proposal, for the reject-only -> dismissed path.
        doc_b = Document(
            slug="lease-b", title="Lease B", sector="real-estate", version=1, clause_count=1,
        )
        session.add(doc_b)
        session.flush()

        clause_b1 = Clause(
            document_id=doc_b.id, anchor="1", ref="lease-b#1", number="1",
            heading="Clause 1", text="original b", order_index=0,
        )
        session.add(clause_b1)
        session.flush()

        item_b = ParliamentItem(
            sprs_id="demo-b", slug="b", title="Bill B", sitting_date="2026-08-05",
            item_type="bill", legislation_type="amendment", speaker="Minister B",
            url="https://example.com", summary="summary b",
        )
        session.add(item_b)
        session.flush()

        task_b = Task(
            parliament_item_id=item_b.id, reference="CC-2026-0101", status="new",
            severity="low", document_count=1, assignee_id=user1.id,
        )
        session.add(task_b)
        session.flush()

        task_doc_b = TaskDocument(
            task_id=task_b.id, document_id=doc_b.id, review_state="pending",
            severity="low", proposal_count=1,
        )
        session.add(task_doc_b)
        session.flush()

        proposal_b1 = Proposal(
            task_document_id=task_doc_b.id, clause_id=clause_b1.id, clause_ref=clause_b1.ref,
            impacted=True, severity="low", rationale="r3", suggested_text="new b",
            status="pending",
        )
        session.add(proposal_b1)
        session.commit()

        fixtures_dir = settings.fixtures_dir / "getHansardReport"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        (fixtures_dir / "05-08-2026.json").write_text(
            json.dumps(
                {
                    "metadata": {
                        "parlimentNO": 15, "sessionNO": 1, "volumeNO": 96,
                        "sittingNO": 34, "sittingDate": "05-08-2026",
                    },
                    "takesSectionVOList": [],
                }
            ),
            encoding="utf-8",
        )

    with TestClient(app) as c:
        yield c


def test_approve_one_of_two_sets_task_in_progress(rollup_client):
    resp = rollup_client.post("/api/proposals/1/approve", json={"user_id": 1})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    task = rollup_client.get("/api/tasks/1").json()
    assert task["status"] == "in_progress"
    assert task["documents"][0]["review_state"] == "pending"


def test_approve_second_of_two_sets_task_approved(rollup_client):
    rollup_client.post("/api/proposals/1/approve", json={"user_id": 1})
    resp = rollup_client.post("/api/proposals/2/approve", json={"user_id": 1})
    assert resp.status_code == 200

    task = rollup_client.get("/api/tasks/1").json()
    assert task["status"] == "approved"
    assert task["documents"][0]["review_state"] == "reviewed"


def test_reject_only_proposal_sets_task_dismissed(rollup_client):
    resp = rollup_client.post("/api/proposals/3/reject", json={"user_id": 1})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    task = rollup_client.get("/api/tasks/2").json()
    assert task["status"] == "dismissed"
    assert task["documents"][0]["review_state"] == "reviewed"


# --- documents -----------------------------------------------------------------


def test_documents_list_and_detail(client):
    body = client.get("/api/documents").json()
    assert body["sectors"][0]["sector"] == "real-estate"
    assert body["sectors"][0]["documents"][0]["slug"] == "lease"

    detail = client.get("/api/documents/lease").json()
    assert detail["clauses"][0]["heading"] == "Notice Period"
    assert client.get("/api/documents/no-such-doc").status_code == 404


# --- parliament + users -----------------------------------------------------------------


def test_parliament_and_users(client):
    body = client.get("/api/parliament").json()
    assert body["sitting"]["parliament_no"] == 15
    assert len(body["items"]) == 1
    assert body["items"][0]["task_reference"] == "CC-2026-0001"

    users = client.get("/api/users").json()["users"]
    assert {u["name"] for u in users} == {"John Goh", "Marcus Ong"}
