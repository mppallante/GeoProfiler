"""Shared chrome, formatting, and case-loading helpers used across GeoProfiler pages."""

from __future__ import annotations

import base64
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_manager import Caso, get_caso, read_case_crimes
from src.db import DB_PATH

LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"


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

        active_caso_id = st.session_state.get("active_caso_id")
        active_caso = get_caso(active_caso_id) if active_caso_id else None
        caso_label = escape(active_caso.nome) if active_caso else "Nenhum caso selecionado"

        st.markdown(
            f"""
            <div class="gp-sidebar-meta">
                <strong>Caso ativo</strong><br>
                {caso_label}<br><br>
                <strong>Base local</strong><br>
                SQLite (múltiplos casos)<br><br>
                <strong>Módulos</strong><br>
                Casos | Mapa | Estatísticas | Análise Automatizada
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


def render_header() -> None:
    """Render the application header banner."""
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


def render_case_header(caso: Caso) -> None:
    """Render a compact header identifying the active case."""
    description = escape(caso.descricao) if caso.descricao else "Sem descrição."
    st.markdown(
        f"""
        <section class="gp-header">
            <div class="gp-header-kicker">Caso ativo</div>
            <h2 class="gp-header-title" style="font-size:1.6rem;">{escape(caso.nome)}</h2>
            <p class="gp-header-subtitle">{description}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def require_active_case() -> Caso:
    """Return the active case, or stop the page prompting the user to pick one."""
    caso_id = st.session_state.get("active_caso_id")
    caso = get_caso(caso_id) if caso_id is not None else None

    if caso is None:
        st.session_state.pop("active_caso_id", None)
        st.warning("Selecione um caso para continuar.")
        st.page_link("src/pages/casos.py", label="Ir para Casos")
        st.stop()

    return caso


@st.cache_data(show_spinner=False)
def _cached_read_case_crimes(caso_id: int, db_mtime: float) -> pd.DataFrame:
    return read_case_crimes(caso_id)


def load_case_crimes(caso_id: int) -> pd.DataFrame:
    """Load a case's crimes, cached until the database file changes on disk."""
    db_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0
    return _cached_read_case_crimes(caso_id, db_mtime)


def filter_crimes_by_date_range(crimes: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Keep only crimes whose `data` falls within [start, end], inclusive."""
    if crimes.empty:
        return crimes

    mask = crimes["data"].dt.date.between(start, end)
    return crimes[mask].reset_index(drop=True)


def render_date_range_filter(caso: Caso, crimes: pd.DataFrame) -> pd.DataFrame:
    """Render a shared date-range control and return the filtered crimes.

    The selection is persisted in a plain session_state entry scoped per case
    id (not via the date_input widget's own `key`, since Streamlit's
    multipage `st.Page` navigation does not reliably carry widget state
    across separate page scripts even when the same key string is reused).
    Switching cases starts fresh at the new case's full span; the selection
    persists across Mapa/Estatísticas/Análise Automatizada for the same case
    because this function itself reads/writes the same session_state entry
    on every page.
    """
    if crimes.empty:
        return crimes

    min_date = crimes["data"].min().date()
    max_date = crimes["data"].max().date()
    state_key = f"date_range_filter_{caso.id}"

    stored = st.session_state.get(state_key, (min_date, max_date))
    default_start = max(stored[0], min_date)
    default_end = min(stored[1], max_date)
    if default_start > default_end:
        default_start, default_end = min_date, max_date

    selected = st.date_input(
        "Período de análise",
        value=(default_start, default_end),
        min_value=min_date,
        max_value=max_date,
        help="Filtra as ocorrências usadas no mapa, nas estatísticas e na análise automatizada deste caso.",
    )

    if isinstance(selected, tuple) and len(selected) == 2:
        start, end = selected
        st.session_state[state_key] = (start, end)
    else:
        # Mid-selection (user has only picked one endpoint so far): don't
        # narrow anything this run, wait for a complete range.
        start, end = default_start, default_end

    filtered = filter_crimes_by_date_range(crimes, start, end)
    if filtered.empty:
        st.warning("Nenhuma ocorrência no período selecionado. Ajuste o intervalo de datas.")
    elif (start, end) != (min_date, max_date):
        st.caption(f"{len(filtered)} de {len(crimes)} ocorrência(s) no período selecionado.")

    return filtered


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


def format_neighborhood_zones_table(zones: pd.DataFrame) -> pd.DataFrame:
    """Format the per-neighborhood comfort/transition zone table for display."""
    if zones.empty:
        return zones

    display_data = zones.rename(
        columns={
            "bairro": "Bairro",
            "total_crimes": "Total de crimes",
            "distancia_media_km": "Distância média ao CGC (km)",
            "classificacao": "Classificação",
        }
    )

    return display_data[
        ["Bairro", "Total de crimes", "Distância média ao CGC (km)", "Classificação"]
    ]


def format_distance_table(crimes: pd.DataFrame) -> pd.DataFrame:
    """Format crime distance table for display."""
    if crimes.empty:
        return crimes

    display_data = crimes.copy()
    display_data["data"] = display_data["data"].dt.strftime("%d/%m/%Y")
    display_data["distancia_centro_km"] = display_data["distancia_centro_km"].round(3)
    if "dentro_zona_buffer" in display_data.columns:
        display_data["dentro_zona_buffer"] = display_data["dentro_zona_buffer"].map(
            {True: "Sim", False: "Não"}
        )
    display_data = display_data.rename(
        columns={
            "id": "ID",
            "tipo_crime": "Tipo de crime",
            "data": "Data",
            "bairro": "Bairro",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "distancia_centro_km": "Distância até o CGC (km)",
            "dentro_zona_buffer": "Dentro da zona de buffer",
        }
    )

    columns = [
        "ID",
        "Tipo de crime",
        "Data",
        "Bairro",
        "Latitude",
        "Longitude",
        "Distância até o CGC (km)",
    ]
    if "Dentro da zona de buffer" in display_data.columns:
        columns.append("Dentro da zona de buffer")

    return display_data[columns]


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
        "zona_de_buffer": "Zona de Buffer",
        "perfil_rossmo": "Perfil de Rossmo (CGT)",
        "barreiras_geograficas": "Barreiras Geográficas",
        "hipoteses_investigativas": "Hipóteses Investigativas",
        "limitacoes_metodologicas": "Limitações Metodológicas",
    }
    return labels.get(value, value.replace("_", " ").title())
