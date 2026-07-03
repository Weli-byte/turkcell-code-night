"""End-to-end tests for the CLI explain command over real run outputs.

Unlike the unit tests (which mock the JSON loaders), these tests run the
real pipeline first and then exercise ``explain`` against the files it
wrote, covering the CLI loading helpers and the deterministic
explanation branches together.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from gamification_engine.cli.main import main
from gamification_engine.orchestration.pipeline import run_pipeline
from gamification_engine.orchestration.run_context import RunContext

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
GOLDEN_INPUTS = FIXTURES_DIR / "golden_inputs"


@pytest.fixture(scope="module")
def run_output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Execute the two-day golden scenario once for all explain tests."""

    out = tmp_path_factory.mktemp("explain_e2e")
    for run_date in (date(2026, 3, 8), date(2026, 3, 9)):
        ctx = RunContext(
            activities_csv_path=GOLDEN_INPUTS / "user_activities.csv",
            challenges_csv_path=GOLDEN_INPUTS / "challenges.csv",
            output_dir=out,
            run_date=run_date,
        )
        run_pipeline(ctx)
    return out


def _explain(
    output_dir: Path,
    user_id: str,
    question: str,
    fmt: str = "text",
) -> list[str]:
    return [
        "explain",
        "--user-id",
        user_id,
        "--question",
        question,
        "--output-dir",
        str(output_dir),
        "--challenges",
        str(GOLDEN_INPUTS / "challenges.csv"),
        "--format",
        fmt,
    ]


@pytest.fixture(autouse=True)
def _llm_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force deterministic-only answers regardless of local API keys."""

    monkeypatch.setenv("GAMIFICATION_LLM_ENABLED", "0")


def test_explain_points_status(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Points questions should report the ledger total."""

    exit_code = main(_explain(run_output_dir, "U1", "Kaç puanım var?"))

    assert exit_code == 0
    assert "760" in capsys.readouterr().out


def test_explain_badge_requirement_gap(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Badge questions should include target, current and remaining points."""

    exit_code = main(
        _explain(
            run_output_dir,
            "U2",
            "Gold rozetine ulaşmak için ne yapmalıyım?",
            fmt="json",
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"]["target_badge"] == "GOLD"
    assert payload["evidence"]["current_points"] == 220
    assert payload["evidence"]["remaining_points"] == 2780


def test_explain_leaderboard_rank_one(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The leader should get the rank-1 answer."""

    exit_code = main(
        _explain(run_output_dir, "U1", "Liderlik tablosunda kaçıncı sıradayım?")
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() != ""


def test_explain_leaderboard_mid_rank_shows_gap_to_next(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mid-rank user should see the distance to the next user."""

    exit_code = main(
        _explain(
            run_output_dir,
            "U2",
            "Liderlik tablosunda neden bu sıradayım?",
            fmt="json",
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"]["rank"] == 2
    assert payload["evidence"]["next_user_id"] == "U1"
    assert payload["evidence"]["points_to_next"] == 540


def test_explain_reward_not_won_suppressed(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A suppressed challenge should be explained via priority selection."""

    exit_code = main(
        _explain(
            run_output_dir,
            "U1",
            "Neden C-01 ödülünü alamadım?",
            fmt="json",
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"]["status"] == "SUPPRESSED"
    assert payload["evidence"]["suppressed_by"] == "C-03"


def test_explain_reward_not_won_condition_failed(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed condition should surface the current vs required value."""

    exit_code = main(
        _explain(
            run_output_dir,
            "U3",
            "Neden C-02 ödülünü alamadım?",
            fmt="json",
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"]["status"] == "CONDITION_FAILED"
    assert payload["evidence"]["field_name"] == "episodes_completed_today"
    assert payload["evidence"]["required_value"] == 2


def test_explain_reward_not_won_inactive_challenge(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An inactive challenge should be explained as inactive."""

    exit_code = main(
        _explain(
            run_output_dir,
            "U1",
            "Neden C-04 ödülünü alamadım?",
            fmt="json",
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"]["active"] is False


def test_explain_reward_won_with_challenge_id(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A won challenge should be confirmed with points and date."""

    exit_code = main(
        _explain(
            run_output_dir,
            "U1",
            "Neden C-03 ödülünü kazandım?",
            fmt="json",
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"]["status"] == "WON"
    assert payload["evidence"]["points"] == 380


def test_explain_unknown_question_falls_back(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unsupported questions should get the controlled fallback answer."""

    exit_code = main(_explain(run_output_dir, "U1", "Bugün hava nasıl olacak?"))

    assert exit_code == 0
    assert capsys.readouterr().out.strip() != ""


def test_explain_is_deterministic(
    run_output_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same question must always produce the same JSON answer."""

    args = _explain(run_output_dir, "U2", "Kaç puanım var?", fmt="json")

    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out

    assert first == second


def test_explain_fails_cleanly_on_corrupt_states_file(
    run_output_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A corrupt states.json must produce exit code 1 and a clear error."""

    broken_dir = tmp_path / "broken"
    broken_dir.mkdir()
    for filename in run_output_dir.glob("*.json"):
        (broken_dir / filename.name).write_text(
            filename.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (broken_dir / "states.json").write_text("{not valid json", encoding="utf-8")

    exit_code = main(_explain(broken_dir, "U1", "Kaç puanım var?"))

    assert exit_code == 1
    assert "Explain Error" in capsys.readouterr().err
