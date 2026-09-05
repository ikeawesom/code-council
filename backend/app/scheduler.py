"""APScheduler job: scrape Hansard daily at 07:00 Asia/Singapore, then run the
match -> judge -> propose pipeline so proposals are waiting at 08:00.

The same pipeline is callable synchronously via scripts/run_daily.py, which is
what the demo actually invokes.
"""
# TODO(M2): CronTrigger(hour=settings.scrape_cron_hour, timezone=settings.timezone)
