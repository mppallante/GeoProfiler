"""GeoProfiler Streamlit application entry point."""

from __future__ import annotations

import streamlit as st

from src.data_manager import bootstrap_case_database
from src.pages._shared import LOGO_PATH

st.set_page_config(
    page_title="GeoProfiler",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

bootstrap_case_database()

pg = st.navigation(
    {
        "Geral": [st.Page("src/pages/casos.py", title="Casos", default=True)],
        "Caso ativo": [
            st.Page("src/pages/mapa.py", title="Mapa"),
            st.Page("src/pages/estatisticas.py", title="Estatísticas"),
            st.Page("src/pages/analise_automatizada.py", title="Análise Automatizada"),
        ],
    }
)
pg.run()
