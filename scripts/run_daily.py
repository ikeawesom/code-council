"""The 07:00 pipeline, runnable by hand (this is what the demo invokes).

    python scripts/run_daily.py [--date YYYY-MM-DD ...] [--offline] [--lookback N] [--force]
                                [--llm mock|claude_cli|local] [--limit N] [--skip-analysis]

scrape -> normalize into vault/parliament/ -> retrieve candidate clauses ->
gate -> LLM impact assessment -> write Task/TaskDocument/Proposal rows.
Prints a summary of each stage. `--offline --llm mock` is the zero-network,
zero-LLM run the stage demo falls back on.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.analysis.pipeline import run_analysis  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import init_db, session_scope  # noqa: E402
from app.llm.base import get_provider  # noqa: E402
from app.scraper.daily import run_scrape  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily Hansard scrape and analysis.")
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
    parser.add_argument(
        "--llm",
        choices=("mock", "claude_cli", "local"),
        default=None,
        help="LLM provider for the judge (default: CC_LLM_PROVIDER)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="max items to judge this run (default: CC_ANALYSIS_MAX_ITEMS)",
    )
    parser.add_argument(
        "--skip-analysis", action="store_true", help="scrape only; do not judge or propose"
    )
    args = parser.parse_args()

    if args.offline:
        # Set before the provider is built so claude_cli refuses to spawn and
        # only ever answers from its cache.
        settings.offline = True

    init_db()
    summary = run_scrape(
        dates=args.dates,
        lookback_days=args.lookback,
        offline=args.offline or None,
        force=args.force,
    )

    print("== scrape ==")
    print(f"offline: {summary.offline}")
    print(f"dates processed: {summary.dates}")
    print(f"dates skipped:   {summary.skipped}")
    print(f"created: {summary.created}   updated: {summary.updated}")

    if args.skip_analysis:
        return 0

    provider = get_provider(args.llm)
    if settings.offline and getattr(provider, "name", "") != "mock":
        # claude_cli/local refuse to spawn offline and can only answer from the
        # response cache. Say so up front: otherwise a cold cache looks like a
        # broken judge rather than a deliberate no-network guard.
        print(
            f"note: --offline with provider {getattr(provider, 'name', '?')} answers from the "
            "LLM cache only; uncached items will fail. Use --llm mock for a cold-cache run."
        )

    with session_scope() as session:
        analysis = run_analysis(session, provider=provider, limit=args.limit)

    print("== analysis ==")
    print(f"provider: {analysis.provider}")
    print(
        f"already tasked: {analysis.already_tasked}   considered: {analysis.considered}   "
        f"gated out: {analysis.gated_out}   over budget: {analysis.over_budget}"
    )
    print(
        f"judged: {analysis.judged}   failures: {analysis.judge_failures}   "
        f"no impact: {analysis.no_impact}"
    )
    print(f"tasks created: {analysis.tasks_created} {analysis.task_references}")
    print(f"proposals created: {analysis.proposals_created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
