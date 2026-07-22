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

CRIME_TYPE_COLORWAY = ["#0b5ed7", "#e2565b", "#2ca25f", "#f0ad4e", "#6f42c1"]


def ordered_crime_types(crimes: pd.DataFrame) -> list[str]:
    """Unique tipo_crime values sorted alphabetically, for stable color assignment.

    Sorted (not first-seen order) so the same tipo_crime always maps to the
    same color regardless of which page/dataframe computes the list — Mapa
    and Estatísticas each call this independently on their own crimes frame.
    """
    if crimes.empty:
        return []
    return sorted(crimes["tipo_crime"].unique())


def crime_type_color(tipo_crime: str, ordered_types: list[str]) -> str:
    """Deterministic color for a crime type, cycling CRIME_TYPE_COLORWAY.

    The same tipo_crime always gets the same color across the map pins, the
    crime list panel, and the donut chart, as long as callers pass the same
    ordered_types list (computed once per case via ordered_crime_types).
    """
    if tipo_crime not in ordered_types:
        return CRIME_TYPE_COLORWAY[-1]
    return CRIME_TYPE_COLORWAY[ordered_types.index(tipo_crime) % len(CRIME_TYPE_COLORWAY)]


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
    _add_clustered_markers(crime_map, crimes, ordered_crime_types(crimes))
    _add_density_heatmap(crime_map, analysis)
    _add_rossmo_heatmap(crime_map, analysis)
    _add_profile_zones(crime_map, analysis)
    _add_canter_circle(crime_map, analysis)
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


def _add_clustered_markers(
    crime_map: folium.Map,
    crimes: pd.DataFrame,
    ordered_types: list[str],
) -> None:
    """Add all crime markers inside a marker cluster layer, colored by tipo_crime."""
    marker_cluster = MarkerCluster(name="Ocorrências agrupadas").add_to(crime_map)

    for _, row in crimes.iterrows():
        color = crime_type_color(row["tipo_crime"], ordered_types)
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(_build_popup(row), max_width=320),
            tooltip=_build_tooltip(row),
            icon=folium.DivIcon(
                icon_size=(16, 16),
                icon_anchor=(8, 8),
                html=(
                    f'<div style="width:16px;height:16px;border-radius:50%;'
                    f'background:{color};border:2px solid #ffffff;'
                    f'box-shadow:0 0 4px rgba(0,0,0,0.45);"></div>'
                ),
            ),
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


def _add_rossmo_heatmap(crime_map: folium.Map, analysis: GeographicAnalysis) -> None:
    """Add Rossmo's CGT probability surface as an optional heatmap layer."""
    if not analysis.rossmo_surface:
        return

    HeatMap(
        analysis.rossmo_surface,
        name="Perfil de Rossmo (CGT)",
        radius=34,
        blur=28,
        min_opacity=0.18,
        max_zoom=15,
        show=False,
        gradient={
            0.15: "#3f2d63",
            0.35: "#7b4ea3",
            0.55: "#c46fb3",
            0.75: "#f2915a",
            1.0: "#ffb703",
        },
    ).add_to(crime_map)


def _add_canter_circle(crime_map: folium.Map, analysis: GeographicAnalysis) -> None:
    """Add Canter's Circle Hypothesis as a dashed, unfilled circle."""
    circle = analysis.canter_circle
    if circle is None or circle.radius_km <= 0:
        return

    id_a, id_b = circle.farthest_pair
    folium.Circle(
        location=[circle.center.latitude, circle.center.longitude],
        radius=circle.radius_km * 1000,
        color="#8b5cf6",
        weight=2,
        dash_array="8, 8",
        fill=False,
        popup=folium.Popup(
            _build_canter_circle_popup(circle.center, circle.radius_km, id_a, id_b),
            max_width=360,
        ),
        tooltip="Círculo de Canter",
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


def _build_canter_circle_popup(center, radius_km: float, id_a: int, id_b: int) -> str:
    """Build popup for Canter's Circle Hypothesis."""
    return (
        "<div style='font-family:Arial,sans-serif;min-width:280px;'>"
        "<div style='font-size:15px;font-weight:900;color:#8b5cf6;margin-bottom:8px;'>"
        "Círculo de Canter</div>"
        f"<strong>Centro:</strong> {center.latitude:.6f}, {center.longitude:.6f}<br>"
        f"<strong>Raio:</strong> {radius_km:.2f} km<br>"
        f"<strong>Definido pelos crimes:</strong> #{id_a} e #{id_b} (os mais distantes "
        "entre si da série)<br><br>"
        "A hipótese do Círculo de Canter espera que a base do infrator esteja "
        "localizada dentro deste círculo."
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
