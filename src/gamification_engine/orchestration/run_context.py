"""Execution context for the batch gamification pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RunContext:
    """Execution parameters and paths for a single pipeline run."""

    activities_csv_path: Path
    challenges_csv_path: Path
    output_dir: Path
    run_date: date
    existing_ledger_path: Path | None = None
    existing_badges_path: Path | None = None
    existing_notifications_path: Path | None = None

    def __post_init__(self) -> None:
        """Resolve paths and assign defaults for missing historical file paths."""

        object.__setattr__(self, "activities_csv_path", Path(self.activities_csv_path))
        object.__setattr__(self, "challenges_csv_path", Path(self.challenges_csv_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))

        if self.existing_ledger_path is None:
            object.__setattr__(
                self,
                "existing_ledger_path",
                Path(self.output_dir) / "ledger.json",
            )
        else:
            object.__setattr__(
                self,
                "existing_ledger_path",
                Path(self.existing_ledger_path),
            )

        if self.existing_badges_path is None:
            object.__setattr__(
                self,
                "existing_badges_path",
                Path(self.output_dir) / "badges.json",
            )
        else:
            object.__setattr__(
                self,
                "existing_badges_path",
                Path(self.existing_badges_path),
            )

        if self.existing_notifications_path is None:
            object.__setattr__(
                self,
                "existing_notifications_path",
                Path(self.output_dir) / "notifications.json",
            )
        else:
            object.__setattr__(
                self,
                "existing_notifications_path",
                Path(self.existing_notifications_path),
            )
