"""Tests for the Sprint 1 CLI placeholder."""

from gamification_engine.cli.main import main


def test_cli_version_prints_package_version(capsys) -> None:  # type: ignore[no-untyped-def]
    """The CLI should expose the package version."""

    exit_code = main(["--version"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "gamification-engine 0.1.0" in captured.out

