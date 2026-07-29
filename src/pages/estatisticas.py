"""Statistics dashboard page for the active case."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.pages._shared import (
    format_frequency_table,
    inject_global_styles,
    load_case_crimes,
    render_case_header,
    render_chart_card,
    render_date_range_filter,
    render_horizontal_bar_chart,
    render_metric_card,
    render_sidebar,
    render_vertical_bar_chart,
    require_active_case,
    style_chart,
)
from src.statistics import StatisticalDashboard, build_statistical_dashboard

_cached_build_statistical_dashboard = st.cache_data(show_spinner=False)(build_statistical_dashboard)


def main() -> None:
    settings = render_sidebar()
    inject_global_styles(settings)

    caso = require_active_case()
    render_case_header(caso)

    crimes = load_case_crimes(caso.id)
    crimes = render_date_range_filter(caso, crimes)
    dashboard = _cached_build_statistical_dashboard(crimes)

    render_statistical_dashboard(dashboard, crimes)


def render_kpi_row(dashboard: StatisticalDashboard, crimes: pd.DataFrame) -> None:
    """Render the top-of-page KPI row: total, top type, top district, period."""
    top_tipo = dashboard.crime_type_frequency.iloc[0]["tipo_crime"] if not dashboard.crime_type_frequency.empty else "—"
    top_bairro = dashboard.district_frequency.iloc[0]["bairro"] if not dashboard.district_frequency.empty else "—"
    period = "—"
    if not crimes.empty:
        period = f"{crimes['data'].min():%d/%m/%Y} – {crimes['data'].max():%d/%m/%Y}"

    kpi_cols = st.columns(4)
    render_metric_card(kpi_cols[0], "list_alt", "Total de ocorrências", str(len(crimes)), "Registros no período")
    render_metric_card(kpi_cols[1], "category", "Tipo mais frequente", str(top_tipo), "Categoria dominante")
    render_metric_card(kpi_cols[2], "location_on", "Bairro mais frequente", str(top_bairro), "Concentração territorial")
    render_metric_card(kpi_cols[3], "date_range", "Período", period, "Intervalo analisado")


def render_statistical_dashboard(dashboard: StatisticalDashboard, crimes: pd.DataFrame) -> None:
    """Render interactive statistical charts and frequency tables."""
    st.subheader("Dashboard estatístico")

    if dashboard.timeline.empty:
        st.warning("Cadastre crimes válidos para gerar estatísticas.")
        return

    render_kpi_row(dashboard, crimes)

    top_cols = st.columns(2)
    tipo_items = [
        (row["tipo_crime"], int(row["total"]), float(row["percentual"]))
        for _, row in dashboard.crime_type_frequency.iterrows()
    ]
    render_chart_card(
        top_cols[0],
        "Frequência por tipo de crime",
        render_horizontal_bar_chart(tipo_items, color="var(--gp-accent)"),
    )

    bairro_items = [
        (row["bairro"], int(row["total"])) for _, row in dashboard.district_frequency.iterrows()
    ]
    render_chart_card(
        top_cols[1],
        "Frequência por bairro",
        render_vertical_bar_chart(bairro_items, color="var(--gp-accent)"),
    )

    middle_cols = st.columns(2)
    weekday_items = [
        (row["dia_semana"], int(row["total"])) for _, row in dashboard.weekday_frequency.iterrows()
    ]
    render_chart_card(
        middle_cols[0],
        "Frequência por dia da semana",
        render_vertical_bar_chart(weekday_items, color="var(--gp-accent)", bar_width="22px"),
    )

    hour_items = [(int(row["hora"]), int(row["total"])) for _, row in dashboard.hour_frequency.iterrows()]
    render_chart_card(
        middle_cols[1],
        "Frequência por horário",
        render_vertical_bar_chart(hour_items, color="var(--gp-accent-2)", thin=True),
    )

    timeline_chart = px.line(
        dashboard.timeline,
        x="data",
        y="total",
        markers=True,
        title="Linha do tempo dos crimes",
        labels={"data": "Data", "total": "Ocorrências"},
    )
    st.plotly_chart(style_chart(timeline_chart), width="stretch")

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
