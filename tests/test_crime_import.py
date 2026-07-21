"""Tests for src/crime_import.py."""

from __future__ import annotations

import pandas as pd

from src.crime_import import apply_column_mapping, guess_column_mapping


def test_guess_column_mapping_exact_match():
    mapping = guess_column_mapping(["tipo_crime", "data", "latitude", "longitude"])
    assert mapping["tipo_crime"] == "tipo_crime"
    assert mapping["data"] == "data"
    assert mapping["latitude"] == "latitude"
    assert mapping["longitude"] == "longitude"


def test_guess_column_mapping_case_and_whitespace_insensitive():
    mapping = guess_column_mapping(["Tipo Crime", " Latitude ", "LONGITUDE"])
    assert mapping["tipo_crime"] == "Tipo Crime"
    assert mapping["latitude"] == " Latitude "
    assert mapping["longitude"] == "LONGITUDE"


def test_guess_column_mapping_no_match_returns_none():
    mapping = guess_column_mapping(["coluna_desconhecida"])
    assert mapping["tipo_crime"] is None
    assert mapping["latitude"] is None


def test_apply_column_mapping_renames_and_omits_unmapped_fields():
    df = pd.DataFrame({"Tipo": ["Roubo"], "Lat": [-23.5], "Lon": [-46.6]})
    mapping = {"tipo_crime": "Tipo", "latitude": "Lat", "longitude": "Lon", "data": None}
    result = apply_column_mapping(df, mapping)

    assert list(result.columns) == ["tipo_crime", "latitude", "longitude"]
    assert result["tipo_crime"].iloc[0] == "Roubo"
    assert result["latitude"].iloc[0] == -23.5
