"""Command-line entry point for the gamification engine."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from gamification_engine import __version__
from gamification_engine.ai.explanation_engine import explain_user_query
from gamification_engine.badges.badge_repository import (
    load_badge_assignments_json,
)
from gamification_engine.domain.enums import BadgeType, RewardReason
from gamification_engine.domain.errors import GamificationEngineError
from gamification_engine.domain.models import (
    DailyUserState,
    LeaderboardEntry,
    RewardEvent,
)
from gamification_engine.ingestion.csv_loader import (
    load_challenge_definitions_csv,
)
from gamification_engine.ledger.ledger_repository import load_points_ledger_json
from gamification_engine.orchestration.pipeline import run_pipeline
from gamification_engine.orchestration.run_context import RunContext


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Exposes subcommands:
        - run: Orchestrate batch gamification pipeline.
        - explain: Query deterministic AI explanations of user status.
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

    # 1. 'run' subcommand
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

    # 2. 'explain' subcommand
    explain_parser = subparsers.add_parser(
        "explain",
        help="Ask questions about a user's gamification status.",
    )
    explain_parser.add_argument(
        "--user-id",
        required=True,
        help="ID of the user to explain.",
    )
    explain_parser.add_argument(
        "--question",
        required=True,
        help="The question to ask (in Turkish).",
    )
    explain_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory containing the JSON run outputs.",
    )
    explain_parser.add_argument(
        "--challenges",
        required=True,
        help="Path to the challenges definition CSV file.",
    )
    explain_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (default) or 'json'.",
    )

    return parser


def _load_states_json(path: Path) -> list[DailyUserState]:
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [
            DailyUserState(
                user_id=item["user_id"],
                state_date=date.fromisoformat(item["state_date"]),
                watch_minutes_today=item["watch_minutes_today"],
                watch_minutes_7d=item["watch_minutes_7d"],
                episodes_completed_today=item["episodes_completed_today"],
                episodes_completed_7d=item["episodes_completed_7d"],
                unique_genres_today=item["unique_genres_today"],
                watch_party_minutes_today=item["watch_party_minutes_today"],
                ratings_today=item["ratings_today"],
                ratings_7d=item["ratings_7d"],
                watch_streak_days=item["watch_streak_days"],
            )
            for item in data
        ]
    except Exception as exc:
        raise GamificationEngineError(f"Could not load states JSON: {exc}") from exc


def _load_leaderboard_json(path: Path) -> list[LeaderboardEntry]:
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [
            LeaderboardEntry(
                rank=item["rank"],
                user_id=item["user_id"],
                total_points=item["total_points"],
                badges=tuple(BadgeType(b) for b in item.get("badges", ())),
            )
            for item in data
        ]
    except Exception as exc:
        raise GamificationEngineError(
            f"Could not load leaderboard JSON: {exc}"
        ) from exc


def _load_rewards_json(path: Path) -> list[RewardEvent]:
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [
            RewardEvent(
                reward_id=item["reward_id"],
                user_id=item["user_id"],
                challenge_id=item["challenge_id"],
                reward_points=item["reward_points"],
                reward_date=date.fromisoformat(item["reward_date"]),
                reason=RewardReason(item["reason"]),
                suppressed_challenge_ids=tuple(
                    item.get("suppressed_challenge_ids", ())
                ),
            )
            for item in data
        ]
    except Exception as exc:
        raise GamificationEngineError(f"Could not load rewards JSON: {exc}") from exc


def _handle_explain(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)

    try:
        # Load necessary data sources
        states = _load_states_json(out_dir / "states.json")
        ledger = load_points_ledger_json(out_dir / "ledger.json")
        badges = load_badge_assignments_json(out_dir / "badges.json")
        leaderboard = _load_leaderboard_json(out_dir / "leaderboard.json")
        rewards = _load_rewards_json(out_dir / "rewards.json")
        challenges = load_challenge_definitions_csv(args.challenges)

        # Get specific user's state
        user_state = next(
            (s for s in states if s.user_id == args.user_id), None
        )

        response = explain_user_query(
            question=args.question,
            user_id=args.user_id,
            state=user_state,
            ledger_entries=ledger,
            badges=badges,
            leaderboard=leaderboard,
            challenges=challenges,
            rewards=rewards,
        )

        from gamification_engine.ai.llm_client import generate_llm_explanation
        from gamification_engine.domain.models import ExplanationResponse

        llm_answer = generate_llm_explanation(
            question=args.question,
            deterministic_answer=response.answer,
            evidence=response.evidence,
        )

        if llm_answer is not None:
            response = ExplanationResponse(
                user_id=response.user_id,
                question=response.question,
                answer=llm_answer,
                evidence=response.evidence,
            )

        if args.format == "json":
            print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(response.answer)

        return 0

    except Exception as exc:
        print(f"Explain Error: {exc}", file=sys.stderr)
        return 1


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

    if args.command == "explain":
        return _handle_explain(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
