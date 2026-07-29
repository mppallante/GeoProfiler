"""Shared chrome, formatting, and case-loading helpers used across GeoProfiler pages."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_manager import Caso, get_caso, read_case_crimes
from src.db import DB_PATH

LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"

DENSITY_LABELS = ["Confortável", "Compacta"]
DENSITY_KEYS = {"Confortável": "confortavel", "Compacta": "compacta"}


@dataclass(frozen=True)
class UISettings:
    """Interface preferences selected in the sidebar, threaded through every page."""

    density: str  # "confortavel" | "compacta"
    show_hypothesis: bool


def render_sidebar() -> UISettings:
    """Render the branded application sidebar and return the selected UI settings."""
    with st.sidebar:
        render_logo()
        st.markdown('<div class="gp-sidebar-title">GeoProfiler</div>', unsafe_allow_html=True)
        st.caption("Ferramenta de apoio ao perfilamento geográfico criminal.")

        st.markdown('<div class="gp-sidebar-section-label">Aparência</div>', unsafe_allow_html=True)
        selected_density = st.radio(
            "Densidade",
            options=DENSITY_LABELS,
            horizontal=True,
            index=0,
        )

        st.markdown('<div class="gp-sidebar-section-label">Análise</div>', unsafe_allow_html=True)
        show_hypothesis = st.checkbox(
            "Exibir hipótese e Círculo de Canter",
            value=True,
            help="Mostra o KPI de hipótese investigativa e o diagrama do Círculo de Canter na Análise Automatizada.",
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

    return UISettings(
        density=DENSITY_KEYS[selected_density],
        show_hypothesis=show_hypothesis,
    )


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
            <h2 class="gp-header-title" style="font-size:28px;">{escape(caso.nome)}</h2>
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


DENSITY_TOKENS = {
    "confortavel": {"outer": "36px", "card": "20px", "gap": "16px"},
    "compacta": {"outer": "22px", "card": "14px", "gap": "10px"},
}


def inject_global_styles(settings: UISettings) -> None:
    """Inject the (light-only) glass investigative interface styles, density-aware."""
    palette = get_theme_palette()
    density = DENSITY_TOKENS[settings.density]

    glass_finish = """
    .gp-card, .gp-metric-card, .gp-zone-card, .gp-report-card,
    [data-testid="stForm"], [data-testid="stDataFrame"] {
        background: var(--gp-glass);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--gp-glass-border);
        box-shadow: var(--gp-shadow-card);
    }
    [data-testid="stSidebar"], [data-testid="stMain"] > div {
        background: var(--gp-glass-shell);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
    }
    """

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

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
            --gp-amber: {palette["amber"]};
            --gp-shadow-card: {palette["shadow_card"]};
            --gp-shadow-shell: {palette["shadow_shell"]};
            --gp-glass: {palette["glass"]};
            --gp-glass-border: {palette["glass_border"]};
            --gp-glass-shell: {palette["glass_shell"]};
            --gp-radius-chip: 12px;
            --gp-radius-input: 14px;
            --gp-radius-card: 20px;
            --gp-radius-shell: 22px;
            --gp-radius-pill: 999px;
            --gp-pad-outer: {density["outer"]};
            --gp-pad-card: {density["card"]};
            --gp-gap: {density["gap"]};
            --gp-font-sans: 'IBM Plex Sans', 'Source Sans Pro', sans-serif;
            --gp-font-display: var(--gp-font-sans);
            --gp-font-mono: 'IBM Plex Mono', ui-monospace, 'Cascadia Code', 'Roboto Mono', Menlo, Consolas, monospace;
        }}

        .stApp {{
            background: var(--gp-bg);
            color: var(--gp-text);
            font-family: var(--gp-font-sans);
        }}

        [data-testid="stAppViewContainer"] {{
            gap: 16px;
        }}

        .block-container, [data-testid="stMainBlockContainer"] {{
            padding-top: var(--gp-pad-outer);
            padding-bottom: var(--gp-pad-outer);
            padding-left: var(--gp-pad-outer);
            padding-right: var(--gp-pad-outer);
            max-width: 1480px;
        }}

        [data-testid="stHorizontalBlock"] {{
            gap: var(--gp-gap);
        }}

        [data-testid="stSidebar"] {{
            width: 272px !important;
            min-width: 272px !important;
            max-width: 272px !important;
            border: 1px solid var(--gp-glass-border);
            border-radius: var(--gp-radius-shell);
            margin: 16px 0 16px 16px;
            box-shadow: var(--gp-shadow-shell);
            overflow: hidden;
        }}

        [data-testid="stSidebarResizeHandle"] {{
            display: none;
        }}

        [data-testid="stSidebar"] > div {{
            padding: 18px 14px;
        }}

        [data-testid="stMain"] {{
            margin: 16px 16px 16px 0;
        }}

        [data-testid="stMain"] > div {{
            border: 1px solid var(--gp-glass-border);
            border-radius: var(--gp-radius-shell);
            box-shadow: var(--gp-shadow-shell);
        }}

        [data-testid="stSidebarNav"] {{
            padding: 4px 4px 8px 4px;
        }}

        [data-testid="stNavSectionHeader"] p {{
            color: var(--gp-muted) !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        [data-testid="stSidebarNavLink"] {{
            border-radius: var(--gp-radius-pill);
            border: 1px solid transparent;
            margin: 2px 8px;
            color: var(--gp-text) !important;
            font-weight: 500;
            transition: background 0.15s;
        }}

        [data-testid="stSidebarNavLink"][aria-current="page"] {{
            background: color-mix(in srgb, var(--gp-accent) 14%, transparent) !important;
            border: 1px solid color-mix(in srgb, var(--gp-accent) 28%, transparent);
        }}

        [data-testid="stSidebarNavLink"][aria-current="page"] p {{
            color: var(--gp-accent) !important;
            font-weight: 700 !important;
        }}

        h1, h2, h3, h4, h5, h6, p, label, span {{
            letter-spacing: 0;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: var(--gp-text);
            font-family: var(--gp-font-sans);
        }}

        .gp-sidebar-section-label {{
            color: var(--gp-muted);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 14px 0 4px;
        }}

        .gp-logo-frame {{
            background: #ffffff;
            border: 1px solid #d6dde5;
            border-radius: var(--gp-radius-chip);
            padding: 12px;
            margin-bottom: 14px;
            box-shadow: var(--gp-shadow-card);
        }}

        .gp-logo-frame img {{
            display: block;
            width: 100%;
            border-radius: 6px;
        }}

        .gp-sidebar-title {{
            color: var(--gp-text);
            font-size: 16px;
            font-weight: 700;
            margin: 8px 0 4px;
        }}

        .gp-sidebar-meta {{
            color: var(--gp-muted);
            font-size: 14px;
            line-height: 1.5;
            padding: 12px;
            border: 1px solid var(--gp-border);
            border-radius: var(--gp-radius-chip);
            background: var(--gp-surface);
            box-shadow: var(--gp-shadow-card);
        }}

        .gp-header {{
            border: 1px solid var(--gp-border);
            background: linear-gradient(135deg, var(--gp-surface), var(--gp-surface-2));
            border-radius: var(--gp-radius-card);
            padding: var(--gp-pad-card) 24px;
            margin-bottom: 18px;
            box-shadow: var(--gp-shadow-card);
        }}

        .gp-header-kicker {{
            color: var(--gp-accent);
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}

        .gp-header .gp-header-title {{
            color: var(--gp-text);
            font-family: var(--gp-font-display);
            font-size: 30px;
            line-height: 1.15;
            font-weight: 700;
            margin: 0 0 8px 0;
        }}

        .gp-header-subtitle {{
            color: var(--gp-muted);
            font-size: 15px;
            margin: 0;
        }}

        .gp-card, .gp-metric-card, .gp-report-card, .gp-zone-card {{
            border: 1px solid var(--gp-border);
            background: var(--gp-surface);
            border-radius: var(--gp-radius-card);
            box-shadow: var(--gp-shadow-card);
        }}

        .gp-card {{
            padding: var(--gp-pad-card);
        }}

        .gp-metric-card {{
            padding: var(--gp-pad-card);
            min-height: 124px;
        }}

        .gp-metric-icon {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: var(--gp-radius-chip);
            background: color-mix(in srgb, var(--gp-accent) 16%, transparent);
            color: var(--gp-accent);
            margin-bottom: 12px;
        }}

        .gp-metric-label {{
            color: var(--gp-muted);
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}

        .gp-metric-value {{
            color: var(--gp-text);
            font-family: var(--gp-font-mono);
            font-size: 21px;
            font-weight: 700;
            line-height: 1.15;
            overflow-wrap: anywhere;
        }}

        .gp-metric-caption {{
            color: var(--gp-accent);
            font-size: 13px;
            margin-top: 8px;
        }}

        .gp-zone-card, .gp-report-card {{
            padding: var(--gp-pad-card);
            margin-bottom: 14px;
        }}

        {glass_finish}

        .gp-card-title {{
            color: var(--gp-text);
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 8px;
        }}

        .gp-card-body {{
            color: var(--gp-muted);
            font-size: 14px;
            line-height: 1.55;
        }}

        .gp-badge {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            border: 1px solid var(--gp-border);
            background: var(--gp-surface-2);
            color: var(--gp-accent);
            border-radius: var(--gp-radius-pill);
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 8px;
        }}

        .gp-badge--accent {{
            color: var(--gp-accent);
            background: color-mix(in srgb, var(--gp-accent) 15%, transparent);
            border-color: color-mix(in srgb, var(--gp-accent) 35%, transparent);
        }}

        .gp-badge--amber {{
            color: var(--gp-amber);
            background: color-mix(in srgb, var(--gp-amber) 18%, transparent);
            border-color: color-mix(in srgb, var(--gp-amber) 40%, transparent);
        }}

        .gp-badge--alert {{
            color: var(--gp-accent-2);
            background: color-mix(in srgb, var(--gp-accent-2) 16%, transparent);
            border-color: color-mix(in srgb, var(--gp-accent-2) 38%, transparent);
        }}

        .gp-badge--neutral {{
            color: var(--gp-muted);
            background: var(--gp-surface-2);
            border-color: var(--gp-border);
        }}

        [data-testid="stForm"] {{
            background: var(--gp-surface);
            border: 1px solid var(--gp-border);
            border-radius: var(--gp-radius-card);
            padding: 18px;
            box-shadow: var(--gp-shadow-card);
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
            border-radius: var(--gp-radius-input) !important;
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
            border-radius: var(--gp-radius-chip) var(--gp-radius-chip) 0 0;
            color: var(--gp-muted);
            padding: 10px 14px;
            font-weight: 700;
        }}

        .stTabs [aria-selected="true"] {{
            color: var(--gp-text);
            background: var(--gp-surface-2);
            border-color: var(--gp-accent);
        }}

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] button {{
            background: linear-gradient(135deg, var(--gp-accent), color-mix(in srgb, var(--gp-accent) 70%, black));
            color: white;
            border: 1px solid var(--gp-accent);
            border-radius: var(--gp-radius-pill);
            font-weight: 700;
            box-shadow: var(--gp-shadow-card);
        }}

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] button:hover {{
            color: white;
            filter: brightness(1.08);
        }}

        [data-testid="stDataFrame"] {{
            background: var(--gp-surface);
            border: 1px solid var(--gp-border);
            border-radius: var(--gp-radius-card);
            box-shadow: var(--gp-shadow-card);
        }}

        .stAlert {{
            border-radius: var(--gp-radius-chip);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_theme_palette() -> dict[str, str]:
    """Return the fixed light-theme, Forense-accent CSS palette values."""
    return {
        "bg": (
            "linear-gradient(135deg, oklch(94% 0.025 240) 0%, "
            "oklch(92% 0.035 255) 50%, oklch(94% 0.02 220) 100%)"
        ),
        "bg_soft": "oklch(91% 0.03 320)",
        "surface": "#ffffff",
        "surface_2": "oklch(96% 0.01 280)",
        "border": "oklch(40% 0.015 250 / 0.12)",
        "text": "oklch(20% 0.015 250)",
        "muted": "oklch(50% 0.015 250)",
        "accent": "oklch(55% 0.17 250)",
        "accent_2": "oklch(58% 0.19 25)",
        "amber": "#b9812f",
        "shadow_card": "0 4px 18px oklch(40% 0.05 280 / 0.08)",
        "shadow_shell": "0 8px 32px oklch(40% 0.05 280 / 0.12)",
        "glass": "oklch(100% 0 0 / 0.55)",
        "glass_border": "oklch(100% 0 0 / 0.7)",
        "glass_shell": "oklch(100% 0 0 / 0.5)",
    }


def material_icon(name: str, size: int = 20) -> str:
    """Return a Material Symbols glyph <span> usable inside raw unsafe_allow_html markup.

    Streamlit's `:material/name:` shortcode only substitutes inside plain
    st.markdown text, not inside HTML strings passed with unsafe_allow_html=True
    (confirmed empirically). The "Material Symbols Rounded" face is already
    loaded globally by Streamlit regardless, so this emits the same span
    Streamlit generates internally for the shortcode, which renders correctly
    inside custom HTML cards too.
    """
    return (
        f'<span style="font-family:\'Material Symbols Rounded\'; '
        f'font-weight:400; font-size:{size}px; vertical-align:middle; '
        f'user-select:none;">{name}</span>'
    )


def render_badge(text: str, variant: str = "accent") -> str:
    """Return a pill-badge <span> for use inside raw unsafe_allow_html markup.

    variant is one of "accent", "amber", "alert", "neutral" (see the
    .gp-badge--* rules in inject_global_styles).
    """
    return f'<span class="gp-badge gp-badge--{variant}">{escape(text)}</span>'


def render_metric_card(column, icon: str, label: str, value: str, caption: str) -> None:
    """Render a custom metric card in the given Streamlit column.

    `icon` is a Material Symbols icon name (e.g. "target"), rendered via
    material_icon() inside the tinted icon chip.
    """
    with column:
        st.markdown(
            f"""
            <div class="gp-metric-card">
                <div class="gp-metric-icon">{material_icon(icon)}</div>
                <div class="gp-metric-label">{escape(label)}</div>
                <div class="gp-metric-value">{escape(value)}</div>
                <div class="gp-metric-caption">{escape(caption)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# Plotly validates color properties against hex/rgb/hsl/named-CSS strings
# only (its Python layer rejects `oklch()` outright, confirmed empirically:
# "ValueError: Invalid value ... received for the 'color' property"), unlike
# the browser-rendered CSS injected elsewhere in this module. These are the
# precise sRGB conversions of the guide's OKLCH tokens (text, grid,
# primary/secondary accent), computed directly from the OKLab formulas so
# they match the CSS tokens exactly rather than an eyeballed hex.
CHART_GRID_COLOR = "rgba(218, 222, 227, 0.5)"  # oklch(90% 0.008 250 / 0.5)
CHART_TEXT_COLOR = "#11171d"  # oklch(20% 0.015 250)
CHART_PRIMARY_COLOR = "#0073cf"  # oklch(55% 0.17 250)
CHART_SECONDARY_COLOR = "#d33a3c"  # oklch(58% 0.19 25)


def style_chart(figure):
    """Apply design-system-compliant styling to a Plotly figure.

    Restricted to the palette's two accents (never a rainbow colorway),
    IBM Plex Sans for titles/labels and IBM Plex Mono for tick numbers, and a
    single subtle gridline instead of the library's default grid.
    """
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(family="'IBM Plex Sans', sans-serif", color=CHART_TEXT_COLOR, size=13),
        margin=dict(l=20, r=20, t=50, b=24),
        hovermode="x unified",
        title_font_size=16,
        title_font_family="'IBM Plex Sans', sans-serif",
        title_font_color=CHART_TEXT_COLOR,
        colorway=[CHART_PRIMARY_COLOR, CHART_SECONDARY_COLOR],
        showlegend=False,
    )
    figure.update_xaxes(
        gridcolor=CHART_GRID_COLOR,
        zerolinecolor=CHART_GRID_COLOR,
        showline=False,
        tickfont=dict(family="'IBM Plex Mono', monospace", size=11),
    )
    figure.update_yaxes(
        gridcolor=CHART_GRID_COLOR,
        zerolinecolor=CHART_GRID_COLOR,
        showline=False,
        tickfont=dict(family="'IBM Plex Mono', monospace", size=11),
    )
    figure.update_traces(textposition="outside", marker_cornerradius=3, selector=dict(type="bar"))
    return figure


def render_chart_card(column, title: str, body_html: str) -> None:
    """Render a glass card containing a title and pre-built chart HTML body.

    The whole markup is emitted as a single line. Streamlit's markdown
    renderer treats a run of consecutive HTML lines as a raw HTML block only
    until the first blank (or whitespace-only) line, after which it falls
    back to normal Markdown block parsing — where a 4+-space-indented line
    is read as an indented code block. Multi-line, indented triple-quoted
    f-string snippets joined in a loop reliably produce such whitespace-only
    lines between items (confirmed empirically: the district/weekday bar
    charts rendered as literal preformatted text before this was flattened),
    so every HTML-returning helper here builds single-line strings instead.
    """
    with column:
        st.markdown(
            f'<div class="gp-card"><div class="gp-card-title">{escape(title)}</div>{body_html}</div>',
            unsafe_allow_html=True,
        )


def render_horizontal_bar_chart(items: list[tuple[str, int, float]], color: str = "var(--gp-accent)") -> str:
    """Return HTML for a stack of labeled proportion bars (e.g. crime type frequency).

    `items` is a list of (label, count, percent) rows, already sorted as desired.
    """
    rows = []
    for label, count, percent in items:
        rows.append(
            f'<div style="margin-top:14px;">'
            f'<div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:4px;">'
            f'<span style="font-weight:600; color:var(--gp-text);">{escape(str(label))}</span>'
            f'<span style="font-family:var(--gp-font-mono); color:var(--gp-muted); font-size:12px;">'
            f'{count} &middot; {percent:.0f}%</span>'
            f"</div>"
            f'<div style="background:var(--gp-surface-2); border-radius:3px; height:10px; overflow:hidden;">'
            f'<div style="height:100%; width:{percent:.2f}%; background:{color}; border-radius:3px;"></div>'
            f"</div></div>"
        )
    return "".join(rows) if rows else '<p style="color:var(--gp-muted); font-size:14px;">Sem dados.</p>'


def render_vertical_bar_chart(
    items: list[tuple[str, int]],
    color: str,
    bar_width: str = "28px",
    height: str = "140px",
    thin: bool = False,
) -> str:
    """Return HTML for a simple vertical bar chart (e.g. frequency by district/weekday/hour).

    `items` is a list of (label, count) pairs. When `thin` is set, bars are
    drawn edge-to-edge with no count/label captions (24-hour style chart);
    bars for a zero count render in a neutral tone instead of the accent.
    """
    if not items:
        return '<p style="color:var(--gp-muted); font-size:14px;">Sem dados.</p>'

    max_count = max((count for _, count in items), default=0) or 1
    bars = []
    for label, count in items:
        pct = max((count / max_count) * 100, 3 if count else 1.5)
        if thin:
            bar_color = color if count else "var(--gp-surface-2)"
            bars.append(
                f'<div style="flex:1; height:{pct:.1f}%; background:{bar_color}; '
                f'border-radius:2px 2px 0 0;" title="{escape(str(label))}: {count}"></div>'
            )
        else:
            bars.append(
                f'<div style="flex:1; display:flex; flex-direction:column; align-items:center; '
                f'justify-content:flex-end; height:100%;">'
                f'<div style="font-family:var(--gp-font-mono); font-size:11px; color:var(--gp-text); margin-bottom:4px;">'
                f"{count}</div>"
                f'<div style="width:{bar_width}; height:{pct:.1f}%; background:{color}; '
                f'border-radius:3px 3px 0 0;"></div>'
                f'<div style="font-size:11px; color:var(--gp-muted); margin-top:6px; text-align:center;">'
                f"{escape(str(label))}</div></div>"
            )

    gap = "3px" if thin else "12px"
    return (
        f'<div style="display:flex; align-items:flex-end; gap:{gap}; height:{height}; margin-top:16px;">'
        f'{"".join(bars)}</div>'
    )


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
