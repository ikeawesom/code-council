"""Record/replay layer over the SPRS client.

record: every live response is saved to data/fixtures/<endpoint>/<key>.json
replay: LEX_OFFLINE=1 (or `offline=True` passed explicitly) serves from disk
and never touches the network.

This is the demo's insurance policy against venue wifi and site changes - the
scraper always calls `call()` below rather than `httpx` directly, so every
Hansard endpoint is replayable offline with no code changes at the call site.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.scraper.sprs_client import BASE_URL, HEADERS


class FixtureMissing(RuntimeError):
    """Raised in offline mode when no recorded response exists for a call."""


def fixture_path(endpoint: str, key: str) -> Path:
    """Where a fixture for `endpoint`/`key` lives on disk."""
    return settings.fixtures_dir / endpoint / f"{key}.json"


def load_fixture(endpoint: str, key: str) -> Any | None:
    """Read a recorded fixture, or None if it does not exist."""
    path = fixture_path(endpoint, key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_fixture(endpoint: str, key: str, payload: Any) -> Path:
    """Write `payload` as the fixture for `endpoint`/`key`, creating dirs as needed."""
    path = fixture_path(endpoint, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def call(endpoint: str, key: str, body: dict, *, offline: bool | None = None) -> Any:
    """Post `body` to `endpoint`, replaying/recording via the fixture cache.

    Offline (settings.offline when `offline` is not given): return the recorded
    fixture, or raise FixtureMissing - the network is never touched.

    Online: POST to SPRS, decode as UTF-8 (see sprs_client's Windows-codec
    gotcha), record the response, and return it. Every network response is
    re-recorded even when a fixture already exists, per the standing rule that
    every network response is recorded.
    """
    if offline is None:
        offline = settings.offline
    if offline:
        payload = load_fixture(endpoint, key)
        if payload is None:
            raise FixtureMissing(f"{endpoint}/{key}")
        return payload

    resp = httpx.post(f"{BASE_URL}/{endpoint}", json=body, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    payload = json.loads(resp.content.decode("utf-8"))
    save_fixture(endpoint, key, payload)
    return payload


def list_report_fixtures() -> list[str]:
    """ISO "YYYY-MM-DD" for every recorded getHansardReport fixture, newest first."""
    directory = settings.fixtures_dir / "getHansardReport"
    if not directory.exists():
        return []
    dates: list[str] = []
    for path in directory.glob("*.json"):
        day, month, year = path.stem.split("-")
        dates.append(f"{year}-{month}-{day}")
    return sorted(dates, reverse=True)
