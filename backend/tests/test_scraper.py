"""Tests for the M2 Hansard scraper (fixtures.py, sprs_client.py, daily.py,
scheduler.py).

Uses the real committed fixtures under data/fixtures/ - they are the whole
point of the record/replay layer - but never touches the network: httpx.post
is monkeypatched wherever an "online" path is exercised, and any test that
records to disk points settings.fixtures_dir at tmp_path first so the real
fixtures are never overwritten.
"""
from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from dataclasses import dataclass

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.scraper import daily, fixtures, sprs_client

# --- sprs_client date helpers ------------------------------------------------


def test_iso_from_sprs_round_trip():
    assert sprs_client.iso_from_sprs("5-8-2026") == "2026-08-05"
    assert sprs_client.iso_from_sprs("05-08-2026") == "2026-08-05"
    assert sprs_client.sprs_from_iso("2026-08-05") == "05-08-2026"
    assert sprs_client.sprs_from_iso(sprs_client.iso_from_sprs("5-8-2026")) == "05-08-2026"


# --- fixtures.py --------------------------------------------------------------


def test_fixture_path_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fixtures_dir", tmp_path)
    path = fixtures.fixture_path("searchResult", "2026-08-01_2026-08-31")
    assert path == tmp_path / "searchResult" / "2026-08-01_2026-08-31.json"


def test_save_load_round_trip_non_ascii(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fixtures_dir", tmp_path)
    payload = {"title": "Café Résumé — dash", "n": 1}
    saved_path = fixtures.save_fixture("getHansardTopic", "unicode-test", payload)
    assert saved_path.exists()
    text = saved_path.read_text(encoding="utf-8")
    assert "Café" in text  # ensure_ascii=False keeps it literal, not é
    loaded = fixtures.load_fixture("getHansardTopic", "unicode-test")
    assert loaded == payload


def test_call_offline_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fixtures_dir", tmp_path)
    with pytest.raises(fixtures.FixtureMissing):
        fixtures.call("searchResult", "nope", {}, offline=True)


def test_call_offline_present_never_calls_httpx(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fixtures_dir", tmp_path)
    fixtures.save_fixture("searchResult", "cached", {"ok": True})

    called = {"hit": False}

    def fake_post(*args, **kwargs):
        called["hit"] = True
        raise AssertionError("network should not be touched in offline mode")

    monkeypatch.setattr(httpx, "post", fake_post)

    result = fixtures.call("searchResult", "cached", {}, offline=True)
    assert result == {"ok": True}
    assert called["hit"] is False


def test_call_online_records_and_decodes_utf8(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fixtures_dir", tmp_path)
    payload = {"title": "Café", "count": 3}

    class FakeResponse:
        def __init__(self, body: dict):
            import json

            self.content = json.dumps(body, ensure_ascii=False).encode("utf-8")

        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url.endswith("/searchResult")
        return FakeResponse(payload)

    monkeypatch.setattr(httpx, "post", fake_post)

    result = fixtures.call("searchResult", "live-test", {"some": "body"}, offline=False)
    assert result == payload

    on_disk = fixtures.load_fixture("searchResult", "live-test")
    assert on_disk == payload
    text = fixtures.fixture_path("searchResult", "live-test").read_text(encoding="utf-8")
    assert "Café" in text


# --- search / list_sitting_dates against real fixtures -----------------------


def test_search_fixture_keys_offline():
    # Page 0 -> the real committed fixture, no suffix.
    page0 = sprs_client.search("2026-08-01", "2026-08-31", 0, offline=True)
    assert isinstance(page0, list)
    assert len(page0) == 20

    # Page 20 -> a suffixed key that was never recorded.
    with pytest.raises(fixtures.FixtureMissing):
        sprs_client.search("2026-08-01", "2026-08-31", 20, offline=True)


def test_list_sitting_dates_offline_stops_on_missing_page():
    dates = sprs_client.list_sitting_dates("2026-08-01", "2026-08-31", offline=True)
    assert dates == ["2026-08-05"]


def test_get_report_offline_real_fixture():
    payload = sprs_client.get_report("2026-08-05", offline=True)
    assert len(payload["takesSectionVOList"]) == 167


def test_list_report_fixtures_real_dir():
    assert fixtures.list_report_fixtures() == ["2026-08-05"]


# --- daily.run_scrape ---------------------------------------------------------


@dataclass
class _FakeItem:
    sitting_date: str
    sprs_id: str
    slug: str = "fake-item"
    title: str = "Fake Item"


def _install_fake_normalize(monkeypatch) -> None:
    """Insert a stub app.scraper.normalize module (the real one is owned by
    another agent and may not exist yet), matching the frozen signatures."""

    def normalize_report(payload: dict) -> list[_FakeItem]:
        iso = sprs_client.iso_from_sprs(payload["metadata"]["sittingDate"])
        return [_FakeItem(sitting_date=iso, sprs_id=f"{iso}-0")]

    def persist_items(session: Session, items: list[_FakeItem]) -> tuple[int, int]:
        from app.models import ParliamentItem

        created = updated = 0
        for item in items:
            existing = session.exec(
                select(ParliamentItem).where(ParliamentItem.sprs_id == item.sprs_id)
            ).first()
            if existing is not None:
                existing.title = item.title
                updated += 1
            else:
                session.add(
                    ParliamentItem(
                        sprs_id=item.sprs_id,
                        slug=item.slug,
                        title=item.title,
                        sitting_date=item.sitting_date,
                    )
                )
                created += 1
        session.flush()
        return created, updated

    module = types.ModuleType("app.scraper.normalize")
    module.normalize_report = normalize_report
    module.persist_items = persist_items
    monkeypatch.setitem(sys.modules, "app.scraper.normalize", module)


@pytest.fixture
def isolated_db(monkeypatch):
    """An in-memory engine swapped in for daily.session_scope, so run_scrape
    tests never touch the real data/app.db."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def fake_session_scope():
        session = Session(engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(daily, "session_scope", fake_session_scope)
    return engine


def test_run_scrape_offline_creates_then_skips_then_forces(monkeypatch, isolated_db):
    _install_fake_normalize(monkeypatch)

    first = daily.run_scrape(dates=["2026-08-05"], offline=True)
    assert first.dates == ["2026-08-05"]
    assert first.skipped == []
    assert first.created == 1
    assert first.updated == 0

    second = daily.run_scrape(dates=["2026-08-05"], offline=True)
    assert second.dates == []
    assert second.skipped == ["2026-08-05"]
    assert second.created == 0
    assert second.updated == 0

    forced = daily.run_scrape(dates=["2026-08-05"], offline=True, force=True)
    assert forced.dates == ["2026-08-05"]
    assert forced.skipped == []
    assert forced.created == 0
    assert forced.updated == 1


def test_run_scrape_offline_missing_report_fixture_is_skipped(monkeypatch, isolated_db):
    _install_fake_normalize(monkeypatch)

    result = daily.run_scrape(dates=["2099-01-01"], offline=True)
    assert result.dates == []
    assert result.skipped == ["2099-01-01"]
    assert result.created == 0


def test_daily_job_swallows_exceptions(monkeypatch, isolated_db):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(daily, "run_scrape", boom)
    daily.daily_job()  # must not raise


# --- scheduler.py --------------------------------------------------------------


def test_build_scheduler_has_daily_scrape_job_at_7am():
    from app.scheduler import build_scheduler

    scheduler = build_scheduler()
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "daily-scrape"

    field_map = {f.name: str(f) for f in job.trigger.fields}
    assert field_map["hour"] == "7"
    assert field_map["minute"] == "0"
