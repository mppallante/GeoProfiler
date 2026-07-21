"""Shared pytest fixtures for GeoProfiler tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data_manager import prepare_crime_data
from src.utils import normalize_column_names

SEED_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "crimes.csv"


@pytest.fixture
def seed_crimes() -> pd.DataFrame:
    """Load the repo's seed crime dataset through the real preparation pipeline."""
    raw = pd.read_csv(SEED_CSV_PATH)
    return prepare_crime_data(normalize_column_names(raw))
