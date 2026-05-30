"""GeoProfiler Streamlit application entry point."""

from __future__ import annotations

import base64
from html import escape
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
from src.geo_analysis import GeographicAnalysis, ProfileZone, run_geographic_analysis
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
    theme = render_sidebar()
    inject_global_styles(theme)
    render_header()
    render_registration_form()

    crimes = load_current_database()
    render_dashboard(crimes, theme)


def render_sidebar() -> str:
    """Render the branded application sidebar and return the selected theme."""
    with st.sidebar:
        render_logo()
        st.markdown('<div class="gp-sidebar-title">GeoProfiler</div>', unsafe_allow_html=True)
        st.caption("Ferramenta de apoio ao perfilamento geográfico criminal.")

        selected_theme = st.radio(
            "Tema da interface",
            options=["Escuro", "Claro"],
            horizontal=True,
            index=0,
        )

        st.markdown(
            """
            <div class="gp-sidebar-meta">
                <strong>Base local</strong><br>
                data/crimes.csv<br><br>
                <strong>Módulos</strong><br>
                Cadastro | Mapa | Estatísticas | Perfilamento
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("Os resultados são hipóteses investigativas, não conclusões periciais.")

    return "light" if selected_theme == "Claro" else "dark"


def render_logo() -> None:
    """Render the transparent logo inside a fixed white container."""
    if not LOGO_PATH.exists():
        return

    encoded_logo = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <div class="gp-logo-frame">
            <img src="data:image/png;base64,{encoded_logo}" alt="GeoProfiler">
        </div>
        """,
        unsafe_allow_html=True,
    )


def inject_global_styles(theme: str) -> None:
    """Inject theme-aware investigative interface styles."""
    palette = get_theme_palette(theme)
    st.markdown(
        f"""
        <style>
        :root {{
            --gp-bg: {palette["bg"]};
            --gp-bg-soft: {palette["bg_soft"]};
            --gp-surface: {palette["surface"]};
            --gp-surface-2: {palette["surface_2"]};
            --gp-border: {palette["border"]};
            --gp-text: {palette["text"]};
            --gp-muted: {palette["muted"]};
            --gp-accent: {palette["accent"]};
            --gp-accent-2: {palette["accent_2"]};
            --gp-shadow: {palette["shadow"]};
        }}

        .stApp {{
            background: var(--gp-bg);
            color: var(--gp-text);
        }}

        .block-container {{
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1480px;
        }}

        [data-testid="stSidebar"] {{
            background: var(--gp-bg-soft);
            border-right: 1px solid var(--gp-border);
        }}

        h1, h2, h3, h4, h5, h6, p, label, span {{
            letter-spacing: 0;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: var(--gp-text);
        }}

        .gp-logo-frame {{
            background: #ffffff;
            border: 1px solid #d6dde5;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 14px;
            box-shadow: var(--gp-shadow);
        }}

        .gp-logo-frame img {{
            display: block;
            width: 100%;
            border-radius: 6px;
        }}

        .gp-sidebar-title {{
            color: var(--gp-text);
            font-size: 1.18rem;
            font-weight: 800;
            margin: 8px 0 4px;
        }}

        .gp-sidebar-meta {{
            color: var(--gp-muted);
            font-size: 0.88rem;
            line-height: 1.5;
            padding: 12px;
            border: 1px solid var(--gp-border);
            border-radius: 8px;
            background: var(--gp-surface);
            box-shadow: var(--gp-shadow);
        }}

        .gp-header {{
            border: 1px solid var(--gp-border);
            background: linear-gradient(135deg, var(--gp-surface), var(--gp-surface-2));
            border-radius: 8px;
            padding: 22px 24px;
            margin-bottom: 18px;
            box-shadow: var(--gp-shadow);
        }}

        .gp-header-kicker {{
            color: var(--gp-accent);
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}

        .gp-header-title {{
            color: var(--gp-text);
            font-size: 2.12rem;
            line-height: 1.1;
            font-weight: 820;
            margin: 0 0 8px 0;
        }}

        .gp-header-subtitle {{
            color: var(--gp-muted);
            font-size: 1rem;
            margin: 0;
        }}

        .gp-card, .gp-metric-card, .gp-report-card, .gp-zone-card {{
            border: 1px solid var(--gp-border);
            background: var(--gp-surface);
            border-radius: 8px;
            box-shadow: var(--gp-shadow);
        }}

        .gp-metric-card {{
            padding: 16px;
            min-height: 124px;
        }}

        .gp-metric-icon {{
            color: var(--gp-accent);
            font-size: 1.25rem;
            margin-bottom: 8px;
        }}

        .gp-metric-label {{
            color: var(--gp-muted);
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}

        .gp-metric-value {{
            color: var(--gp-text);
            font-size: 1.55rem;
            font-weight: 820;
            line-height: 1.15;
            overflow-wrap: anywhere;
        }}

        .gp-metric-caption {{
            color: var(--gp-accent);
            font-size: 0.82rem;
            margin-top: 8px;
        }}

        .gp-zone-card, .gp-report-card {{
            padding: 16px;
            margin-bottom: 14px;
        }}

        .gp-card-title {{
            color: var(--gp-text);
            font-weight: 820;
            font-size: 1.02rem;
            margin-bottom: 8px;
        }}

        .gp-card-body {{
            color: var(--gp-muted);
            font-size: 0.93rem;
            line-height: 1.55;
        }}

        .gp-badge {{
            display: inline-block;
            border: 1px solid var(--gp-border);
            background: var(--gp-surface-2);
            color: var(--gp-accent);
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 0.78rem;
            font-weight: 800;
            margin-bottom: 8px;
        }}

        [data-testid="stForm"] {{
            background: var(--gp-surface);
            border: 1px solid var(--gp-border);
            border-radius: 8px;
            padding: 18px;
            box-shadow: var(--gp-shadow);
        }}

        [data-baseweb="input"],
        [data-baseweb="textarea"],
        [data-baseweb="select"],
        .stTextInput input,
        .stNumberInput input,
        .stTextArea textarea {{
            background-color: var(--gp-surface-2) !important;
            color: var(--gp-text) !important;
            border-color: var(--gp-border) !important;
        }}

        [data-baseweb="radio"] div,
        [data-baseweb="radio"] label,
        [data-testid="stWidgetLabel"] {{
            color: var(--gp-text) !important;
        }}

        [data-testid="stMarkdownContainer"],
        [data-testid="stCaptionContainer"] {{
            color: var(--gp-text);
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            border-bottom: 1px solid var(--gp-border);
        }}

        .stTabs [data-baseweb="tab"] {{
            background: var(--gp-surface);
            border: 1px solid var(--gp-border);
            border-radius: 8px 8px 0 0;
            color: var(--gp-muted);
            padding: 10px 14px;
            font-weight: 700;
        }}

        .stTabs [aria-selected="true"] {{
            color: var(--gp-text);
            background: var(--gp-surface-2);
            border-color: var(--gp-accent);
        }}

        .stButton > button {{
            background: linear-gradient(135deg, var(--gp-accent), #14527a);
            color: white;
            border: 1px solid var(--gp-accent);
            border-radius: 8px;
            font-weight: 800;
        }}

        .stButton > button:hover {{
            color: white;
            filter: brightness(1.08);
        }}

        [data-testid="stDataFrame"] {{
            background: var(--gp-surface);
            border: 1px solid var(--gp-border);
            border-radius: 8px;
            box-shadow: var(--gp-shadow);
        }}

        .stAlert {{
            border-radius: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_theme_palette(theme: str) -> dict[str, str]:
    """Return CSS palette values for the selected theme."""
    if theme == "light":
        return {
            "bg": "#f4f7fb",
            "bg_soft": "#eaf0f7",
            "surface": "#ffffff",
            "surface_2": "#eef5fb",
            "border": "rgba(23, 60, 86, 0.16)",
            "text": "#17212b",
            "muted": "#51606a",
            "accent": "#0b5ed7",
            "accent_2": "#b4232a",
            "shadow": "0 12px 28px rgba(23, 60, 86, 0.10)",
        }

    return {
        "bg": "#070b10",
        "bg_soft": "#07101a",
        "surface": "#0d141d",
        "surface_2": "#111c28",
        "border": "rgba(116, 178, 214, 0.18)",
        "text": "#e8f2f7",
        "muted": "#8ea6b5",
        "accent": "#4db6e8",
        "accent_2": "#e2565b",
        "shadow": "0 18px 48px rgba(0, 0, 0, 0.28)",
    }


def render_header() -> None:
    """Render the application header."""
    st.markdown(
        """
        <section class="gp-header">
            <div class="gp-header-kicker">Painel investigativo georreferenciado</div>
            <h1 class="gp-header-title">GeoProfiler</h1>
            <p class="gp-header-subtitle">
                Ferramenta de apoio ao Perfilamento Geográfico Criminal com mapa,
                estatísticas, análise espacial e hipóteses investigativas.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_registration_form() -> None:
    """Render the manual crime registration form."""
    st.markdown("### Novo registro de ocorrência")

    with st.form("crime_registration_form", clear_on_submit=True):
        form_cols = st.columns(3)

        with form_cols[0]:
            tipo_crime = st.text_input("Tipo de crime", placeholder="Ex.: Roubo")
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
            cidade = st.text_input("Cidade", placeholder="Ex.: São Paulo")

        with form_cols[2]:
            bairro = st.text_input("Bairro", placeholder="Ex.: Centro")
            modus_operandi = st.text_area("Modus operandi", height=90)
            observacoes = st.text_area("Observações", height=90)

        submitted = st.form_submit_button("Salvar ocorrência", use_container_width=True)

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

    st.success("Ocorrência cadastrada com sucesso.")


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


def render_dashboard(crimes: pd.DataFrame, theme: str) -> None:
    """Render metrics, map, profiling, statistics, and registered crimes."""
    stats = calculate_basic_statistics(crimes)
    geo_analysis = run_geographic_analysis(crimes)
    statistical_dashboard = build_statistical_dashboard(crimes)

    st.markdown("### Visão operacional")
    metric_cols = st.columns(4)
    render_metric_card(metric_cols[0], "◆", "Ocorrências", str(stats.total_records), "Registros válidos")
    render_metric_card(metric_cols[1], "▣", "Tipos de crime", str(stats.unique_crime_types), "Categorias distintas")
    render_metric_card(metric_cols[2], "◷", "Período", stats.date_range_label, "Janela temporal")
    render_metric_card(metric_cols[3], "◎", "Células críticas", str(len(geo_analysis.critical_cells)), "Grade ranqueada")

    map_tab, profile_tab, stats_tab, table_tab = st.tabs(
        ["Mapa", "Perfilamento", "Estatísticas", "Registros"]
    )

    with map_tab:
        st.subheader("Mapa tático de ocorrências")
        crime_map = create_crime_map(crimes, geo_analysis)
        st_folium(crime_map, width=None, height=560)

    with profile_tab:
        render_geographic_profiling_panel(geo_analysis, theme)

    with stats_tab:
        render_statistical_dashboard(statistical_dashboard, theme)

    with table_tab:
        st.subheader("Crimes cadastrados")
        st.dataframe(format_crime_table(crimes), use_container_width=True, hide_index=True)


def render_metric_card(column, icon: str, label: str, value: str, caption: str) -> None:
    """Render a custom metric card in the given Streamlit column."""
    with column:
        st.markdown(
            f"""
            <div class="gp-metric-card">
                <div class="gp-metric-icon">{escape(icon)}</div>
                <div class="gp-metric-label">{escape(label)}</div>
                <div class="gp-metric-value">{escape(value)}</div>
                <div class="gp-metric-caption">{escape(caption)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_statistical_dashboard(dashboard: StatisticalDashboard, theme: str) -> None:
    """Render interactive statistical charts and frequency tables."""
    st.subheader("Dashboard estatístico")

    if dashboard.timeline.empty:
        st.warning("Cadastre crimes válidos para gerar estatísticas.")
        return

    top_cols = st.columns(2)
    with top_cols[0]:
        crime_type_chart = px.bar(
            dashboard.crime_type_frequency,
            x="tipo_crime",
            y="total",
            text="total",
            title="Frequência por tipo de crime",
            labels={"tipo_crime": "Tipo de crime", "total": "Ocorrências"},
        )
        st.plotly_chart(style_chart(crime_type_chart, theme), use_container_width=True)

    with top_cols[1]:
        district_chart = px.bar(
            dashboard.district_frequency,
            x="bairro",
            y="total",
            text="total",
            title="Frequência por bairro",
            labels={"bairro": "Bairro", "total": "Ocorrências"},
        )
        st.plotly_chart(style_chart(district_chart, theme), use_container_width=True)

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
        st.plotly_chart(style_chart(weekday_chart, theme), use_container_width=True)

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
        st.plotly_chart(style_chart(hour_chart, theme), use_container_width=True)

    timeline_chart = px.line(
        dashboard.timeline,
        x="data",
        y="total",
        markers=True,
        title="Linha do tempo dos crimes",
        labels={"data": "Data", "total": "Ocorrências"},
    )
    st.plotly_chart(style_chart(timeline_chart, theme), use_container_width=True)

    table_cols = st.columns(2)
    with table_cols[0]:
        st.markdown("#### Tipos de crime")
        st.dataframe(format_frequency_table(dashboard.crime_type_frequency, "Tipo de crime"), use_container_width=True, hide_index=True)
        st.markdown("#### Dias da semana")
        st.dataframe(format_frequency_table(dashboard.weekday_frequency, "Dia da semana"), use_container_width=True, hide_index=True)

    with table_cols[1]:
        st.markdown("#### Bairros")
        st.dataframe(format_frequency_table(dashboard.district_frequency, "Bairro"), use_container_width=True, hide_index=True)
        st.markdown("#### Horários")
        st.dataframe(format_frequency_table(dashboard.hour_frequency, "Hora"), use_container_width=True, hide_index=True)


def render_geographic_profiling_panel(analysis: GeographicAnalysis, theme: str) -> None:
    """Render the V2 geographic profiling intelligence panel."""
    st.subheader("PAINEL DE PERFILAMENTO GEOGRÁFICO")

    if analysis.distance_metrics is None or analysis.center is None:
        st.warning("Cadastre crimes válidos para gerar o painel de perfilamento.")
        return

    metrics = analysis.distance_metrics
    metric_cols = st.columns(4)
    render_metric_card(
        metric_cols[0],
        "★",
        "CGC",
        f"{analysis.center.latitude:.5f}, {analysis.center.longitude:.5f}",
        "Centro de Gravidade Criminal",
    )
    render_metric_card(metric_cols[1], "⌁", "Distância média", f"{metrics.average_distance_km:.2f} km", "Raio operacional médio")
    render_metric_card(metric_cols[2], "⇄", "Desvio espacial", f"{metrics.spatial_std_km:.2f} km", "Dispersão territorial")
    render_metric_card(metric_cols[3], "◉", "Hipótese", analysis.offender_classification.category, f"{analysis.offender_classification.confidence:.1f}% de confiança")

    zone_cols = st.columns(3)
    render_zone_card(zone_cols[0], analysis.comfort_zone)
    render_zone_card(zone_cols[1], analysis.operations_base)
    render_zone_card(zone_cols[2], analysis.security_zone)

    st.markdown("#### Relatório de inteligência geográfica")
    for title, text in analysis.interpretation.items():
        render_report_card(format_interpretation_title(title), text)

    st.markdown("#### Evidências espaciais")
    evidence_cols = st.columns(2)
    with evidence_cols[0]:
        st.write("Crime mais próximo do CGC")
        st.dataframe(pd.DataFrame([metrics.nearest_crime]), use_container_width=True, hide_index=True)
    with evidence_cols[1]:
        st.write("Crime mais distante do CGC")
        st.dataframe(pd.DataFrame([metrics.farthest_crime]), use_container_width=True, hide_index=True)

    ranking = format_grid_table(analysis.critical_cells)
    st.markdown("#### Ranking das células críticas")
    st.dataframe(ranking, use_container_width=True, hide_index=True)
    if not ranking.empty:
        critical_cells_chart = px.bar(
            ranking,
            x="Célula",
            y="Total de crimes",
            text="Total de crimes",
            title="Concentração por célula crítica",
        )
        st.plotly_chart(style_chart(critical_cells_chart, theme), use_container_width=True)

    distance_table = format_distance_table(analysis.crimes_with_distances)
    st.markdown("#### Distância de cada crime até o CGC")
    st.dataframe(distance_table, use_container_width=True, hide_index=True)
    if not distance_table.empty:
        distance_chart = px.line(
            distance_table,
            x="ID",
            y="Distância até o CGC (km)",
            markers=True,
            title="Distância ao Centro de Gravidade Criminal por ocorrência",
        )
        st.plotly_chart(style_chart(distance_chart, theme), use_container_width=True)


def render_zone_card(column, zone: ProfileZone) -> None:
    """Render a geographic profiling zone card."""
    center = "Indisponível"
    if zone.center is not None:
        center = f"{zone.center.latitude:.6f}, {zone.center.longitude:.6f}"

    with column:
        st.markdown(
            f"""
            <div class="gp-zone-card">
                <div class="gp-badge">{escape(zone.title)}</div>
                <div class="gp-card-title">Raio estimado: {zone.radius_km:.2f} km</div>
                <div class="gp-card-body">
                    <strong>Coordenadas:</strong> {escape(center)}<br><br>
                    {escape(zone.description)}<br><br>
                    <strong>Justificativa:</strong> {escape(zone.evidence)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_report_card(title: str, text: str) -> None:
    """Render one intelligence report section."""
    st.markdown(
        f"""
        <div class="gp-report-card">
            <div class="gp-card-title">{escape(title)}</div>
            <div class="gp-card-body">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_chart(figure, theme: str):
    """Apply consistent styling to Plotly figures."""
    if theme == "light":
        template = "plotly_white"
        paper = "rgba(255,255,255,0)"
        plot = "rgba(255,255,255,0.92)"
        font = "#17212b"
        grid = "rgba(23, 60, 86, 0.13)"
    else:
        template = "plotly_dark"
        paper = "rgba(13, 20, 29, 0)"
        plot = "rgba(13, 20, 29, 0.72)"
        font = "#e8f2f7"
        grid = "rgba(142, 166, 181, 0.16)"

    figure.update_layout(
        template=template,
        paper_bgcolor=paper,
        plot_bgcolor=plot,
        font=dict(color=font),
        margin=dict(l=20, r=20, t=60, b=24),
        hovermode="x unified",
        title_font_size=18,
        title_font_color=font,
        colorway=["#0b5ed7", "#e2565b", "#2ca25f", "#f0ad4e", "#6f42c1"],
    )
    figure.update_xaxes(gridcolor=grid, zerolinecolor=grid)
    figure.update_yaxes(gridcolor=grid, zerolinecolor=grid)
    figure.update_traces(textposition="outside", selector=dict(type="bar"))
    return figure


def format_crime_table(crimes: pd.DataFrame) -> pd.DataFrame:
    """Format the crime table for display."""
    display_data = crimes.copy()
    if not display_data.empty:
        display_data["data"] = display_data["data"].dt.strftime("%d/%m/%Y")

    return display_data.rename(
        columns={
            "id": "ID",
            "tipo_crime": "Tipo de crime",
            "data": "Data",
            "hora": "Hora",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "cidade": "Cidade",
            "bairro": "Bairro",
            "modus_operandi": "Modus operandi",
            "observacoes": "Observações",
        }
    )


def format_frequency_table(data: pd.DataFrame, first_column_label: str) -> pd.DataFrame:
    """Format a frequency table for display."""
    if data.empty:
        return data

    display_data = data.copy()
    first_column = display_data.columns[0]
    display_data = display_data.rename(
        columns={
            first_column: first_column_label,
            "total": "Total",
            "percentual": "Percentual (%)",
        }
    )
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

    display_data["densidade_relativa"] = (display_data["densidade_relativa"] * 100).round(2)

    display_data = display_data.rename(
        columns={
            "ranking": "Ranking",
            "celula": "Célula",
            "total_crimes": "Total de crimes",
            "densidade_relativa": "Densidade relativa (%)",
            "centro_latitude": "Latitude central",
            "centro_longitude": "Longitude central",
            "bairros": "Bairros",
            "tipos_crime": "Tipos de crime",
        }
    )

    return display_data[
        [
            "Ranking",
            "Célula",
            "Total de crimes",
            "Densidade relativa (%)",
            "Latitude central",
            "Longitude central",
            "Bairros",
            "Tipos de crime",
        ]
    ]


def format_distance_table(crimes: pd.DataFrame) -> pd.DataFrame:
    """Format crime distance table for display."""
    if crimes.empty:
        return crimes

    display_data = crimes.copy()
    display_data["data"] = display_data["data"].dt.strftime("%d/%m/%Y")
    display_data["distancia_centro_km"] = display_data["distancia_centro_km"].round(3)
    display_data = display_data.rename(
        columns={
            "id": "ID",
            "tipo_crime": "Tipo de crime",
            "data": "Data",
            "bairro": "Bairro",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "distancia_centro_km": "Distância até o CGC (km)",
        }
    )

    return display_data[
        [
            "ID",
            "Tipo de crime",
            "Data",
            "Bairro",
            "Latitude",
            "Longitude",
            "Distância até o CGC (km)",
        ]
    ]


def format_interpretation_title(value: str) -> str:
    """Convert interpretation keys into readable labels."""
    labels = {
        "resumo_executivo": "Resumo Executivo",
        "padrao_espacial_identificado": "Padrão Espacial Identificado",
        "centro_gravidade_criminal": "Centro de Gravidade Criminal (CGC)",
        "zona_de_conforto": "Zona de Conforto",
        "base_de_operacoes": "Base de Operações",
        "zona_de_seguranca": "Zona de Segurança",
        "classificacao_geografica": "Classificação Marauder ou Commuter",
        "hipoteses_investigativas": "Hipóteses Investigativas",
        "limitacoes_metodologicas": "Limitações Metodológicas",
    }
    return labels.get(value, value.replace("_", " ").title())


if __name__ == "__main__":
    main()
