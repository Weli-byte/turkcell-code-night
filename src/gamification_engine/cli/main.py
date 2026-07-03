"""Command-line entry point for the gamification engine."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from gamification_engine import __version__
from gamification_engine.domain.errors import GamificationEngineError
from gamification_engine.orchestration.pipeline import run_pipeline
from gamification_engine.orchestration.run_context import RunContext


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Exposes the top-level --version flag and the 'run' subcommand for
    orchestrating the batch gamification pipeline.
    """

    parser = argparse.ArgumentParser(
        prog="gamification-engine",
        description="Deterministic gamification engine for video platforms.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the installed package version.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    run_parser = subparsers.add_parser(
        "run",
        help="Run the batch gamification pipeline.",
    )
    run_parser.add_argument(
        "--activities",
        required=True,
        help="Path to the user activities CSV file.",
    )
    run_parser.add_argument(
        "--challenges",
        required=True,
        help="Path to the challenges definition CSV file.",
    )
    run_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write JSON output files to.",
    )
    run_parser.add_argument(
        "--run-date",
        required=True,
        help="Reference date for the batch run (YYYY-MM-DD).",
    )
    run_parser.add_argument(
        "--existing-ledger",
        help="Optional path to existing points ledger JSON file.",
    )
    run_parser.add_argument(
        "--existing-badges",
        help="Optional path to existing badges JSON file.",
    )
    run_parser.add_argument(
        "--existing-notifications",
        help="Optional path to existing notifications JSON file.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument list. When omitted, argparse reads from
            ``sys.argv``.

    Returns:
        Process exit code.
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"gamification-engine {__version__}")
        return 0

    if args.command == "run":
        try:
            run_date = date.fromisoformat(args.run_date)
        except ValueError:
            print(
                f"Error: Invalid run-date '{args.run_date}'. Expected YYYY-MM-DD.",
                file=sys.stderr,
            )
            return 1

        context = RunContext(
            activities_csv_path=Path(args.activities),
            challenges_csv_path=Path(args.challenges),
            output_dir=Path(args.output_dir),
            run_date=run_date,
            existing_ledger_path=(
                Path(args.existing_ledger) if args.existing_ledger else None
            ),
            existing_badges_path=(
                Path(args.existing_badges) if args.existing_badges else None
            ),
            existing_notifications_path=(
                Path(args.existing_notifications)
                if args.existing_notifications
                else None
            ),
        )

        try:
            summary = run_pipeline(context)
            print("Pipeline completed successfully.")
            print(f"Run Date:                  {summary.run_date}")
            print(f"Total Users Processed:     {summary.total_users_processed}")
            print(f"Total Rewards Generated:   {summary.total_rewards_generated}")
            print(f"Total Ledger Entries:      {summary.total_ledger_entries}")
            print(f"Total Badges Assigned:     {summary.total_badges_assigned}")
            print(f"Total Notifications:       {summary.total_notifications_created}")
            print(f"Leaderboard Size:          {summary.leaderboard_size}")
            return 0
        except GamificationEngineError as exc:
            print(f"Pipeline Error: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"Unexpected Error: {exc}", file=sys.stderr)
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
