"""Golden-file regression tests for the full pipeline.

The golden scenario runs the pipeline for two consecutive days over the
same output directory, exercising multi-day accumulation, append-only
ledger behaviour, badge threshold crossing and leaderboard tie-breaks.
Any intentional business-rule change requires regenerating the golden
files (see docs/testing_and_determinism.md).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gamification_engine.orchestration.pipeline import run_pipeline
from gamification_engine.orchestration.run_context import RunContext

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
GOLDEN_INPUTS = FIXTURES_DIR / "golden_inputs"
GOLDEN_OUTPUTS = FIXTURES_DIR / "golden_outputs"

OUTPUT_FILES = [
    "states.json",
    "rewards.json",
    "ledger.json",
    "badges.json",
    "leaderboard.json",
    "notifications.json",
    "run_summary.json",
]

RUN_DATES = {"day1": date(2026, 3, 8), "day2": date(2026, 3, 9)}


def _normalize(text: str) -> str:
    """Normalize platform line endings for byte-level comparison."""

    return text.replace("\r\n", "\n")


def _run_day(output_dir: Path, run_date: date) -> None:
    ctx = RunContext(
        activities_csv_path=GOLDEN_INPUTS / "user_activities.csv",
        challenges_csv_path=GOLDEN_INPUTS / "challenges.csv",
        output_dir=output_dir,
        run_date=run_date,
    )
    run_pipeline(ctx)


@pytest.fixture(scope="module")
def two_day_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Run the golden scenario once and snapshot outputs per day."""

    work = tmp_path_factory.mktemp("golden_work")
    snapshots: dict[str, Path] = {}

    for day, run_date in RUN_DATES.items():
        _run_day(work, run_date)
        snapshot = tmp_path_factory.mktemp(f"golden_{day}")
        for filename in OUTPUT_FILES:
            (snapshot / filename).write_text(
                (work / filename).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        snapshots[day] = snapshot

    return snapshots


@pytest.mark.parametrize("day", ["day1", "day2"])
@pytest.mark.parametrize("filename", OUTPUT_FILES)
def test_output_matches_golden_file(
    two_day_run: dict[str, Path],
    day: str,
    filename: str,
) -> None:
    """Each pipeline output must match its golden snapshot exactly."""

    actual = _normalize((two_day_run[day] / filename).read_text(encoding="utf-8"))
    expected = _normalize((GOLDEN_OUTPUTS / day / filename).read_text(encoding="utf-8"))

    assert actual == expected, (
        f"{day}/{filename} diverged from the golden file. If the business "
        "rules changed intentionally, regenerate the golden outputs as "
        "described in docs/testing_and_determinism.md."
    )


def test_golden_scenario_covers_key_behaviours(
    two_day_run: dict[str, Path],
) -> None:
    """Sanity-check that the golden scenario keeps exercising the
    behaviours it was designed for (guards against fixture erosion)."""

    import json

    day2 = two_day_run["day2"]

    badges = json.loads((day2 / "badges.json").read_text(encoding="utf-8"))
    assert [b["user_id"] for b in badges] == ["U1"], (
        "Golden scenario must include a badge threshold crossing."
    )

    leaderboard = json.loads((day2 / "leaderboard.json").read_text(encoding="utf-8"))
    tied = [e for e in leaderboard if e["total_points"] == 80]
    assert [e["user_id"] for e in tied] == ["U3", "U4"], (
        "Golden scenario must include an equal-score alphabetical tie-break."
    )

    ledger = json.loads((day2 / "ledger.json").read_text(encoding="utf-8"))
    assert len(ledger) == 6, (
        "Golden scenario must accumulate ledger entries across both days."
    )
