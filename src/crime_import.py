"""CSV/XLSX bulk import helpers: reading, column-mapping, and applying it."""

from __future__ import annotations

import pandas as pd

CANONICAL_IMPORT_FIELDS = [
    "tipo_crime",
    "data",
    "hora",
    "latitude",
    "longitude",
    "cidade",
    "bairro",
    "modus_operandi",
    "observacoes",
]

REQUIRED_IMPORT_FIELDS = {"tipo_crime", "data", "latitude", "longitude"}


def read_uploaded_table(uploaded_file) -> pd.DataFrame:
    """Read an uploaded CSV or XLSX file into a raw DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx"):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def _normalize_column_label(label: str) -> str:
    return str(label).strip().lower().replace(" ", "_").replace("-", "_")


def guess_column_mapping(columns: list[str]) -> dict[str, str | None]:
    """Best-effort auto-match of uploaded columns to canonical field names."""
    normalized_to_original = {_normalize_column_label(column): column for column in columns}
    return {field: normalized_to_original.get(field) for field in CANONICAL_IMPORT_FIELDS}


def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    """Build a DataFrame with canonical column names from a confirmed mapping."""
    selected = {
        field: df[source_column]
        for field, source_column in mapping.items()
        if source_column is not None
    }
    return pd.DataFrame(selected)
