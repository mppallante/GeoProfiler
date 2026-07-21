"""Tests for the pure helper functions in src/pages/_shared.py."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.pages._shared import filter_crimes_by_date_range


def test_filter_crimes_by_date_range_keeps_only_rows_inside_inclusive_bounds():
    crimes = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "data": pd.to_datetime(
                ["2026-01-01", "2026-01-05", "2026-01-10", "2026-01-15"]
            ),
        }
    )

    result = filter_crimes_by_date_range(crimes, date(2026, 1, 5), date(2026, 1, 10))

    assert list(result["id"]) == [2, 3]


def test_filter_crimes_by_date_range_empty_input_returns_empty():
    crimes = pd.DataFrame({"id": [], "data": pd.to_datetime([])})

    result = filter_crimes_by_date_range(crimes, date(2026, 1, 1), date(2026, 1, 31))

    assert result.empty


def test_filter_crimes_by_date_range_matches_seed_data_known_dates(seed_crimes):
    # seed_crimes has 5 distinct dates: 01-05, 01-12, 01-20, 02-02, 02-11.
    # A range of 01-13..02-05 should keep exactly the 01-20 and 02-02 rows.
    result = filter_crimes_by_date_range(seed_crimes, date(2026, 1, 13), date(2026, 2, 5))

    assert sorted(result["data"].dt.date.unique()) == [date(2026, 1, 20), date(2026, 2, 2)]
