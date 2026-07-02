"""
File Loader Utilities for Gamification System.

Provides helper functions for loading input data and exporting
output artefacts in a consistent format.
"""

import json
import pandas as pd
from typing import Any


def load_csv(filepath: str) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame.

    Args:
        filepath: The path to the CSV file.

    Returns:
        A pandas DataFrame containing the parsed CSV data.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    return pd.read_csv(filepath)


def export_json(data: Any, filepath: str) -> None:
    """Export data to a JSON file with pretty formatting.

    Args:
        data: The Python object to serialise (must be JSON-serialisable).
        filepath: The destination file path for the JSON output.
    """
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def load_json(filepath: str) -> Any:
    """Load and parse a JSON file.

    Args:
        filepath: The path to the JSON file.

    Returns:
        The parsed Python object.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    with open(filepath, "r", encoding="utf-8") as fh:
        return json.load(fh)
