"""Tests for src/report_export.py."""

from __future__ import annotations

import pandas as pd

from src.geo_analysis import run_geographic_analysis
from src.report_export import build_case_pdf, build_map_html
from src.statistics import calculate_basic_statistics


def _dummy_caso():
    from src.data_manager import Caso

    return Caso(
        id=1,
        nome="Caso Teste",
        descricao="Descrição do caso",
        responsavel="Investigador",
        data_abertura="2026-01-01",
        barreiras_geograficas="",
        notas="",
        arquivado=False,
        total_crimes=0,
        created_at="",
        updated_at="",
    )


def test_build_map_html_returns_non_empty_bytes(seed_crimes):
    analysis = run_geographic_analysis(seed_crimes)
    html_bytes = build_map_html(seed_crimes, analysis)
    assert isinstance(html_bytes, bytes)
    assert len(html_bytes) > 0


def test_build_case_pdf_returns_valid_pdf_for_seed_data(seed_crimes):
    analysis = run_geographic_analysis(seed_crimes)
    stats = calculate_basic_statistics(seed_crimes)
    pdf_bytes = build_case_pdf(_dummy_caso(), seed_crimes, analysis, stats)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


def test_build_case_pdf_does_not_crash_for_empty_case():
    empty_crimes = pd.DataFrame(columns=["id", "tipo_crime", "data", "hora", "latitude", "longitude", "cidade", "bairro", "modus_operandi", "observacoes"])
    analysis = run_geographic_analysis(empty_crimes)
    stats = calculate_basic_statistics(empty_crimes)
    pdf_bytes = build_case_pdf(_dummy_caso(), empty_crimes, analysis, stats)

    assert pdf_bytes.startswith(b"%PDF")
