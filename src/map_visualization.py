"""Map visualization functions for GeoProfiler."""

from __future__ import annotations

from html import escape

import folium
import pandas as pd
from folium.plugins import HeatMap, MarkerCluster

from src.geo_analysis import (
    GeographicAnalysis,
    calculate_central_point,
    calculate_map_bounds,
    run_geographic_analysis,
)


DEFAULT_MAP_CENTER = [-23.550520, -46.633308]
DEFAULT_ZOOM = 12


def create_crime_map(
    crimes: pd.DataFrame,
    analysis: GeographicAnalysis | None = None,
) -> folium.Map:
    """Create a Folium map with markers, profiling zones, CGC, and heatmap."""
    if crimes.empty:
        return _create_base_map(DEFAULT_MAP_CENTER, DEFAULT_ZOOM)

    analysis = analysis or run_geographic_analysis(crimes)
    center = analysis.center or calculate_central_point(crimes)
    map_center = (
        [center.latitude, center.longitude]
        if center is not None
        else DEFAULT_MAP_CENTER
    )

    crime_map = _create_base_map(map_center, DEFAULT_ZOOM)
    _add_clustered_markers(crime_map, crimes)
    _add_density_heatmap(crime_map, analysis)
    _add_profile_zones(crime_map, analysis)
    _add_central_gravity_point(crime_map, crimes, analysis)
    _fit_map_to_crimes(crime_map, crimes)

    folium.LayerControl(collapsed=False).add_to(crime_map)

    return crime_map


def _create_base_map(location: list[float], zoom_start: int) -> folium.Map:
    """Create the base map with light and dark tile options."""
    crime_map = folium.Map(
        location=location,
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True,
    )
    folium.TileLayer(
        "CartoDB positron",
        name="Mapa claro",
        control=True,
        show=True,
    ).add_to(crime_map)
    folium.TileLayer(
        "CartoDB dark_matter",
        name="Mapa escuro",
        control=True,
        show=False,
    ).add_to(crime_map)
    return crime_map


def _add_clustered_markers(crime_map: folium.Map, crimes: pd.DataFrame) -> None:
    """Add all crime markers inside a marker cluster layer."""
    marker_cluster = MarkerCluster(name="Ocorrências agrupadas").add_to(crime_map)

    for _, row in crimes.iterrows():
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(_build_popup(row), max_width=320),
            tooltip=_build_tooltip(row),
            icon=folium.Icon(color="red", icon="exclamation-sign"),
        ).add_to(marker_cluster)


def _add_density_heatmap(crime_map: folium.Map, analysis: GeographicAnalysis) -> None:
    """Add a continuous spatial density heatmap layer."""
    if not analysis.density_surface:
        return

    HeatMap(
        analysis.density_surface,
        name="Heatmap - densidade espacial",
        radius=34,
        blur=28,
        min_opacity=0.18,
        max_zoom=15,
        gradient={
            0.15: "#2c7bb6",
            0.35: "#abd9e9",
            0.55: "#ffffbf",
            0.75: "#fdae61",
            1.0: "#d7191c",
        },
    ).add_to(crime_map)


def _add_profile_zones(crime_map: folium.Map, analysis: GeographicAnalysis) -> None:
    """Add profiling zones to the map."""
    zones = [
        (analysis.security_zone, "#6c757d", "#6c757d", 0.06),
        (analysis.comfort_zone, "#e2565b", "#e2565b", 0.12),
        (analysis.operations_base, "#2ca25f", "#2ca25f", 0.18),
    ]

    for zone, color, fill_color, fill_opacity in zones:
        if zone.center is None or zone.radius_km <= 0:
            continue

        folium.Circle(
            location=[zone.center.latitude, zone.center.longitude],
            radius=zone.radius_km * 1000,
            color=color,
            weight=2,
            fill=True,
            fill_color=fill_color,
            fill_opacity=fill_opacity,
            popup=folium.Popup(
                _build_zone_popup(zone.title, zone.description, zone.evidence, zone.radius_km),
                max_width=360,
            ),
            tooltip=zone.title,
        ).add_to(crime_map)


def _add_central_gravity_point(
    crime_map: folium.Map,
    crimes: pd.DataFrame,
    analysis: GeographicAnalysis,
) -> None:
    """Highlight the Criminal Gravity Center as the main map element."""
    center = analysis.center or calculate_central_point(crimes)
    if center is None:
        return

    folium.CircleMarker(
        location=[center.latitude, center.longitude],
        radius=18,
        color="#0b5ed7",
        weight=4,
        fill=True,
        fill_color="#4db6e8",
        fill_opacity=0.92,
        popup=folium.Popup(
            _build_cgc_popup(center, len(crimes)),
            max_width=360,
        ),
        tooltip="Centro de Gravidade Criminal (CGC)",
    ).add_to(crime_map)

    folium.Marker(
        location=[center.latitude, center.longitude],
        icon=folium.DivIcon(
            html=(
                '<div style="font-size:28px;color:#003f8f;'
                'text-shadow:0 0 4px #ffffff;font-weight:900;">★</div>'
            )
        ),
        popup=folium.Popup(
            _build_cgc_popup(center, len(crimes)),
            max_width=360,
        ),
        tooltip="Centro de Gravidade Criminal (CGC)",
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
    """Build a structured HTML popup for a crime occurrence."""
    date_value = row.get("data")
    date_label = date_value.strftime("%d/%m/%Y") if hasattr(date_value, "strftime") else "-"
    values = {
        "ID": row.get("id", "-"),
        "Tipo de Crime": row.get("tipo_crime", "Ocorrência"),
        "Data": date_label,
        "Hora": row.get("hora") or "-",
        "Cidade": row.get("cidade") or "Não informada",
        "Bairro": row.get("bairro") or "Não informado",
        "Modus Operandi": row.get("modus_operandi") or "Não informado",
    }

    rows = "".join(
        "<tr>"
        f"<td style='padding:4px 8px;color:#51606a;font-weight:700;'>{escape(str(label))}</td>"
        f"<td style='padding:4px 8px;color:#17212b;'>{escape(str(value))}</td>"
        "</tr>"
        for label, value in values.items()
    )

    return (
        "<div style='font-family:Arial,sans-serif;min-width:250px;'>"
        "<div style='font-size:15px;font-weight:800;color:#0b5ed7;margin-bottom:8px;'>"
        "Ocorrência criminal</div>"
        f"<table style='border-collapse:collapse;width:100%;'>{rows}</table>"
        "</div>"
    )


def _build_tooltip(row: pd.Series) -> str:
    """Build short marker tooltip text."""
    crime_id = row.get("id", "-")
    crime_type = row.get("tipo_crime", "Ocorrência")
    district = row.get("bairro") or "Bairro não informado"
    return f"ID {crime_id} | {crime_type} | {district}"


def _build_cgc_popup(center, total_crimes: int) -> str:
    """Build popup for the Criminal Gravity Center."""
    return (
        "<div style='font-family:Arial,sans-serif;min-width:260px;'>"
        "<div style='font-size:16px;font-weight:900;color:#0b5ed7;margin-bottom:8px;'>"
        "Centro de Gravidade Criminal (CGC)</div>"
        f"<strong>Latitude:</strong> {center.latitude:.6f}<br>"
        f"<strong>Longitude:</strong> {center.longitude:.6f}<br>"
        f"<strong>Ocorrências analisadas:</strong> {total_crimes}"
        "</div>"
    )


def _build_zone_popup(title: str, description: str, evidence: str, radius_km: float) -> str:
    """Build popup for a profiling zone."""
    return (
        "<div style='font-family:Arial,sans-serif;min-width:280px;'>"
        f"<div style='font-size:15px;font-weight:900;color:#17212b;margin-bottom:8px;'>{escape(title)}</div>"
        f"<strong>Raio estimado:</strong> {radius_km:.2f} km<br><br>"
        f"<strong>Descrição:</strong><br>{escape(description)}<br><br>"
        f"<strong>Base analítica:</strong><br>{escape(evidence)}"
        "</div>"
    )
