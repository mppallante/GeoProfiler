"""Statistical analysis helpers for GeoProfiler."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CrimeStatistics:
    """Small container for dashboard metrics."""

    total_records: int
    unique_crime_types: int
    date_range_label: str


@dataclass(frozen=True)
class StatisticalDashboard:
    """Structured statistical data used by the Streamlit dashboard."""

    crime_type_frequency: pd.DataFrame
    district_frequency: pd.DataFrame
    weekday_frequency: pd.DataFrame
    hour_frequency: pd.DataFrame
    timeline: pd.DataFrame


def calculate_basic_statistics(crimes: pd.DataFrame) -> CrimeStatistics:
    """Calculate simple metrics for the initial dashboard."""
    if crimes.empty:
        return CrimeStatistics(
            total_records=0,
            unique_crime_types=0,
            date_range_label="Sem dados",
        )

    min_date = crimes["data"].min()
    max_date = crimes["data"].max()
    date_range_label = f"{min_date:%d/%m/%Y} - {max_date:%d/%m/%Y}"

    return CrimeStatistics(
        total_records=len(crimes),
        unique_crime_types=crimes["tipo_crime"].nunique(),
        date_range_label=date_range_label,
    )


def build_statistical_dashboard(crimes: pd.DataFrame) -> StatisticalDashboard:
    """Build all statistical tables required by the dashboard."""
    prepared = prepare_statistics_data(crimes)

    return StatisticalDashboard(
        crime_type_frequency=calculate_frequency(
            prepared,
            column="tipo_crime",
            label="tipo_crime",
        ),
        district_frequency=calculate_frequency(
            prepared,
            column="bairro",
            label="bairro",
        ),
        weekday_frequency=calculate_weekday_frequency(prepared),
        hour_frequency=calculate_hour_frequency(prepared),
        timeline=calculate_crime_timeline(prepared),
    )


def prepare_statistics_data(crimes: pd.DataFrame) -> pd.DataFrame:
    """Normalize fields needed by the statistical module."""
    prepared = crimes.copy()
    if prepared.empty:
        return prepared

    prepared["data"] = pd.to_datetime(prepared["data"], errors="coerce")
    prepared["tipo_crime"] = prepared["tipo_crime"].replace("", "Não informado")
    prepared["bairro"] = prepared["bairro"].replace("", "Não informado")
    prepared["hora"] = prepared["hora"].fillna("").astype(str)
    prepared["hora_numero"] = pd.to_numeric(
        prepared["hora"].str.slice(0, 2),
        errors="coerce",
    )

    return prepared.dropna(subset=["data"])


def calculate_frequency(
    crimes: pd.DataFrame,
    column: str,
    label: str,
) -> pd.DataFrame:
    """Calculate absolute and relative frequency for a categorical column."""
    if crimes.empty or column not in crimes.columns:
        return empty_frequency_table(label)

    frequency = (
        crimes[column]
        .fillna("Não informado")
        .astype(str)
        .replace("", "Não informado")
        .value_counts()
        .rename_axis(label)
        .reset_index(name="total")
    )
    frequency["percentual"] = (frequency["total"] / frequency["total"].sum() * 100).round(2)

    return frequency


def calculate_weekday_frequency(crimes: pd.DataFrame) -> pd.DataFrame:
    """Calculate crime frequency by weekday."""
    columns = ["dia_semana", "total", "percentual"]
    if crimes.empty:
        return pd.DataFrame(columns=columns)

    weekday_order = [
        "Segunda",
        "Terça",
        "Quarta",
        "Quinta",
        "Sexta",
        "Sábado",
        "Domingo",
    ]
    weekday_map = {
        0: "Segunda",
        1: "Terça",
        2: "Quarta",
        3: "Quinta",
        4: "Sexta",
        5: "Sábado",
        6: "Domingo",
    }

    weekday_data = crimes.copy()
    weekday_data["dia_semana"] = weekday_data["data"].dt.dayofweek.map(weekday_map)

    frequency = (
        weekday_data["dia_semana"]
        .value_counts()
        .reindex(weekday_order, fill_value=0)
        .rename_axis("dia_semana")
        .reset_index(name="total")
    )
    frequency["percentual"] = (frequency["total"] / max(len(weekday_data), 1) * 100).round(2)

    return frequency[columns]


def calculate_hour_frequency(crimes: pd.DataFrame) -> pd.DataFrame:
    """Calculate crime frequency by hour of day."""
    columns = ["hora", "total", "percentual"]
    if crimes.empty:
        return pd.DataFrame(columns=columns)

    valid_hours = crimes.dropna(subset=["hora_numero"]).copy()
    valid_hours = valid_hours[
        valid_hours["hora_numero"].between(0, 23)
    ]
    if valid_hours.empty:
        return pd.DataFrame(columns=columns)

    frequency = (
        valid_hours["hora_numero"]
        .astype(int)
        .value_counts()
        .reindex(range(24), fill_value=0)
        .rename_axis("hora")
        .reset_index(name="total")
    )
    frequency["percentual"] = (frequency["total"] / len(valid_hours) * 100).round(2)
    frequency["hora"] = frequency["hora"].astype(int)

    return frequency[columns]


def calculate_crime_timeline(crimes: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily crime counts over time."""
    columns = ["data", "total"]
    if crimes.empty:
        return pd.DataFrame(columns=columns)

    timeline = (
        crimes.groupby(crimes["data"].dt.date)
        .size()
        .rename("total")
        .reset_index()
        .rename(columns={"data": "data"})
    )
    timeline["data"] = pd.to_datetime(timeline["data"])

    return timeline.sort_values("data").reset_index(drop=True)


def empty_frequency_table(label: str) -> pd.DataFrame:
    """Create an empty frequency table with the standard schema."""
    return pd.DataFrame(columns=[label, "total", "percentual"])
