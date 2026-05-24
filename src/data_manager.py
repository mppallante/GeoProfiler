"""Data loading, validation, and persistence helpers for GeoProfiler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
import os
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from src.utils import normalize_column_names


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = Path(os.environ.get("GEOPROFILER_RUNTIME_DIR", PROJECT_ROOT))
DATA_PATH = RUNTIME_ROOT / "data" / "crimes.csv"

CRIME_COLUMNS = [
    "id",
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

REQUIRED_COLUMNS = {"tipo_crime", "data", "latitude", "longitude"}


@dataclass(frozen=True)
class CrimeInput:
    """Validated form data used to create a crime record."""

    tipo_crime: str
    data: date
    hora: time
    latitude: float
    longitude: float
    cidade: str
    bairro: str
    modus_operandi: str
    observacoes: str


def load_crime_data(uploaded_file: BinaryIO | None = None) -> pd.DataFrame:
    """Load crime records from an uploaded file or the project CSV database."""
    source = uploaded_file if uploaded_file is not None else DATA_PATH
    if uploaded_file is None:
        ensure_data_file()

    data = pd.read_csv(source)
    data = normalize_column_names(data)
    return prepare_crime_data(data)


def read_crime_database() -> pd.DataFrame:
    """Read the persistent crime database, creating it when needed."""
    ensure_data_file()
    return load_crime_data()


def ensure_data_file() -> None:
    """Create the data directory and CSV file if they do not exist."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DATA_PATH.exists():
        pd.DataFrame(columns=CRIME_COLUMNS).to_csv(DATA_PATH, index=False)


def save_crime_record(crime_input: CrimeInput) -> pd.DataFrame:
    """Persist a validated crime record and return the updated database."""
    crimes = read_crime_database()
    next_id = generate_next_id(crimes)
    record = build_crime_record(next_id, crime_input)

    updated = pd.concat([crimes, pd.DataFrame([record])], ignore_index=True)
    updated = prepare_crime_data(updated)
    write_crime_database(updated)

    return updated


def build_crime_record(record_id: int, crime_input: CrimeInput) -> dict[str, object]:
    """Build a serializable record from form input."""
    return {
        "id": record_id,
        "tipo_crime": crime_input.tipo_crime.strip(),
        "data": crime_input.data.isoformat(),
        "hora": crime_input.hora.strftime("%H:%M"),
        "latitude": crime_input.latitude,
        "longitude": crime_input.longitude,
        "cidade": crime_input.cidade.strip(),
        "bairro": crime_input.bairro.strip(),
        "modus_operandi": crime_input.modus_operandi.strip(),
        "observacoes": crime_input.observacoes.strip(),
    }


def write_crime_database(crimes: pd.DataFrame) -> None:
    """Write the crime database using the canonical column order."""
    output = crimes.copy()
    output["data"] = output["data"].dt.strftime("%Y-%m-%d")
    output = output[CRIME_COLUMNS]
    output.to_csv(DATA_PATH, index=False)


def generate_next_id(crimes: pd.DataFrame) -> int:
    """Generate the next sequential crime ID."""
    if crimes.empty or "id" not in crimes.columns:
        return 1

    ids = pd.to_numeric(crimes["id"], errors="coerce").dropna()
    if ids.empty:
        return 1

    return int(ids.max()) + 1


def validate_coordinates(latitude: float, longitude: float) -> None:
    """Validate latitude and longitude ranges."""
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude deve estar entre -90 e 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude deve estar entre -180 e 180.")


def prepare_crime_data(data: pd.DataFrame) -> pd.DataFrame:
    """Apply cleanup and schema normalization needed by the application."""
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Colunas obrigatorias ausentes: {missing}")

    cleaned = data.copy()
    cleaned = add_missing_columns(cleaned)
    cleaned = migrate_legacy_columns(cleaned)

    cleaned["id"] = pd.to_numeric(cleaned["id"], errors="coerce")
    cleaned["data"] = pd.to_datetime(cleaned["data"], errors="coerce")
    cleaned["hora"] = cleaned["hora"].fillna("").astype(str)
    cleaned["latitude"] = pd.to_numeric(cleaned["latitude"], errors="coerce")
    cleaned["longitude"] = pd.to_numeric(cleaned["longitude"], errors="coerce")
    cleaned["tipo_crime"] = cleaned["tipo_crime"].fillna("").astype(str)
    cleaned["cidade"] = cleaned["cidade"].fillna("").astype(str)
    cleaned["bairro"] = cleaned["bairro"].fillna("").astype(str)
    cleaned["modus_operandi"] = cleaned["modus_operandi"].fillna("").astype(str)
    cleaned["observacoes"] = cleaned["observacoes"].fillna("").astype(str)

    cleaned = cleaned.dropna(subset=["data", "latitude", "longitude"])
    cleaned = cleaned[
        cleaned["latitude"].between(-90, 90)
        & cleaned["longitude"].between(-180, 180)
    ]
    cleaned = cleaned.sort_values(["data", "id"], ascending=[False, False])
    cleaned = cleaned.reset_index(drop=True)
    cleaned = cleaned[CRIME_COLUMNS]

    return cleaned


def add_missing_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Add absent schema columns with empty default values."""
    normalized = data.copy()
    for column in CRIME_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    return normalized


def migrate_legacy_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Preserve values from the first sample CSV format."""
    migrated = data.copy()

    if "local" in migrated.columns:
        empty_bairro = migrated["bairro"].isna() | (migrated["bairro"].astype(str) == "")
        migrated.loc[empty_bairro, "bairro"] = migrated.loc[empty_bairro, "local"]

    return migrated
