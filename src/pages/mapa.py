"""Tactical map page for the active case."""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from src.geo_analysis import run_geographic_analysis
from src.map_visualization import create_crime_map
from src.pages._shared import (
    inject_global_styles,
    load_case_crimes,
    render_case_header,
    render_date_range_filter,
    render_sidebar,
    require_active_case,
)

_cached_run_geographic_analysis = st.cache_data(show_spinner=False)(run_geographic_analysis)


def main() -> None:
    theme = render_sidebar()
    inject_global_styles(theme)

    caso = require_active_case()
    render_case_header(caso)

    crimes = load_case_crimes(caso.id)
    crimes = render_date_range_filter(caso, crimes)
    geo_analysis = _cached_run_geographic_analysis(crimes)

    st.subheader("Mapa tático de ocorrências")
    crime_map = create_crime_map(crimes, geo_analysis)
    st_folium(crime_map, width=None, height=560)


main()
