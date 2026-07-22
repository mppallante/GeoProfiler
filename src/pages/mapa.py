"""Tactical map page for the active case."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.geo_analysis import run_geographic_analysis
from src.map_visualization import create_crime_map, crime_type_color, ordered_crime_types
from src.pages._shared import (
    inject_global_styles,
    load_case_crimes,
    render_case_header,
    render_date_range_filter,
    render_sidebar,
    require_active_case,
)

_cached_run_geographic_analysis = st.cache_data(show_spinner=False)(run_geographic_analysis)

PANEL_HEIGHT = 560


def main() -> None:
    theme = render_sidebar()
    inject_global_styles(theme)

    caso = require_active_case()
    render_case_header(caso)

    crimes = load_case_crimes(caso.id)
    crimes = render_date_range_filter(caso, crimes)
    geo_analysis = _cached_run_geographic_analysis(crimes)

    st.subheader("Mapa tático de ocorrências")

    map_col, list_col = st.columns([2.4, 1])
    with map_col:
        crime_map = create_crime_map(crimes, geo_analysis)
        st_folium(crime_map, width=None, height=PANEL_HEIGHT)
    with list_col:
        render_crime_list_panel(crimes, geo_analysis.crimes_with_distances)


def render_crime_list_panel(crimes: pd.DataFrame, crimes_with_distances: pd.DataFrame) -> None:
    """Render a compact, scrollable list of the crimes shown on the map."""
    st.markdown(f"**Ocorrências ({len(crimes)})**")

    if crimes_with_distances.empty:
        st.caption("Nenhuma ocorrência para listar.")
        return

    ordered_types = ordered_crime_types(crimes)
    with st.container(height=PANEL_HEIGHT):
        for row in crimes_with_distances.itertuples():
            color = crime_type_color(row.tipo_crime, ordered_types)
            date_label = row.data.strftime("%d/%m/%Y") if hasattr(row.data, "strftime") else "-"
            distance_label = (
                f"{row.distancia_centro_km:.2f} km do CGC"
                if hasattr(row, "distancia_centro_km")
                else ""
            )
            st.markdown(
                f"""
                <div style="display:flex; align-items:flex-start; gap:10px;
                    padding:10px 4px; border-bottom:1px solid var(--gp-border);">
                    <div style="width:10px; height:10px; border-radius:50%;
                        background:{color}; margin-top:5px; flex-shrink:0;"></div>
                    <div>
                        <div style="font-weight:700; color:var(--gp-text); font-size:0.92rem;">
                            {escape(row.tipo_crime or "Não informado")}
                            <span style="font-weight:400; color:var(--gp-muted);">
                                · {escape(row.bairro or "Bairro não informado")}
                            </span>
                        </div>
                        <div style="font-size:0.8rem; color:var(--gp-muted);
                            font-family:var(--gp-font-mono);">
                            {date_label} · {distance_label}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


main()
