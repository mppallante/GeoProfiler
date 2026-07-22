"""Automated geographic profiling and natural-language analysis page."""

from __future__ import annotations

import math
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.data_manager import Caso
from src.geo_analysis import (
    CanterCircle,
    Coordinate,
    GeographicAnalysis,
    OffenderClassification,
    ProfileZone,
    run_geographic_analysis,
)
from src.pages._shared import (
    format_distance_table,
    format_grid_table,
    format_interpretation_title,
    format_neighborhood_zones_table,
    inject_global_styles,
    load_case_crimes,
    render_badge,
    render_case_header,
    render_date_range_filter,
    render_metric_card,
    render_sidebar,
    require_active_case,
    style_chart,
)
from src.report_export import build_case_pdf, build_map_html
from src.statistics import calculate_basic_statistics

_cached_run_geographic_analysis = st.cache_data(show_spinner=False)(run_geographic_analysis)


def main() -> None:
    theme = render_sidebar()
    inject_global_styles(theme)

    caso = require_active_case()
    render_case_header(caso)

    buffer_km = st.number_input(
        "Raio da zona de buffer (km)",
        min_value=0.05,
        max_value=5.0,
        value=0.5,
        step=0.1,
        format="%.2f",
        help="Distância a partir do CGC usada para classificar ocorrências dentro/fora da zona de buffer e como parâmetro do modelo de Rossmo (CGT).",
    )

    crimes = load_case_crimes(caso.id)
    crimes = render_date_range_filter(caso, crimes)
    analysis = _cached_run_geographic_analysis(
        crimes, buffer_km=buffer_km, barreiras_geograficas=caso.barreiras_geograficas
    )

    render_geographic_profiling_panel(analysis, theme)
    render_export_section(caso, crimes, analysis)


def render_geographic_profiling_panel(analysis: GeographicAnalysis, theme: str) -> None:
    """Render the geographic profiling intelligence panel."""
    st.subheader("PAINEL DE PERFILAMENTO GEOGRÁFICO")

    if analysis.distance_metrics is None or analysis.center is None:
        st.warning("Cadastre crimes válidos para gerar o painel de perfilamento.")
        return

    metrics = analysis.distance_metrics
    metric_cols = st.columns(4)
    render_metric_card(
        metric_cols[0],
        "target",
        "CGC",
        f"{analysis.center.latitude:.5f}, {analysis.center.longitude:.5f}",
        "Centro de Gravidade Criminal",
    )
    render_metric_card(metric_cols[1], "straighten", "Distância média", f"{metrics.average_distance_km:.2f} km", "Raio operacional médio")
    render_metric_card(metric_cols[2], "scatter_plot", "Desvio espacial", f"{metrics.spatial_std_km:.2f} km", "Dispersão territorial")
    render_metric_card(metric_cols[3], "insights", "Hipótese", analysis.offender_classification.category, f"{analysis.offender_classification.confidence:.1f}% de confiança")

    zone_cols = st.columns(3)
    render_zone_card(zone_cols[0], analysis.comfort_zone)
    render_zone_card(zone_cols[1], analysis.operations_base)
    render_zone_card(zone_cols[2], analysis.security_zone)

    st.markdown("#### Círculo de Canter")
    render_canter_circle_card(analysis.canter_circle, analysis.offender_classification)
    render_canter_circle_diagram(
        analysis.canter_circle,
        analysis.center,
        analysis.operations_base,
        analysis.crimes_with_distances,
        theme,
    )

    st.markdown("#### Relatório de inteligência geográfica")
    for title, text in analysis.interpretation.items():
        render_report_card(format_interpretation_title(title), text)

    st.markdown("#### Comparação de métodos de decaimento")
    st.caption(
        "Onde cada método de decaimento aponta como pico de probabilidade, e o quanto "
        "esse ponto diverge do resultado do modelo de Rossmo (CGT)."
    )
    decay_max_distance = (
        float(analysis.decay_comparison["distancia_ao_rossmo_km"].max() or 0.001)
        if not analysis.decay_comparison.empty
        else 0.001
    )
    st.dataframe(
        analysis.decay_comparison,
        width="stretch",
        hide_index=True,
        column_config={
            "distancia_ao_rossmo_km": st.column_config.ProgressColumn(
                "Distância ao pico de Rossmo (km)",
                format="%.3f km",
                min_value=0.0,
                max_value=decay_max_distance,
            ),
        },
    )

    st.markdown("#### Evidências espaciais")
    evidence_cols = st.columns(2)
    with evidence_cols[0]:
        st.write("Crime mais próximo do CGC")
        st.dataframe(pd.DataFrame([metrics.nearest_crime]), width="stretch", hide_index=True)
    with evidence_cols[1]:
        st.write("Crime mais distante do CGC")
        st.dataframe(pd.DataFrame([metrics.farthest_crime]), width="stretch", hide_index=True)

    ranking = format_grid_table(analysis.critical_cells)
    st.markdown("#### Ranking das células críticas")
    st.dataframe(ranking, width="stretch", hide_index=True)
    if not ranking.empty:
        critical_cells_chart = px.bar(
            ranking,
            x="Célula",
            y="Total de crimes",
            text="Total de crimes",
            title="Concentração por célula crítica",
        )
        st.plotly_chart(style_chart(critical_cells_chart, theme), width="stretch")

    distance_table = format_distance_table(analysis.crimes_with_distances)
    st.markdown("#### Distância de cada crime até o CGC")
    st.dataframe(distance_table, width="stretch", hide_index=True)
    if not distance_table.empty:
        distance_chart = px.line(
            distance_table,
            x="ID",
            y="Distância até o CGC (km)",
            markers=True,
            title="Distância ao Centro de Gravidade Criminal por ocorrência",
        )
        st.plotly_chart(style_chart(distance_chart, theme), width="stretch")

    neighborhood_zones = format_neighborhood_zones_table(analysis.neighborhood_zones)
    st.markdown("#### Classificação de bairros")
    st.caption(
        "Bairros com distância média ao CGC igual ou menor que a média geral da série são "
        "lidos como Zona de Conforto; os demais, como Zona de Transição."
    )
    st.dataframe(neighborhood_zones, width="stretch", hide_index=True)


def render_zone_card(column, zone: ProfileZone) -> None:
    """Render a geographic profiling zone card."""
    center = "Indisponível"
    if zone.center is not None:
        center = f"{zone.center.latitude:.6f}, {zone.center.longitude:.6f}"

    with column:
        st.markdown(
            f"""
            <div class="gp-zone-card">
                {render_badge(zone.title, "accent")}
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


def render_canter_circle_card(
    canter_circle: CanterCircle | None,
    offender_classification: OffenderClassification,
) -> None:
    """Render Canter's Circle Hypothesis result as a card."""
    if canter_circle is None:
        st.info("Cadastre ao menos 2 crimes válidos para calcular o Círculo de Canter.")
        return

    id_a, id_b = canter_circle.farthest_pair
    if offender_classification.category.startswith("Marauder"):
        badge_text, badge_variant = "Base estimada dentro do círculo", "accent"
    elif offender_classification.category.startswith("Commuter"):
        badge_text, badge_variant = "Base estimada fora do círculo", "amber"
    else:
        badge_text, badge_variant = "Indeterminado", "neutral"

    st.markdown(
        f"""
        <div class="gp-zone-card">
            {render_badge(badge_text, badge_variant)}
            <div class="gp-card-title">Raio: {canter_circle.radius_km:.2f} km</div>
            <div class="gp-card-body">
                <strong>Centro:</strong> {canter_circle.center.latitude:.6f}, {canter_circle.center.longitude:.6f}<br><br>
                Definido pelos crimes mais distantes entre si da série:
                <strong>#{id_a}</strong> e <strong>#{id_b}</strong>.<br><br>
                A hipótese de Canter espera que a base do infrator esteja localizada
                dentro deste círculo.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_canter_circle_diagram(
    canter_circle: CanterCircle | None,
    center: Coordinate | None,
    operations_base: ProfileZone,
    crimes_with_distances: pd.DataFrame,
    theme: str,
) -> None:
    """Render a schematic diagram of the Canter Circle with labeled callouts.

    Not the tactical map (that's src/map_visualization.py) — a clean, tile-free
    plot of just the points that matter for this specific hypothesis test: the
    CGC, the estimated base, and the two crimes whose distance defines the
    circle. Real lat/long positions are used (not a fake abstract layout), with
    an axis scale correction so the circle renders as an actual circle instead
    of a latitude-distorted ellipse.
    """
    if canter_circle is None or center is None:
        return

    id_a, id_b = canter_circle.farthest_pair
    points: list[tuple[float, float, str]] = [(center.longitude, center.latitude, "CGC")]

    if operations_base.center is not None:
        points.append((operations_base.center.longitude, operations_base.center.latitude, "Base estimada"))

    for crime_id in (id_a, id_b):
        match = crimes_with_distances.loc[crimes_with_distances["id"] == crime_id]
        if not match.empty:
            row = match.iloc[0]
            points.append((row["longitude"], row["latitude"], f"Crime #{crime_id}"))

    lat_radius_deg = canter_circle.radius_km / 111.0
    lon_radius_deg = canter_circle.radius_km / (
        111.0 * max(math.cos(math.radians(canter_circle.center.latitude)), 0.01)
    )

    figure = go.Figure()
    figure.add_shape(
        type="circle",
        xref="x",
        yref="y",
        x0=canter_circle.center.longitude - lon_radius_deg,
        x1=canter_circle.center.longitude + lon_radius_deg,
        y0=canter_circle.center.latitude - lat_radius_deg,
        y1=canter_circle.center.latitude + lat_radius_deg,
        line=dict(color="#8b5cf6", width=2, dash="dash"),
        fillcolor="rgba(139, 92, 246, 0.08)",
    )
    figure.add_trace(
        go.Scatter(
            x=[point[0] for point in points],
            y=[point[1] for point in points],
            mode="markers",
            marker=dict(size=12, color="#4db6e8", line=dict(color="#ffffff", width=2)),
            showlegend=False,
            hovertext=[point[2] for point in points],
            hoverinfo="text",
        )
    )

    callout_offsets = [(50, -40), (50, 40), (-50, -40), (-50, 40)]
    for index, (lon, lat, label) in enumerate(points):
        offset_x, offset_y = callout_offsets[index % len(callout_offsets)]
        figure.add_annotation(
            x=lon,
            y=lat,
            text=label,
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            ax=offset_x,
            ay=offset_y,
            font=dict(size=12),
        )

    figure.update_xaxes(
        scaleanchor="y",
        scaleratio=math.cos(math.radians(canter_circle.center.latitude)),
        visible=False,
    )
    figure.update_yaxes(visible=False)
    figure.update_layout(
        title="Diagrama esquemático do Círculo de Canter",
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
    )

    st.plotly_chart(style_chart(figure, theme), width="stretch")


def render_export_section(caso: Caso, crimes: pd.DataFrame, analysis: GeographicAnalysis) -> None:
    """Render download buttons for the case's interactive map and PDF dossier."""
    st.markdown("#### Exportar")
    slug = "".join(char if char.isalnum() else "_" for char in caso.nome).strip("_") or "caso"

    export_cols = st.columns(2)
    with export_cols[0]:
        st.download_button(
            "Baixar mapa interativo (HTML)",
            data=build_map_html(crimes, analysis),
            file_name=f"{slug}_mapa.html",
            mime="text/html",
            icon=":material/map:",
            width="stretch",
        )
    with export_cols[1]:
        stats = calculate_basic_statistics(crimes)
        st.download_button(
            "Baixar relatório do caso (PDF)",
            data=build_case_pdf(caso, crimes, analysis, stats),
            file_name=f"{slug}_relatorio.pdf",
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
            width="stretch",
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


main()
