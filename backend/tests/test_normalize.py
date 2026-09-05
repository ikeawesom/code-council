"""Tests for `app/scraper/normalize.py` (M2, docs/VAULT_FORMAT.md §5).

Anything that writes to the vault monkeypatches `settings.vault_dir` to a
temp directory - never the real `vault/`. The real fixture at
`data/fixtures/getHansardReport/05-08-2026.json` is used for the end-to-end
checks so the heuristics are validated against actual Hansard HTML, not just
handcrafted snippets.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.models import LEGISLATION_TYPES, ParliamentItem
from app.scraper import normalize

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import seed_demo  # noqa: E402


@pytest.fixture
def vault(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    monkeypatch.setattr(settings, "vault_dir", vault_root)
    return vault_root


@pytest.fixture
def report_payload():
    path = settings.fixtures_dir / "getHansardReport" / "05-08-2026.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def topic_payload():
    path = settings.fixtures_dir / "getHansardTopic" / "oral-answer-4165.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    return eng


# --- html_to_text ------------------------------------------------------------


def test_html_to_text_paragraphs_and_entities():
    html = (
        "<p>1 <strong>Ms X</strong> asked&nbsp;the Minister.</p>"
        "<h6>12.02 pm</h6>"
        "<p>Second   paragraph   with   spacing.</p>"
    )
    text = normalize.html_to_text(html)
    assert "<" not in text and ">" not in text
    assert "&nbsp;" not in text
    paragraphs = text.split("\n\n")
    assert paragraphs == [
        "1 Ms X asked the Minister.",
        "12.02 pm",
        "Second paragraph with spacing.",
    ]


def test_html_to_text_empty():
    assert normalize.html_to_text("") == ""
    assert normalize.html_to_text("<p>   </p>") == ""


# --- extract_speaker -----------------------------------------------------


def test_extract_speaker_asked_the_minister():
    html = (
        "1 <strong>Ms X</strong> asked&nbsp;the Minister for Education whether "
        "the Ministry intends to review the exam."
    )
    assert normalize.extract_speaker(html) == "Minister for Education"


def test_extract_speaker_strong_fallback():
    html = "<strong>Mr Speaker</strong>: Mr Kenneth Tiong."
    assert normalize.extract_speaker(html) == "Mr Speaker"


def test_extract_speaker_strips_constituency():
    html = "<strong>Mr Kenneth Tiong Boon Kiat (Aljunied)</strong>: Mr Speaker, I move."
    assert normalize.extract_speaker(html) == "Mr Kenneth Tiong Boon Kiat"


def test_extract_speaker_empty():
    assert normalize.extract_speaker("") == ""


# --- classify_legislation_type -----------------------------------------------


def test_classify_bill_title_is_new_legislation():
    assert normalize.classify_legislation_type("Some New Bill", "") == "new_legislation"


def test_classify_amendment_bill_is_amendment():
    assert normalize.classify_legislation_type("Some Act (Amendment) Bill", "") == "amendment"


def test_classify_plain_oral_answer_is_amendment():
    result = normalize.classify_legislation_type("Probe into Exam Incident", "some text")
    assert result == "amendment"


def test_classify_new_framework_in_text_is_new_legislation():
    text = "The Ministry will introduce a new framework for licensing operators."
    assert normalize.classify_legislation_type("Korban Services", text) == "new_legislation"


# --- normalize_report (real fixture) -----------------------------------------


def test_normalize_report_real_fixture(report_payload):
    items = normalize.normalize_report(report_payload)

    assert len(items) >= 160
    assert all(item.sitting_date == "2026-08-05" for item in items)

    sprs_ids = [item.sprs_id for item in items]
    assert len(sprs_ids) == len(set(sprs_ids))

    slugs = [item.slug for item in items]
    assert len(slugs) == len(set(slugs))

    for item in items:
        assert item.legislation_type in LEGISLATION_TYPES
        assert item.title == item.title.strip()
        assert item.title != ""
        assert item.slug != "" and len(item.slug) <= 80
        assert re.fullmatch(r"[a-z0-9-]+", item.slug)
        assert item.item_type in set(normalize.SECTION_TYPE_LABELS.values())

    oa_items = [item for item in items if item.item_type == "oral answer"]
    assert any(
        item.speaker.startswith("Minister") or "Minister" in item.speaker for item in oa_items
    )


def test_normalize_report_slug_dedupe_and_determinism(report_payload):
    items_first = normalize.normalize_report(report_payload)
    items_second = normalize.normalize_report(report_payload)

    assert [i.sprs_id for i in items_first] == [i.sprs_id for i in items_second]
    assert [i.slug for i in items_first] == [i.slug for i in items_second]

    duplicate_title = "An Economy of the Future that Works for All"
    matching = [i for i in items_first if i.title == duplicate_title]
    assert len(matching) >= 2
    slugs = [i.slug for i in matching]
    assert slugs[0] == "an-economy-of-the-future-that-works-for-all"
    assert slugs[1] == "an-economy-of-the-future-that-works-for-all-2"


# --- normalize_topic (real fixture) ------------------------------------------


def test_normalize_topic_real_fixture(topic_payload):
    item = normalize.normalize_topic(topic_payload, "oral-answer-4165#")
    assert item.sprs_id == "oral-answer-4165"
    assert item.item_type == "oral answer"
    assert item.sitting_date == "2026-08-05"
    assert item.body_text != ""
    assert item.title != ""


# --- persist_items ------------------------------------------------------------


def _make_item(sprs_id: str, title: str) -> ParliamentItem:
    return ParliamentItem(
        sprs_id=sprs_id,
        slug=title.lower().replace(" ", "-"),
        title=title,
        sitting_date="2026-08-05",
        item_type="oral answer",
        legislation_type="amendment",
        speaker="Minister for Testing",
        url="",
        summary=title,
        body_text=title,
        vault_path="",
    )


def test_persist_items_create_then_update(vault, engine):
    item1 = _make_item("test-a", "Test Item A")
    item2 = _make_item("test-b", "Test Item B")

    with Session(engine) as session:
        created, updated = normalize.persist_items(session, [item1, item2])
        session.commit()
        assert (created, updated) == (2, 0)

    parliament_dir = vault / "parliament"
    files = sorted(p.name for p in parliament_dir.glob("*.md"))
    assert files == ["2026-08-05-test-item-a.md", "2026-08-05-test-item-b.md"]

    with Session(engine) as session:
        row = session.exec(select(ParliamentItem).where(ParliamentItem.sprs_id == "test-a")).one()
        assert row.vault_path == "vault/parliament/2026-08-05-test-item-a.md"

    item1_renamed = _make_item("test-a", "Renamed Item A")
    item2_renamed = _make_item("test-b", "Renamed Item B")
    with Session(engine) as session:
        created, updated = normalize.persist_items(session, [item1_renamed, item2_renamed])
        session.commit()
        assert (created, updated) == (0, 2)

    content = (parliament_dir / "2026-08-05-renamed-item-a.md").read_text(encoding="utf-8")
    assert "Renamed Item A" in content
    assert "legislation_type: amendment" in content

    # frontmatter key order per docs/VAULT_FORMAT.md §5
    keys = []
    for line in content.splitlines():
        if line == "---" and keys:
            break
        if line == "---":
            continue
        keys.append(line.split(":", 1)[0])
    assert keys == [
        "title",
        "slug",
        "type",
        "sitting_date",
        "sprs_id",
        "item_type",
        "legislation_type",
        "speaker",
        "url",
        "concepts",
    ]


# --- seed_demo ------------------------------------------------------------


def test_seed_demo_idempotent(vault, engine, monkeypatch):
    monkeypatch.setattr(seed_demo, "session_scope", lambda: Session(engine))

    with Session(engine) as session:
        summary1 = seed_demo.run(session, "2026-09-02")
        session.commit()
    assert len(summary1["users"]) == 4
    assert summary1["item_created"] is True

    with Session(engine) as session:
        user_count = len(session.exec(select(seed_demo.User)).all())
    assert user_count == 4

    with Session(engine) as session:
        summary2 = seed_demo.run(session, "2026-09-02")
        session.commit()
    assert summary2["item_created"] is False

    with Session(engine) as session:
        assert len(session.exec(select(seed_demo.User)).all()) == 4
        items = session.exec(
            select(ParliamentItem).where(ParliamentItem.sprs_id == seed_demo.DEMO_SPRS_ID)
        ).all()
        assert len(items) == 1


def test_item_slug_cuts_at_word_boundary():
    from app.scraper.normalize import item_slug

    short = "Residential Tenancies Bill"
    assert item_slug(short) == "residential-tenancies-bill"
    long_title = " ".join(["word"] * 40)  # 199 chars slugified
    slug = item_slug(long_title)
    assert len(slug) <= 80
    assert not slug.endswith("-")
    assert slug.split("-")[-1] == "word"  # never a truncated fragment
    assert item_slug(long_title) == slug  # deterministic
