"""Tests for src/geo_analysis.py."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from src.geo_analysis import (
    CanterCircle,
    Coordinate,
    ProfileZone,
    build_decay_comparison_surface,
    build_rossmo_probability_surface,
    calculate_canter_circle,
    calculate_central_point,
    calculate_distance_metrics,
    calculate_map_bounds,
    classify_buffer_zone,
    classify_geographic_offender,
    classify_neighborhood_zones,
    compare_decay_methods,
    create_geographic_grid,
    estimate_comfort_zone,
    estimate_operations_base,
    estimate_security_zone,
    exponential_decay_score,
    gaussian_decay_score,
    haversine_distance_km,
    linear_decay_score,
    rank_critical_cells,
    rossmo_score,
    run_geographic_analysis,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DENSITY_SURFACE_SNAPSHOT = FIXTURES_DIR / "density_surface_snapshot.json"


def test_haversine_known_points():
    # Se (Sao Paulo) to Centro (Rio de Janeiro), ~357 km great-circle distance.
    distance = haversine_distance_km(-23.5505, -46.6333, -22.9068, -43.1729)
    assert math.isclose(distance, 357.0, rel_tol=0.02)


def test_haversine_zero_distance_for_identical_points():
    assert haversine_distance_km(-23.5, -46.6, -23.5, -46.6) == 0.0


def test_calculate_central_point_empty_returns_none():
    assert calculate_central_point(pd.DataFrame(columns=["latitude", "longitude"])) is None


def test_calculate_central_point_averages_coordinates():
    crimes = pd.DataFrame({"latitude": [-23.0, -24.0], "longitude": [-46.0, -47.0]})
    center = calculate_central_point(crimes)
    assert center == Coordinate(latitude=-23.5, longitude=-46.5)


def test_calculate_map_bounds_empty_returns_none():
    assert calculate_map_bounds(pd.DataFrame(columns=["latitude", "longitude"])) is None


def test_calculate_map_bounds_covers_extremes():
    crimes = pd.DataFrame({"latitude": [-23.0, -24.0, -22.5], "longitude": [-46.0, -47.0, -45.5]})
    bounds = calculate_map_bounds(crimes)
    assert bounds.southwest == Coordinate(latitude=-24.0, longitude=-47.0)
    assert bounds.northeast == Coordinate(latitude=-22.5, longitude=-45.5)


def test_calculate_distance_metrics_empty_returns_none():
    assert calculate_distance_metrics(pd.DataFrame()) is None


def test_calculate_canter_circle_none_for_fewer_than_two_crimes():
    assert calculate_canter_circle(pd.DataFrame({"id": [1], "latitude": [-23.0], "longitude": [-46.0]})) is None
    assert calculate_canter_circle(pd.DataFrame(columns=["id", "latitude", "longitude"])) is None


def test_calculate_canter_circle_finds_farthest_pair():
    crimes = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "latitude": [-23.55, -23.56, -22.90],
            "longitude": [-46.63, -46.64, -43.17],
        }
    )
    circle = calculate_canter_circle(crimes)

    expected_distance = haversine_distance_km(-23.56, -46.64, -22.90, -43.17)
    assert circle.farthest_pair == (2, 3)
    assert circle.radius_km == pytest.approx(expected_distance / 2, rel=1e-9)
    assert circle.center == Coordinate(latitude=(-23.56 + -22.90) / 2, longitude=(-46.64 + -43.17) / 2)


def test_classify_buffer_zone_marks_crimes_relative_to_threshold():
    crimes_with_distances = pd.DataFrame({"distancia_centro_km": [0.1, 0.5, 0.51, 2.0]})
    result = classify_buffer_zone(crimes_with_distances, buffer_km=0.5)
    assert list(result["dentro_zona_buffer"]) == [True, True, False, False]


def test_classify_buffer_zone_empty_data():
    result = classify_buffer_zone(pd.DataFrame(), buffer_km=0.5)
    assert result.empty


def test_rossmo_score_outside_buffer_uses_inverse_power():
    assert rossmo_score(2.0, buffer_km=0.5, f=1.2, g=1.2) == pytest.approx(1 / 2.0**1.2)


def test_rossmo_score_inside_buffer_uses_piecewise_branch():
    expected = 0.5 ** (1.2 - 1.2) / (2 * 0.5 - 0.1) ** 1.2
    assert rossmo_score(0.1, buffer_km=0.5, f=1.2, g=1.2) == pytest.approx(expected)


def test_rossmo_score_is_continuous_at_buffer_boundary():
    buffer_km = 0.5
    just_inside = rossmo_score(buffer_km, buffer_km=buffer_km, f=1.2, g=1.2)
    just_outside = rossmo_score(buffer_km + 1e-9, buffer_km=buffer_km, f=1.2, g=1.2)
    assert just_inside == pytest.approx(just_outside, rel=1e-6)


def test_build_rossmo_probability_surface_structural_properties(seed_crimes):
    surface = build_rossmo_probability_surface(seed_crimes)
    assert surface
    for _, _, score in surface:
        assert 0.0 <= score <= 1.0


def test_build_rossmo_probability_surface_empty_data_returns_empty_list():
    assert build_rossmo_probability_surface(pd.DataFrame(columns=["latitude", "longitude"])) == []


def test_classify_marauder_when_base_inside_circle():
    crimes_with_distances = pd.DataFrame({"id": [1, 2, 3]})
    canter_circle = CanterCircle(
        center=Coordinate(latitude=-23.55, longitude=-46.63),
        radius_km=2.0,
        farthest_pair=(1, 2),
    )
    operations_base = ProfileZone(
        title="Base de Operações",
        center=Coordinate(latitude=-23.551, longitude=-46.631),
        radius_km=0.5,
        description="",
        evidence="",
    )
    result = classify_geographic_offender(crimes_with_distances, canter_circle, operations_base)
    assert result.category.startswith("Marauder")
    assert result.confidence >= 60.0


def test_classify_commuter_when_base_outside_circle():
    crimes_with_distances = pd.DataFrame({"id": [1, 2, 3]})
    canter_circle = CanterCircle(
        center=Coordinate(latitude=-23.55, longitude=-46.63),
        radius_km=0.2,
        farthest_pair=(1, 2),
    )
    operations_base = ProfileZone(
        title="Base de Operações",
        center=Coordinate(latitude=-23.60, longitude=-46.70),
        radius_km=0.5,
        description="",
        evidence="",
    )
    result = classify_geographic_offender(crimes_with_distances, canter_circle, operations_base)
    assert result.category.startswith("Commuter")


def test_classify_empty_data_is_indeterminate():
    result = classify_geographic_offender(pd.DataFrame(), None, None)
    assert result.category == "Indeterminado"
    assert result.confidence == 0.0


def test_create_geographic_grid_groups_points_into_cells(seed_crimes):
    grid = create_geographic_grid(seed_crimes)
    assert not grid.empty
    assert grid["total_crimes"].sum() == len(seed_crimes)
    assert list(grid.columns).count("celula") == 1


def test_rank_critical_cells_assigns_sequential_ranking(seed_crimes):
    grid = create_geographic_grid(seed_crimes)
    ranked = rank_critical_cells(grid, top_n=5)
    assert list(ranked["ranking"]) == list(range(1, len(ranked) + 1))
    assert len(ranked) <= 5


def test_estimate_zones_return_empty_zone_for_empty_data():
    zone = estimate_comfort_zone(pd.DataFrame(), pd.DataFrame(), None)
    assert zone.center is None
    assert zone.radius_km == 0.0


def test_estimate_zones_produce_a_center_for_real_data(seed_crimes):
    grid = create_geographic_grid(seed_crimes)
    critical_cells = rank_critical_cells(grid)
    from src.geo_analysis import calculate_crime_distances

    center = calculate_central_point(seed_crimes)
    crimes_with_distances = calculate_crime_distances(seed_crimes, center)
    metrics = calculate_distance_metrics(crimes_with_distances)

    comfort_zone = estimate_comfort_zone(crimes_with_distances, critical_cells, metrics)
    operations_base = estimate_operations_base(crimes_with_distances, comfort_zone, metrics)
    security_zone = estimate_security_zone(crimes_with_distances, center, metrics)

    assert comfort_zone.center is not None
    assert comfort_zone.radius_km > 0
    assert operations_base.center is not None
    assert security_zone.center is not None
    assert security_zone.radius_km >= comfort_zone.radius_km


def test_run_geographic_analysis_on_seed_data_matches_shape(seed_crimes):
    analysis = run_geographic_analysis(seed_crimes)

    assert analysis.center is not None
    assert analysis.distance_metrics is not None
    assert len(analysis.crimes_with_distances) == len(seed_crimes)
    assert not analysis.critical_cells.empty
    assert analysis.offender_classification.category in {
        "Marauder (Predador Local)",
        "Commuter (Viajante)",
    }


def test_run_geographic_analysis_empty_data_returns_safe_defaults():
    analysis = run_geographic_analysis(pd.DataFrame(columns=["latitude", "longitude", "id", "bairro", "tipo_crime"]))

    assert analysis.center is None
    assert analysis.distance_metrics is None
    assert analysis.density_surface == []
    assert analysis.offender_classification.category == "Indeterminado"


def test_density_surface_matches_pre_vectorization_snapshot(seed_crimes):
    """Regression guard for the numpy vectorization of build_density_surface.

    The fixture below was captured from the original nested-loop/iterrows
    implementation on the seed CSV. Any rewrite of build_density_surface must
    keep reproducing the same (lat, lon, density) triples within floating
    point tolerance.
    """
    analysis = run_geographic_analysis(seed_crimes)

    with DENSITY_SURFACE_SNAPSHOT.open(encoding="utf-8") as handle:
        expected = json.load(handle)

    actual = analysis.density_surface
    assert len(actual) == len(expected)
    for (actual_lat, actual_lon, actual_density), (expected_lat, expected_lon, expected_density) in zip(
        actual, expected
    ):
        assert actual_lat == pytest.approx(expected_lat, abs=1e-6)
        assert actual_lon == pytest.approx(expected_lon, abs=1e-6)
        assert actual_density == pytest.approx(expected_density, abs=1e-4)


def test_classify_neighborhood_zones_empty_data_returns_empty_frame():
    result = classify_neighborhood_zones(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == ["bairro", "total_crimes", "distancia_media_km", "classificacao"]


def test_classify_neighborhood_zones_classifies_relative_to_overall_average():
    # Overall average distance = (0.5 + 0.5 + 3.0 + 3.0) / 4 = 1.75 km.
    # "Centro" averages 0.5 km (<= 1.75) -> Zona de Conforto.
    # "Periferia" averages 3.0 km (> 1.75) -> Zona de Transição.
    crimes_with_distances = pd.DataFrame(
        {
            "bairro": ["Centro", "Centro", "Periferia", "Periferia"],
            "distancia_centro_km": [0.5, 0.5, 3.0, 3.0],
        }
    )
    result = classify_neighborhood_zones(crimes_with_distances)
    by_bairro = result.set_index("bairro")

    assert by_bairro.loc["Centro", "classificacao"] == "Zona de Conforto"
    assert by_bairro.loc["Centro", "total_crimes"] == 2
    assert by_bairro.loc["Periferia", "classificacao"] == "Zona de Transição"


def test_classify_neighborhood_zones_blank_bairro_becomes_nao_informado():
    crimes_with_distances = pd.DataFrame({"bairro": ["", None], "distancia_centro_km": [1.0, 1.0]})
    result = classify_neighborhood_zones(crimes_with_distances)
    assert list(result["bairro"]) == ["Não informado"]
    assert result.iloc[0]["total_crimes"] == 2


def test_exponential_decay_score_known_value():
    assert exponential_decay_score(1.0, decay_rate=1.0) == pytest.approx(1 / math.e)
    assert exponential_decay_score(0.0, decay_rate=2.0) == pytest.approx(1.0)


def test_linear_decay_score_known_values():
    assert linear_decay_score(0.0, max_distance_km=2.0) == pytest.approx(1.0)
    assert linear_decay_score(1.0, max_distance_km=2.0) == pytest.approx(0.5)
    assert linear_decay_score(5.0, max_distance_km=2.0) == 0.0
    assert linear_decay_score(1.0, max_distance_km=0.0) == 0.0


def test_gaussian_decay_score_known_value():
    assert gaussian_decay_score(0.0, bandwidth_km=1.0) == pytest.approx(1.0)
    assert gaussian_decay_score(1.0, bandwidth_km=1.0) == pytest.approx(math.exp(-0.5))


def test_build_decay_comparison_surface_structural_properties(seed_crimes):
    for decay_type in ("rossmo", "exponencial", "linear", "gaussiana"):
        surface = build_decay_comparison_surface(seed_crimes, decay_type, max_distance_km=5.0, bandwidth_km=1.0)
        assert surface, f"expected a non-empty surface for {decay_type}"
        for _, _, score in surface:
            assert 0.0 <= score <= 1.0


def test_build_decay_comparison_surface_empty_data_returns_empty_list():
    assert build_decay_comparison_surface(pd.DataFrame(columns=["latitude", "longitude"]), "linear") == []


def test_build_decay_comparison_surface_unknown_type_raises():
    with pytest.raises(ValueError):
        build_decay_comparison_surface(pd.DataFrame({"latitude": [-23.5], "longitude": [-46.6]}), "desconhecido")


def test_compare_decay_methods_returns_four_rows_with_rossmo_at_zero(seed_crimes):
    from src.geo_analysis import calculate_central_point, calculate_crime_distances

    center = calculate_central_point(seed_crimes)
    crimes_with_distances = calculate_crime_distances(seed_crimes, center)
    metrics = calculate_distance_metrics(crimes_with_distances)

    comparison = compare_decay_methods(crimes_with_distances, metrics)

    assert len(comparison) == 4
    rossmo_row = comparison[comparison["metodo"] == "Rossmo (CGT)"].iloc[0]
    assert rossmo_row["distancia_ao_rossmo_km"] == 0.0


def test_compare_decay_methods_empty_data_returns_empty_frame():
    result = compare_decay_methods(pd.DataFrame(), None)
    assert result.empty
