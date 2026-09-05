"""The 07:00 pipeline, runnable by hand (this is what the demo invokes).

    python scripts/run_daily.py [--date YYYY-MM-DD ...] [--offline] [--lookback N] [--force]

scrape -> normalize into vault/parliament/ -> retrieve candidate clauses ->
LLM impact assessment -> write proposals. Prints a summary of the scrape step;
the retrieve/judge/propose steps land in M3.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.db import init_db  # noqa: E402
from app.scraper.daily import run_scrape  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily Hansard scrape.")
    parser.add_argument(
        "--date",
        dest="dates",
        action="append",
        default=None,
        metavar="YYYY-MM-DD",
        help="a specific sitting date to process (repeatable); default: auto-discover",
    )
    parser.add_argument(
        "--offline", action="store_true", help="replay from data/fixtures, never touch network"
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=None,
        metavar="N",
        help="days to look back when auto-discovering dates (default: settings value)",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-process dates already ingested"
    )
    args = parser.parse_args()

    init_db()
    summary = run_scrape(
        dates=args.dates,
        lookback_days=args.lookback,
        offline=args.offline or None,
        force=args.force,
    )

    print(f"offline: {summary.offline}")
    print(f"dates processed: {summary.dates}")
    print(f"dates skipped:   {summary.skipped}")
    print(f"created: {summary.created}   updated: {summary.updated}")

    # TODO(M3): retrieve -> judge -> propose runs here

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
