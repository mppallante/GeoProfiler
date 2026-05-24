"""Map visualization functions for GeoProfiler."""

from __future__ import annotations

from html import escape

import folium
import pandas as pd
from folium.plugins import HeatMap, MarkerCluster

from src.geo_analysis import (
    build_heatmap_points,
    calculate_central_point,
    calculate_map_bounds,
)


DEFAULT_MAP_CENTER = [-23.550520, -46.633308]
DEFAULT_ZOOM = 12


def create_crime_map(crimes: pd.DataFrame) -> folium.Map:
    """Create a Folium map with clustered markers, heatmap, and central point."""
    if crimes.empty:
        return _create_base_map(DEFAULT_MAP_CENTER, DEFAULT_ZOOM)

    center = calculate_central_point(crimes)
    map_center = (
        [center.latitude, center.longitude]
        if center is not None
        else DEFAULT_MAP_CENTER
    )

    crime_map = _create_base_map(map_center, DEFAULT_ZOOM)
    _add_clustered_markers(crime_map, crimes)
    _add_heatmap(crime_map, crimes)
    _add_central_point(crime_map, crimes)
    _fit_map_to_crimes(crime_map, crimes)

    folium.LayerControl(collapsed=False).add_to(crime_map)

    return crime_map


def _create_base_map(location: list[float], zoom_start: int) -> folium.Map:
    """Create the base map with a clean tile layer."""
    return folium.Map(
        location=location,
        zoom_start=zoom_start,
        tiles="CartoDB dark_matter",
        control_scale=True,
    )


def _add_clustered_markers(crime_map: folium.Map, crimes: pd.DataFrame) -> None:
    """Add all crime markers inside a marker cluster layer."""
    marker_cluster = MarkerCluster(name="Crimes agrupados").add_to(crime_map)

    for _, row in crimes.iterrows():
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(_build_popup(row), max_width=320),
            tooltip=_build_tooltip(row),
            icon=folium.Icon(color="red", icon="exclamation-sign"),
        ).add_to(marker_cluster)


def _add_heatmap(crime_map: folium.Map, crimes: pd.DataFrame) -> None:
    """Add a heatmap layer with crime density."""
    heatmap_points = build_heatmap_points(crimes)
    if not heatmap_points:
        return

    HeatMap(
        heatmap_points,
        name="Mapa de calor",
        radius=28,
        blur=20,
        min_opacity=0.35,
    ).add_to(crime_map)


def _add_central_point(crime_map: folium.Map, crimes: pd.DataFrame) -> None:
    """Highlight the central point of the registered crimes."""
    center = calculate_central_point(crimes)
    if center is None:
        return

    folium.CircleMarker(
        location=[center.latitude, center.longitude],
        radius=10,
        color="#1f4e79",
        fill=True,
        fill_color="#1f4e79",
        fill_opacity=0.85,
        popup=folium.Popup(
            "<strong>Ponto central dos crimes</strong><br>"
            f"Latitude: {center.latitude:.6f}<br>"
            f"Longitude: {center.longitude:.6f}",
            max_width=280,
        ),
        tooltip="Ponto central",
    ).add_to(crime_map)


def _fit_map_to_crimes(crime_map: folium.Map, crimes: pd.DataFrame) -> None:
    """Automatically fit map zoom to all crime points."""
    bounds = calculate_map_bounds(crimes)
    if bounds is None:
        return

    if bounds.southwest == bounds.northeast:
        crime_map.location = [bounds.southwest.latitude, bounds.southwest.longitude]
        crime_map.zoom_start = 15
        return

    crime_map.fit_bounds(
        [
            [bounds.southwest.latitude, bounds.southwest.longitude],
            [bounds.northeast.latitude, bounds.northeast.longitude],
        ],
        padding=(30, 30),
    )


def _build_popup(row: pd.Series) -> str:
    """Build a small HTML popup for a crime occurrence."""
    date_value = row.get("data")
    date_label = date_value.strftime("%d/%m/%Y") if hasattr(date_value, "strftime") else "-"
    crime_type = escape(str(row.get("tipo_crime", "Ocorrencia")))
    district = escape(str(row.get("bairro") or "Bairro nao informado"))

    return (
        f"<strong>{crime_type}</strong><br>"
        f"Data: {date_label}<br>"
        f"Bairro: {district}"
    )


def _build_tooltip(row: pd.Series) -> str:
    """Build short marker tooltip text."""
    crime_type = row.get("tipo_crime", "Ocorrencia")
    district = row.get("bairro") or "Bairro nao informado"
    return f"{crime_type} - {district}"
