"""The 07:00 scrape step: pull sitting dates, fetch each report, normalise and
persist. This is the body of the scheduler's daily job, and is also what
scripts/run_daily.py calls before the retrieve -> judge -> propose pipeline
(M3) picks up from the freshly written ParliamentItem rows.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlmodel import select

from app.config import settings
from app.db import session_scope
from app.models import ParliamentItem
from app.scraper.fixtures import FixtureMissing, list_report_fixtures
from app.scraper.sprs_client import get_report, list_sitting_dates

logger = logging.getLogger(__name__)


@dataclass
class ScrapeSummary:
    """What one run_scrape() call did, for logging and the CLI summary."""

    dates: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    created: int = 0
    updated: int = 0
    offline: bool = False


def run_scrape(
    dates: list[str] | None = None,
    *,
    lookback_days: int | None = None,
    offline: bool | None = None,
    force: bool = False,
) -> ScrapeSummary:
    """Fetch and persist Hansard reports for `dates` (ISO), or discover them.

    When `dates` is None: offline mode lists every recorded getHansardReport
    fixture; online mode lists sitting dates over the last `lookback_days` up
    to today. Each date already covered by a ParliamentItem is skipped unless
    `force` is set. A date whose report fixture is missing (offline) is
    recorded in `skipped` rather than raising.
    """
    from app.scraper.normalize import normalize_report, persist_items

    if offline is None:
        offline = settings.offline
    if lookback_days is None:
        lookback_days = settings.scrape_lookback_days

    summary = ScrapeSummary(offline=offline)

    if dates is None:
        if offline:
            dates = list_report_fixtures()
        else:
            today = date.today()
            start = today - timedelta(days=lookback_days)
            dates = list_sitting_dates(start.isoformat(), today.isoformat(), offline=offline)

    for sitting_date in dates:
        with session_scope() as session:
            already = session.exec(
                select(ParliamentItem).where(ParliamentItem.sitting_date == sitting_date)
            ).first()
            if already is not None and not force:
                summary.skipped.append(sitting_date)
                continue

            try:
                payload = get_report(sitting_date, offline=offline)
            except FixtureMissing:
                logger.warning("no fixture for sitting date %s, skipping", sitting_date)
                summary.skipped.append(sitting_date)
                continue

            items = normalize_report(payload)
            created, updated = persist_items(session, items)
            summary.dates.append(sitting_date)
            summary.created += created
            summary.updated += updated

    return summary


def daily_job() -> None:
    """Entry point the scheduler calls at 07:00. Never raises - a bad run must
    not take down the scheduler thread."""
    try:
        summary = run_scrape()
        logger.info(
            "daily scrape done: %d date(s) processed, %d skipped, %d created, %d updated "
            "(offline=%s)",
            len(summary.dates),
            len(summary.skipped),
            summary.created,
            summary.updated,
            summary.offline,
        )
    except Exception:
        logger.exception("daily scrape failed")
