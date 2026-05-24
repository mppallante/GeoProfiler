"""Shared utility functions for GeoProfiler."""

from __future__ import annotations

import pandas as pd


def normalize_column_names(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize DataFrame column names for internal use."""
    normalized = data.copy()
    normalized.columns = (
        normalized.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )
    return normalized
