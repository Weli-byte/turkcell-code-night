"""Automated determinism guarantees for the full pipeline.

These tests assert the core architectural promise: the same inputs, the
same configuration and the same run date always produce byte-identical
outputs — regardless of input row ordering or how many times the
pipeline is executed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gamification_engine.orchestration.pipeline import run_pipeline
from gamification_engine.orchestration.run_context import RunContext

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
GOLDEN_INPUTS = FIXTURES_DIR / "golden_inputs"

OUTPUT_FILES = [
    "states.json",
    "rewards.json",
    "ledger.json",
    "badges.json",
    "leaderboard.json",
    "notifications.json",
    "run_summary.json",
]

RUN_DATE = date(2026, 3, 9)


def _run(activities: Path, challenges: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = RunContext(
        activities_csv_path=activities,
        challenges_csv_path=challenges,
        output_dir=output_dir,
        run_date=RUN_DATE,
    )
    run_pipeline(ctx)


def _read_outputs(output_dir: Path) -> dict[str, str]:
    return {
        filename: (output_dir / filename).read_text(encoding="utf-8")
        for filename in OUTPUT_FILES
    }


def _permuted_csv(source: Path, target: Path) -> None:
    """Write a copy of ``source`` with its data rows in reversed order."""

    lines = source.read_text(encoding="utf-8").strip().splitlines()
    header, rows = lines[0], lines[1:]
    target.write_text(
        "\n".join([header, *reversed(rows)]) + "\n",
        encoding="utf-8",
    )


def test_two_independent_runs_produce_identical_bytes(tmp_path: Path) -> None:
    """Running the same input twice must yield byte-identical outputs."""

    activities = GOLDEN_INPUTS / "user_activities.csv"
    challenges = GOLDEN_INPUTS / "challenges.csv"

    _run(activities, challenges, tmp_path / "run_a")
    _run(activities, challenges, tmp_path / "run_b")

    assert _read_outputs(tmp_path / "run_a") == _read_outputs(tmp_path / "run_b")


def test_input_row_ordering_does_not_change_outputs(tmp_path: Path) -> None:
    """Shuffled CSV rows must produce the exact same outputs."""

    original_activities = GOLDEN_INPUTS / "user_activities.csv"
    original_challenges = GOLDEN_INPUTS / "challenges.csv"

    shuffled_activities = tmp_path / "activities_reversed.csv"
    shuffled_challenges = tmp_path / "challenges_reversed.csv"
    _permuted_csv(original_activities, shuffled_activities)
    _permuted_csv(original_challenges, shuffled_challenges)

    _run(original_activities, original_challenges, tmp_path / "run_original")
    _run(shuffled_activities, shuffled_challenges, tmp_path / "run_shuffled")

    assert _read_outputs(tmp_path / "run_original") == _read_outputs(
        tmp_path / "run_shuffled"
    )


def test_multi_day_rerun_is_idempotent(tmp_path: Path) -> None:
    """Re-running a past day after a later day must not mutate history."""

    activities = GOLDEN_INPUTS / "user_activities.csv"
    challenges = GOLDEN_INPUTS / "challenges.csv"
    out = tmp_path / "out"
    out.mkdir()

    for run_date in (date(2026, 3, 8), date(2026, 3, 9)):
        ctx = RunContext(
            activities_csv_path=activities,
            challenges_csv_path=challenges,
            output_dir=out,
            run_date=run_date,
        )
        run_pipeline(ctx)

    ledger_after_day2 = (out / "ledger.json").read_text(encoding="utf-8")
    badges_after_day2 = (out / "badges.json").read_text(encoding="utf-8")

    # Replay day 1 on top of the accumulated history: the append-only
    # ledger and the badge duplicate guard must leave history unchanged.
    replay_ctx = RunContext(
        activities_csv_path=activities,
        challenges_csv_path=challenges,
        output_dir=out,
        run_date=date(2026, 3, 8),
    )
    run_pipeline(replay_ctx)

    assert (out / "ledger.json").read_text(encoding="utf-8") == ledger_after_day2
    assert (out / "badges.json").read_text(encoding="utf-8") == badges_after_day2
