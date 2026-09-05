"""APScheduler job: scrape Hansard daily at 07:00 Asia/Singapore, then run the
match -> judge -> propose pipeline so proposals are waiting at 08:00.

The same pipeline is callable synchronously via scripts/run_daily.py, which is
what the demo actually invokes.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.scraper.daily import daily_job

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def build_scheduler() -> BackgroundScheduler:
    """Construct (but do not start) the scheduler with the daily-scrape job."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        daily_job,
        trigger=CronTrigger(hour=settings.scrape_cron_hour, minute=0, timezone=settings.timezone),
        id="daily-scrape",
    )
    return scheduler


def start_scheduler() -> BackgroundScheduler | None:
    """Start the module-level scheduler singleton. Idempotent.

    Returns None (and logs) when settings.scheduler_enabled is False.
    """
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("scheduler disabled via settings.scheduler_enabled=False")
        return None
    if _scheduler is not None:
        return _scheduler
    _scheduler = build_scheduler()
    _scheduler.start()
    logger.info(
        "scheduler started: daily-scrape at %02d:00 %s",
        settings.scrape_cron_hour,
        settings.timezone,
    )
    return _scheduler


def stop_scheduler() -> None:
    """Stop the module-level scheduler singleton, if running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
