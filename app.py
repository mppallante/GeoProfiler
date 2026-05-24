"""GeoProfiler Streamlit application entry point."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from src.data_manager import (
    CrimeInput,
    read_crime_database,
    save_crime_record,
    validate_coordinates,
)
from src.geo_analysis import GeographicAnalysis, run_geographic_analysis
from src.map_visualization import create_crime_map
from src.statistics import (
    StatisticalDashboard,
    build_statistical_dashboard,
    calculate_basic_statistics,
)


st.set_page_config(
    page_title="GeoProfiler",
    page_icon="assets/logo.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"


def main() -> None:
    """Render the GeoProfiler interface."""
    inject_global_styles()
    render_sidebar()
    render_header()

    render_registration_form()

    crimes = load_current_database()
    render_dashboard(crimes)


def inject_global_styles() -> None:
    """Inject the GeoProfiler dark investigative interface styles."""
    st.markdown(
        """
        <style>
        :root {
            --gp-bg: #070b10;
            --gp-surface: #0d141d;
            --gp-surface-2: #111c28;
            --gp-border: rgba(116, 178, 214, 0.18);
            --gp-accent: #4db6e8;
            --gp-accent-2: #e2565b;
            --gp-text: #e8f2f7;
            --gp-muted: #8ea6b5;
        }

        .stApp {
            background:
                radial-gradient(circle at 18% 5%, rgba(77, 182, 232, 0.16), transparent 28%),
                linear-gradient(135deg, #070b10 0%, #0a1119 48%, #0d151d 100%);
            color: var(--gp-text);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #07101a 0%, #0b121a 100%);
            border-right: 1px solid var(--gp-border);
        }

        [data-testid="stSidebar"] img {
            border-radius: 8px;
            border: 1px solid rgba(77, 182, 232, 0.22);
            box-shadow: 0 14px 32px rgba(0, 0, 0, 0.35);
        }

        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2.5rem;
            max-width: 1440px;
        }

        h1, h2, h3, h4 {
            color: var(--gp-text);
            letter-spacing: 0;
        }

        .gp-header {
            border: 1px solid var(--gp-border);
            background: linear-gradient(135deg, rgba(13, 20, 29, 0.94), rgba(12, 29, 42, 0.9));
            border-radius: 8px;
            padding: 22px 24px;
            margin-bottom: 18px;
            box-shadow: 0 18px 48px rgba(0, 0, 0, 0.28);
        }

        .gp-header-kicker {
            color: var(--gp-accent);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .gp-header-title {
            color: var(--gp-text);
            font-size: 2.15rem;
            line-height: 1.1;
            font-weight: 760;
            margin: 0 0 8px 0;
        }

        .gp-header-subtitle {
            color: var(--gp-muted);
            font-size: 1rem;
            margin: 0;
        }

        .gp-sidebar-title {
            color: var(--gp-text);
            font-size: 1.16rem;
            font-weight: 760;
            margin-top: 0.75rem;
        }

        .gp-sidebar-meta {
            color: var(--gp-muted);
            font-size: 0.88rem;
            line-height: 1.5;
            padding: 12px;
            border: 1px solid var(--gp-border);
            border-radius: 8px;
            background: rgba(17, 28, 40, 0.74);
        }

        .gp-metric-card {
            border: 1px solid var(--gp-border);
            background: linear-gradient(180deg, rgba(17, 28, 40, 0.96), rgba(10, 17, 25, 0.96));
            border-radius: 8px;
            padding: 16px 16px 14px;
            min-height: 112px;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.24);
        }

        .gp-metric-label {
            color: var(--gp-muted);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        .gp-metric-value {
            color: var(--gp-text);
            font-size: 1.68rem;
            font-weight: 760;
            line-height: 1.1;
        }

        .gp-metric-caption {
            color: var(--gp-accent);
            font-size: 0.82rem;
            margin-top: 8px;
        }

        .gp-callout {
            border: 1px solid rgba(226, 86, 91, 0.28);
            border-left: 4px solid var(--gp-accent-2);
            background: rgba(226, 86, 91, 0.08);
            border-radius: 8px;
            padding: 14px 16px;
            color: #f3c8ca;
            margin-bottom: 16px;
        }

        [data-testid="stForm"], [data-testid="stExpander"], [data-testid="stDataFrame"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--gp-border) !important;
        }

        [data-testid="stForm"] {
            background: rgba(13, 20, 29, 0.72);
            border: 1px solid var(--gp-border);
            border-radius: 8px;
            padding: 18px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 1px solid var(--gp-border);
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(17, 28, 40, 0.72);
            border: 1px solid var(--gp-border);
            border-radius: 8px 8px 0 0;
            color: var(--gp-muted);
            padding: 10px 14px;
        }

        .stTabs [aria-selected="true"] {
            color: var(--gp-text);
            background: rgba(77, 182, 232, 0.14);
            border-color: rgba(77, 182, 232, 0.42);
        }

        .stButton > button {
            background: linear-gradient(135deg, #176b94, #124a66);
            color: white;
            border: 1px solid rgba(77, 182, 232, 0.55);
            border-radius: 8px;
            font-weight: 700;
        }

        .stButton > button:hover {
            border-color: var(--gp-accent);
            color: white;
            filter: brightness(1.08);
        }

        [data-testid="stDataFrame"] {
            background: rgba(13, 20, 29, 0.84);
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    """Render the branded application sidebar."""
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)

        st.markdown('<div class="gp-sidebar-title">GeoProfiler</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="gp-sidebar-meta">
                <strong>Base local</strong><br>
                data/crimes.csv<br><br>
                <strong>Modulos</strong><br>
                Cadastro | Mapa | Estatisticas | Analise
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("Ambiente analitico para triagem investigativa georreferenciada.")


def render_header() -> None:
    """Render the application header."""
    st.markdown(
        """
        <section class="gp-header">
            <div class="gp-header-kicker">Painel investigativo georreferenciado</div>
            <h1 class="gp-header-title">GeoProfiler</h1>
            <p class="gp-header-subtitle">
                Cadastro, mapa interativo, estatisticas e analise espacial de ocorrencias criminais.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_registration_form() -> None:
    """Render the manual crime registration form."""
    st.markdown("### Novo registro")

    with st.form("crime_registration_form", clear_on_submit=True):
        form_cols = st.columns(3)

        with form_cols[0]:
            tipo_crime = st.text_input("Tipo de crime", placeholder="Ex.: Furto")
            data = st.date_input("Data")
            hora = st.time_input("Hora")

        with form_cols[1]:
            latitude = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                value=-23.550520,
                format="%.6f",
            )
            longitude = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                value=-46.633308,
                format="%.6f",
            )
            cidade = st.text_input("Cidade", placeholder="Ex.: Sao Paulo")

        with form_cols[2]:
            bairro = st.text_input("Bairro", placeholder="Ex.: Centro")
            modus_operandi = st.text_area("Modus operandi", height=90)
            observacoes = st.text_area("Observacoes", height=90)

        submitted = st.form_submit_button("Salvar ocorrencia", use_container_width=True)

    if not submitted:
        return

    try:
        validate_registration(tipo_crime, latitude, longitude)
        save_crime_record(
            CrimeInput(
                tipo_crime=tipo_crime,
                data=data,
                hora=hora,
                latitude=latitude,
                longitude=longitude,
                cidade=cidade,
                bairro=bairro,
                modus_operandi=modus_operandi,
                observacoes=observacoes,
            )
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    st.success("Ocorrencia cadastrada com sucesso.")


def validate_registration(tipo_crime: str, latitude: float, longitude: float) -> None:
    """Validate required form fields before persistence."""
    if not tipo_crime.strip():
        raise ValueError("Informe o tipo de crime.")

    validate_coordinates(latitude, longitude)


def load_current_database() -> pd.DataFrame:
    """Load the current database and stop the app on schema errors."""
    try:
        return read_crime_database()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()


def render_dashboard(crimes: pd.DataFrame) -> None:
    """Render metrics, map, and table for registered crimes."""
    stats = calculate_basic_statistics(crimes)
    geo_analysis = run_geographic_analysis(crimes)
    statistical_dashboard = build_statistical_dashboard(crimes)

    st.markdown("### Visao operacional")
    metric_cols = st.columns(4)
    render_metric_card(
        metric_cols[0],
        label="Ocorrencias",
        value=str(stats.total_records),
        caption="Registros validos na base",
    )
    render_metric_card(
        metric_cols[1],
        label="Tipos de crime",
        value=str(stats.unique_crime_types),
        caption="Categorias distintas",
    )
    render_metric_card(
        metric_cols[2],
        label="Periodo",
        value=stats.date_range_label,
        caption="Janela temporal analisada",
    )
    render_metric_card(
        metric_cols[3],
        label="Celulas criticas",
        value=str(len(geo_analysis.critical_cells)),
        caption="Grade geografica ranqueada",
    )

    map_tab, stats_tab, analysis_tab, table_tab = st.tabs(
        ["⌖ Mapa", "▦ Estatisticas", "◎ Analise geografica", "≡ Registros"]
    )

    with map_tab:
        st.subheader("Mapa tatico de ocorrencias")
        crime_map = create_crime_map(crimes)
        st_folium(crime_map, width=None, height=520)

    with stats_tab:
        render_statistical_dashboard(statistical_dashboard)

    with analysis_tab:
        render_geographic_analysis(geo_analysis)

    with table_tab:
        st.subheader("Crimes cadastrados")
        st.dataframe(format_crime_table(crimes), use_container_width=True, hide_index=True)


def render_metric_card(column, label: str, value: str, caption: str) -> None:
    """Render a custom metric card in the given Streamlit column."""
    with column:
        st.markdown(
            f"""
            <div class="gp-metric-card">
                <div class="gp-metric-label">{label}</div>
                <div class="gp-metric-value">{value}</div>
                <div class="gp-metric-caption">{caption}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_statistical_dashboard(dashboard: StatisticalDashboard) -> None:
    """Render interactive statistical charts and frequency tables."""
    st.subheader("Dashboard estatistico")

    if dashboard.timeline.empty:
        st.warning("Cadastre crimes validos para gerar estatisticas.")
        return

    top_cols = st.columns(2)
    with top_cols[0]:
        crime_type_chart = px.bar(
            dashboard.crime_type_frequency,
            x="tipo_crime",
            y="total",
            text="total",
            title="Frequencia por tipo de crime",
            labels={"tipo_crime": "Tipo de crime", "total": "Ocorrencias"},
        )
        st.plotly_chart(style_chart(crime_type_chart), use_container_width=True)

    with top_cols[1]:
        district_chart = px.bar(
            dashboard.district_frequency,
            x="bairro",
            y="total",
            text="total",
            title="Frequencia por bairro",
            labels={"bairro": "Bairro", "total": "Ocorrencias"},
        )
        st.plotly_chart(style_chart(district_chart), use_container_width=True)

    middle_cols = st.columns(2)
    with middle_cols[0]:
        weekday_chart = px.bar(
            dashboard.weekday_frequency,
            x="dia_semana",
            y="total",
            text="total",
            title="Frequencia por dia da semana",
            labels={"dia_semana": "Dia da semana", "total": "Ocorrencias"},
        )
        st.plotly_chart(style_chart(weekday_chart), use_container_width=True)

    with middle_cols[1]:
        hour_chart = px.line(
            dashboard.hour_frequency,
            x="hora",
            y="total",
            markers=True,
            title="Frequencia por horario",
            labels={"hora": "Hora do dia", "total": "Ocorrencias"},
        )
        hour_chart.update_xaxes(dtick=1)
        st.plotly_chart(style_chart(hour_chart), use_container_width=True)

    timeline_chart = px.line(
        dashboard.timeline,
        x="data",
        y="total",
        markers=True,
        title="Linha do tempo dos crimes",
        labels={"data": "Data", "total": "Ocorrencias"},
    )
    st.plotly_chart(style_chart(timeline_chart), use_container_width=True)

    table_cols = st.columns(2)
    with table_cols[0]:
        st.markdown("#### Tipos de crime")
        st.dataframe(
            dashboard.crime_type_frequency,
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("#### Dias da semana")
        st.dataframe(
            dashboard.weekday_frequency,
            use_container_width=True,
            hide_index=True,
        )

    with table_cols[1]:
        st.markdown("#### Bairros")
        st.dataframe(
            dashboard.district_frequency,
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("#### Horarios")
        st.dataframe(
            dashboard.hour_frequency,
            use_container_width=True,
            hide_index=True,
        )


def style_chart(figure):
    """Apply consistent styling to Plotly figures."""
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(13, 20, 29, 0)",
        plot_bgcolor="rgba(13, 20, 29, 0.72)",
        font=dict(color="#e8f2f7"),
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
        title_font_size=18,
        title_font_color="#e8f2f7",
    )
    figure.update_xaxes(
        gridcolor="rgba(142, 166, 181, 0.16)",
        zerolinecolor="rgba(142, 166, 181, 0.22)",
    )
    figure.update_yaxes(
        gridcolor="rgba(142, 166, 181, 0.16)",
        zerolinecolor="rgba(142, 166, 181, 0.22)",
    )
    figure.update_traces(textposition="outside", selector=dict(type="bar"))
    return figure


def render_geographic_analysis(analysis: GeographicAnalysis) -> None:
    """Render geographic crime analysis tables and charts."""
    st.subheader("Analise geografica criminal")

    if analysis.distance_metrics is None or analysis.center is None:
        st.warning("Cadastre crimes validos para gerar a analise geografica.")
        return

    metrics = analysis.distance_metrics
    metric_cols = st.columns(4)
    metric_cols[0].metric(
        "Centro medio",
        f"{analysis.center.latitude:.5f}, {analysis.center.longitude:.5f}",
    )
    metric_cols[1].metric("Distancia media", f"{metrics.average_distance_km:.2f} km")
    metric_cols[2].metric("Desvio espacial", f"{metrics.spatial_std_km:.2f} km")
    metric_cols[3].metric("Celulas criticas", len(analysis.critical_cells))

    st.markdown("#### Crimes extremos")
    extreme_cols = st.columns(2)
    with extreme_cols[0]:
        st.write("Crime mais proximo do centro")
        st.dataframe(
            pd.DataFrame([metrics.nearest_crime]),
            use_container_width=True,
            hide_index=True,
        )

    with extreme_cols[1]:
        st.write("Crime mais distante do centro")
        st.dataframe(
            pd.DataFrame([metrics.farthest_crime]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Ranking das celulas mais criticas")
    ranking = format_grid_table(analysis.critical_cells)
    st.dataframe(ranking, use_container_width=True, hide_index=True)

    if not ranking.empty:
        critical_cells_chart = px.bar(
            ranking,
            x="celula",
            y="total_crimes",
            text="total_crimes",
            title="Concentracao por celula critica",
            labels={"celula": "Celula", "total_crimes": "Ocorrencias"},
        )
        st.plotly_chart(style_chart(critical_cells_chart), use_container_width=True)

    distance_table = format_distance_table(analysis.crimes_with_distances)
    st.markdown("#### Distancia de cada crime ate o centro")
    st.dataframe(distance_table, use_container_width=True, hide_index=True)

    if not distance_table.empty:
        distance_chart = px.line(
            distance_table,
            x="id",
            y="distancia_centro_km",
            markers=True,
            title="Distancia ao centro medio por crime",
            labels={"id": "ID", "distancia_centro_km": "Distancia ao centro (km)"},
        )
        st.plotly_chart(style_chart(distance_chart), use_container_width=True)

    st.markdown("#### Interpretacao automatica")
    for title, text in analysis.interpretation.items():
        st.write(f"**{format_interpretation_title(title)}**")
        st.write(text)


def format_crime_table(crimes: pd.DataFrame) -> pd.DataFrame:
    """Format the crime table for display."""
    display_data = crimes.copy()
    if not display_data.empty:
        display_data["data"] = display_data["data"].dt.strftime("%d/%m/%Y")

    return display_data


def format_grid_table(grid: pd.DataFrame) -> pd.DataFrame:
    """Format critical grid cells for display."""
    if grid.empty:
        return grid

    display_data = grid.copy()
    for column in [
        "latitude_min",
        "latitude_max",
        "longitude_min",
        "longitude_max",
        "centro_latitude",
        "centro_longitude",
    ]:
        display_data[column] = display_data[column].round(6)

    display_data["densidade_relativa"] = (
        display_data["densidade_relativa"] * 100
    ).round(2)

    return display_data[
        [
            "ranking",
            "celula",
            "total_crimes",
            "densidade_relativa",
            "centro_latitude",
            "centro_longitude",
            "bairros",
            "tipos_crime",
        ]
    ]


def format_distance_table(crimes: pd.DataFrame) -> pd.DataFrame:
    """Format crime distance table for display."""
    if crimes.empty:
        return crimes

    display_data = crimes.copy()
    display_data["data"] = display_data["data"].dt.strftime("%d/%m/%Y")
    display_data["distancia_centro_km"] = display_data["distancia_centro_km"].round(3)

    return display_data[
        [
            "id",
            "tipo_crime",
            "data",
            "bairro",
            "latitude",
            "longitude",
            "distancia_centro_km",
        ]
    ]


def format_interpretation_title(value: str) -> str:
    """Convert interpretation keys into readable labels."""
    labels = {
        "possivel_zona_atuacao": "Possivel zona de atuacao",
        "area_maior_concentracao": "Area de maior concentracao",
        "hipotese_zona_conforto": "Hipotese de zona de conforto",
        "limitacoes_analise": "Limitacoes da analise",
        "dispersao_espacial": "Dispersao espacial",
    }
    return labels.get(value, value.replace("_", " ").title())


if __name__ == "__main__":
    main()
