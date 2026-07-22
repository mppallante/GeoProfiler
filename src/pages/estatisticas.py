"""Statistics dashboard page for the active case."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.map_visualization import crime_type_color, ordered_crime_types
from src.pages._shared import (
    format_frequency_table,
    inject_global_styles,
    load_case_crimes,
    render_case_header,
    render_date_range_filter,
    render_sidebar,
    require_active_case,
    style_chart,
)
from src.statistics import StatisticalDashboard, build_statistical_dashboard

_cached_build_statistical_dashboard = st.cache_data(show_spinner=False)(build_statistical_dashboard)


def main() -> None:
    theme = render_sidebar()
    inject_global_styles(theme)

    caso = require_active_case()
    render_case_header(caso)

    crimes = load_case_crimes(caso.id)
    crimes = render_date_range_filter(caso, crimes)
    dashboard = _cached_build_statistical_dashboard(crimes)

    render_statistical_dashboard(dashboard, crimes, theme)


def render_statistical_dashboard(dashboard: StatisticalDashboard, crimes: pd.DataFrame, theme: str) -> None:
    """Render interactive statistical charts and frequency tables."""
    st.subheader("Dashboard estatístico")

    if dashboard.timeline.empty:
        st.warning("Cadastre crimes válidos para gerar estatísticas.")
        return

    ordered_types = ordered_crime_types(crimes)
    top_cols = st.columns(2)
    with top_cols[0]:
        crime_type_chart = px.pie(
            dashboard.crime_type_frequency,
            values="total",
            names="tipo_crime",
            hole=0.55,
            title="Frequência por tipo de crime",
            color="tipo_crime",
            color_discrete_map={t: crime_type_color(t, ordered_types) for t in ordered_types},
            labels={"tipo_crime": "Tipo de crime", "total": "Ocorrências"},
        )
        crime_type_chart.update_traces(textinfo="percent+label")
        st.plotly_chart(style_chart(crime_type_chart, theme), width="stretch")

    with top_cols[1]:
        district_chart = px.bar(
            dashboard.district_frequency,
            x="bairro",
            y="total",
            text="total",
            title="Frequência por bairro",
            labels={"bairro": "Bairro", "total": "Ocorrências"},
        )
        st.plotly_chart(style_chart(district_chart, theme), width="stretch")

    middle_cols = st.columns(2)
    with middle_cols[0]:
        weekday_chart = px.bar(
            dashboard.weekday_frequency,
            x="dia_semana",
            y="total",
            text="total",
            title="Frequência por dia da semana",
            labels={"dia_semana": "Dia da semana", "total": "Ocorrências"},
        )
        st.plotly_chart(style_chart(weekday_chart, theme), width="stretch")

    with middle_cols[1]:
        hour_chart = px.line(
            dashboard.hour_frequency,
            x="hora",
            y="total",
            markers=True,
            title="Frequência por horário",
            labels={"hora": "Hora do dia", "total": "Ocorrências"},
        )
        hour_chart.update_xaxes(dtick=1)
        st.plotly_chart(style_chart(hour_chart, theme), width="stretch")

    timeline_chart = px.line(
        dashboard.timeline,
        x="data",
        y="total",
        markers=True,
        title="Linha do tempo dos crimes",
        labels={"data": "Data", "total": "Ocorrências"},
    )
    st.plotly_chart(style_chart(timeline_chart, theme), width="stretch")

    table_cols = st.columns(2)
    with table_cols[0]:
        st.markdown("#### Tipos de crime")
        st.dataframe(
            format_frequency_table(dashboard.crime_type_frequency, "Tipo de crime"),
            width="stretch",
            hide_index=True,
        )
        st.markdown("#### Dias da semana")
        st.dataframe(
            format_frequency_table(dashboard.weekday_frequency, "Dia da semana"),
            width="stretch",
            hide_index=True,
        )

    with table_cols[1]:
        st.markdown("#### Bairros")
        st.dataframe(
            format_frequency_table(dashboard.district_frequency, "Bairro"),
            width="stretch",
            hide_index=True,
        )
        st.markdown("#### Horários")
        st.dataframe(
            format_frequency_table(dashboard.hour_frequency, "Hora"),
            width="stretch",
            hide_index=True,
        )


main()
