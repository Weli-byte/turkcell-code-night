"""Command-line entry point for the gamification engine."""

from __future__ import annotations

import argparse

from gamification_engine import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    The Sprint 1 CLI intentionally exposes only project metadata. The actual
    batch pipeline command will be added after the new package architecture has
    domain models, ingestion, and orchestration modules.
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

