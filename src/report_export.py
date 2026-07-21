"""Case dossier export: standalone interactive map HTML and a PDF report."""

from __future__ import annotations

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.data_manager import Caso
from src.geo_analysis import GeographicAnalysis
from src.map_visualization import create_crime_map
from src.statistics import CrimeStatistics

_INTERPRETATION_TITLES = {
    "resumo_executivo": "Resumo Executivo",
    "padrao_espacial_identificado": "Padrao Espacial Identificado",
    "centro_gravidade_criminal": "Centro de Gravidade Criminal (CGC)",
    "zona_de_conforto": "Zona de Conforto",
    "base_de_operacoes": "Base de Operacoes",
    "zona_de_seguranca": "Zona de Seguranca",
    "classificacao_geografica": "Classificacao Marauder ou Commuter",
    "zona_de_buffer": "Zona de Buffer",
    "perfil_rossmo": "Perfil de Rossmo (CGT)",
    "hipoteses_investigativas": "Hipoteses Investigativas",
    "limitacoes_metodologicas": "Limitacoes Metodologicas",
}


def _interpretation_title(value: str) -> str:
    return _INTERPRETATION_TITLES.get(value, value.replace("_", " ").title())


def build_map_html(crimes: pd.DataFrame, analysis: GeographicAnalysis) -> bytes:
    """Render the case's Folium map as a standalone HTML file."""
    crime_map = create_crime_map(crimes, analysis)
    return crime_map.get_root().render().encode("utf-8")


def _safe_text(text: object) -> str:
    """Coerce to a string safe for fpdf2's Latin-1 core fonts."""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def build_case_pdf(
    caso: Caso,
    crimes: pd.DataFrame,
    analysis: GeographicAnalysis,
    stats: CrimeStatistics,
) -> bytes:
    """Build a PDF case dossier: metadata, metrics, zones, narrative report, tables."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _add_title(pdf, "GeoProfiler - Relatorio do Caso")
    _add_case_metadata(pdf, caso, stats)
    _add_profiling_summary(pdf, analysis)
    _add_narrative_report(pdf, analysis)
    _add_critical_cells_table(pdf, analysis)
    _add_crime_list_table(pdf, crimes)

    return bytes(pdf.output())


def _add_title(pdf: FPDF, text: str) -> None:
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, _safe_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


def _add_section_title(pdf: FPDF, text: str) -> None:
    pdf.set_font("helvetica", "B", 13)
    pdf.cell(0, 8, _safe_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 11)


def _add_case_metadata(pdf: FPDF, caso: Caso, stats: CrimeStatistics) -> None:
    _add_section_title(pdf, caso.nome)
    lines = [
        f"Descricao: {caso.descricao or '-'}",
        f"Responsavel: {caso.responsavel or 'Nao informado'}",
        f"Data de abertura: {caso.data_abertura or '-'}",
        f"Ocorrencias: {stats.total_records} | Tipos de crime: {stats.unique_crime_types} | "
        f"Periodo: {stats.date_range_label}",
    ]
    for line in lines:
        pdf.multi_cell(0, 6, _safe_text(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)


def _add_profiling_summary(pdf: FPDF, analysis: GeographicAnalysis) -> None:
    _add_section_title(pdf, "Resumo do perfilamento geografico")

    if analysis.center is None or analysis.distance_metrics is None:
        pdf.multi_cell(0, 6, _safe_text("Sem dados suficientes para o perfilamento."))
        pdf.ln(4)
        return

    metrics = analysis.distance_metrics
    lines = [
        f"CGC: {analysis.center.latitude:.6f}, {analysis.center.longitude:.6f}",
        f"Distancia media ao CGC: {metrics.average_distance_km:.2f} km",
        f"Desvio espacial: {metrics.spatial_std_km:.2f} km",
        f"Classificacao: {analysis.offender_classification.category} "
        f"({analysis.offender_classification.confidence:.1f}% de confianca)",
    ]

    for zone in (analysis.comfort_zone, analysis.operations_base, analysis.security_zone):
        if zone.center is not None:
            lines.append(
                f"{zone.title}: raio {zone.radius_km:.2f} km, centro "
                f"{zone.center.latitude:.6f}, {zone.center.longitude:.6f}"
            )

    if analysis.canter_circle is not None:
        id_a, id_b = analysis.canter_circle.farthest_pair
        lines.append(
            f"Circulo de Canter: raio {analysis.canter_circle.radius_km:.2f} km, "
            f"definido pelos crimes #{id_a} e #{id_b}"
        )

    for line in lines:
        pdf.multi_cell(0, 6, _safe_text(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)


def _add_narrative_report(pdf: FPDF, analysis: GeographicAnalysis) -> None:
    _add_section_title(pdf, "Relatorio de inteligencia geografica")
    for key, text in analysis.interpretation.items():
        pdf.set_font("helvetica", "B", 11)
        pdf.multi_cell(0, 6, _safe_text(_interpretation_title(key)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("helvetica", "", 11)
        pdf.multi_cell(0, 6, _safe_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)
    pdf.ln(2)


def _add_critical_cells_table(pdf: FPDF, analysis: GeographicAnalysis) -> None:
    if analysis.critical_cells.empty:
        return

    _add_section_title(pdf, "Ranking das celulas criticas")
    pdf.set_font("helvetica", "B", 9)
    headers = ["Ranking", "Celula", "Total", "Bairros"]
    widths = [20, 25, 20, 125]
    for header, width in zip(headers, widths):
        pdf.cell(width, 6, _safe_text(header), border=1)
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    for _, row in analysis.critical_cells.iterrows():
        pdf.cell(widths[0], 6, _safe_text(int(row["ranking"])), border=1)
        pdf.cell(widths[1], 6, _safe_text(row["celula"]), border=1)
        pdf.cell(widths[2], 6, _safe_text(int(row["total_crimes"])), border=1)
        pdf.cell(widths[3], 6, _safe_text(row["bairros"])[:80], border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)


def _add_crime_list_table(pdf: FPDF, crimes: pd.DataFrame) -> None:
    if crimes.empty:
        return

    _add_section_title(pdf, "Ocorrencias cadastradas")
    pdf.set_font("helvetica", "B", 9)
    headers = ["ID", "Tipo", "Data", "Bairro", "Latitude", "Longitude"]
    widths = [12, 35, 22, 40, 30, 30]
    for header, width in zip(headers, widths):
        pdf.cell(width, 6, _safe_text(header), border=1)
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    for row in crimes.itertuples():
        pdf.cell(widths[0], 6, _safe_text(int(row.id)), border=1)
        pdf.cell(widths[1], 6, _safe_text(row.tipo_crime)[:22], border=1)
        pdf.cell(widths[2], 6, _safe_text(row.data.strftime("%d/%m/%Y")), border=1)
        pdf.cell(widths[3], 6, _safe_text(row.bairro)[:25], border=1)
        pdf.cell(widths[4], 6, _safe_text(f"{row.latitude:.6f}"), border=1)
        pdf.cell(widths[5], 6, _safe_text(f"{row.longitude:.6f}"), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
