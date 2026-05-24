"""Geographic analysis helpers for GeoProfiler."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt

import pandas as pd


@dataclass(frozen=True)
class Coordinate:
    """Simple latitude and longitude pair."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class MapBounds:
    """Map bounds represented by southwest and northeast coordinates."""

    southwest: Coordinate
    northeast: Coordinate


@dataclass(frozen=True)
class DistanceMetrics:
    """Distance statistics around the geographic center."""

    average_distance_km: float
    spatial_std_km: float
    nearest_crime: dict[str, object]
    farthest_crime: dict[str, object]


@dataclass(frozen=True)
class GeographicAnalysis:
    """Full geographic analysis result used by the dashboard."""

    center: Coordinate | None
    crimes_with_distances: pd.DataFrame
    distance_metrics: DistanceMetrics | None
    grid: pd.DataFrame
    critical_cells: pd.DataFrame
    interpretation: dict[str, str]


def create_geodataframe(crimes: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert a crime DataFrame into a GeoDataFrame."""
    import geopandas as gpd

    return gpd.GeoDataFrame(
        crimes.copy(),
        geometry=gpd.points_from_xy(crimes["longitude"], crimes["latitude"]),
        crs="EPSG:4326",
    )


def calculate_central_point(crimes: pd.DataFrame) -> Coordinate | None:
    """Calculate the central point of all registered crimes."""
    if crimes.empty:
        return None

    return Coordinate(
        latitude=float(crimes["latitude"].mean()),
        longitude=float(crimes["longitude"].mean()),
    )


def calculate_map_bounds(crimes: pd.DataFrame) -> MapBounds | None:
    """Calculate map bounds that include all crime points."""
    if crimes.empty:
        return None

    return MapBounds(
        southwest=Coordinate(
            latitude=float(crimes["latitude"].min()),
            longitude=float(crimes["longitude"].min()),
        ),
        northeast=Coordinate(
            latitude=float(crimes["latitude"].max()),
            longitude=float(crimes["longitude"].max()),
        ),
    )


def build_heatmap_points(crimes: pd.DataFrame) -> list[list[float]]:
    """Build latitude and longitude pairs for Folium heatmaps."""
    if crimes.empty:
        return []

    return crimes[["latitude", "longitude"]].astype(float).values.tolist()


def run_geographic_analysis(crimes: pd.DataFrame, grid_size_degrees: float = 0.01) -> GeographicAnalysis:
    """Run the complete initial geographic crime analysis."""
    if crimes.empty:
        return GeographicAnalysis(
            center=None,
            crimes_with_distances=crimes.copy(),
            distance_metrics=None,
            grid=pd.DataFrame(),
            critical_cells=pd.DataFrame(),
            interpretation=build_empty_interpretation(),
        )

    center = calculate_central_point(crimes)
    crimes_with_distances = calculate_crime_distances(crimes, center)
    distance_metrics = calculate_distance_metrics(crimes_with_distances)
    grid = create_geographic_grid(crimes_with_distances, grid_size_degrees)
    critical_cells = rank_critical_cells(grid)
    interpretation = generate_geographic_interpretation(
        crimes_with_distances=crimes_with_distances,
        distance_metrics=distance_metrics,
        critical_cells=critical_cells,
        center=center,
    )

    return GeographicAnalysis(
        center=center,
        crimes_with_distances=crimes_with_distances,
        distance_metrics=distance_metrics,
        grid=grid,
        critical_cells=critical_cells,
        interpretation=interpretation,
    )


def calculate_crime_distances(crimes: pd.DataFrame, center: Coordinate | None) -> pd.DataFrame:
    """Calculate each crime distance to the geographic center."""
    enriched = crimes.copy()
    if center is None or enriched.empty:
        enriched["distancia_centro_km"] = pd.Series(dtype=float)
        return enriched

    enriched["distancia_centro_km"] = enriched.apply(
        lambda row: haversine_distance_km(
            row["latitude"],
            row["longitude"],
            center.latitude,
            center.longitude,
        ),
        axis=1,
    )

    return enriched


def calculate_distance_metrics(crimes_with_distances: pd.DataFrame) -> DistanceMetrics | None:
    """Calculate average distance, spatial standard deviation, and extreme cases."""
    if crimes_with_distances.empty or "distancia_centro_km" not in crimes_with_distances:
        return None

    distances = crimes_with_distances["distancia_centro_km"].dropna()
    if distances.empty:
        return None

    nearest = crimes_with_distances.loc[distances.idxmin()]
    farthest = crimes_with_distances.loc[distances.idxmax()]

    return DistanceMetrics(
        average_distance_km=float(distances.mean()),
        spatial_std_km=float(distances.std(ddof=0)),
        nearest_crime=crime_row_to_summary(nearest),
        farthest_crime=crime_row_to_summary(farthest),
    )


def create_geographic_grid(crimes: pd.DataFrame, grid_size_degrees: float = 0.01) -> pd.DataFrame:
    """Create a geographic grid and count crimes per cell."""
    if crimes.empty:
        return pd.DataFrame()

    min_lat = float(crimes["latitude"].min())
    min_lon = float(crimes["longitude"].min())
    grid_data = crimes.copy()

    grid_data["grid_lat_index"] = (
        ((grid_data["latitude"] - min_lat) / grid_size_degrees).astype(int) + 1
    )
    grid_data["grid_lon_index"] = (
        ((grid_data["longitude"] - min_lon) / grid_size_degrees).astype(int) + 1
    )
    grid_data["celula"] = (
        "G"
        + grid_data["grid_lat_index"].astype(str).str.zfill(2)
        + "-"
        + grid_data["grid_lon_index"].astype(str).str.zfill(2)
    )

    grouped = (
        grid_data.groupby("celula")
        .agg(
            total_crimes=("id", "count"),
            latitude_min=("latitude", "min"),
            latitude_max=("latitude", "max"),
            longitude_min=("longitude", "min"),
            longitude_max=("longitude", "max"),
            centro_latitude=("latitude", "mean"),
            centro_longitude=("longitude", "mean"),
            bairros=("bairro", lambda values: join_unique_values(values)),
            tipos_crime=("tipo_crime", lambda values: join_unique_values(values)),
        )
        .reset_index()
    )

    grouped["densidade_relativa"] = grouped["total_crimes"] / len(crimes)
    grouped = grouped.sort_values(
        ["total_crimes", "densidade_relativa"],
        ascending=[False, False],
    )

    return grouped.reset_index(drop=True)


def rank_critical_cells(grid: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Rank the most critical cells by crime concentration."""
    if grid.empty:
        return pd.DataFrame()

    ranking = grid.copy()
    ranking["ranking"] = range(1, len(ranking) + 1)
    return ranking.head(top_n)


def generate_geographic_interpretation(
    crimes_with_distances: pd.DataFrame,
    distance_metrics: DistanceMetrics | None,
    critical_cells: pd.DataFrame,
    center: Coordinate | None,
) -> dict[str, str]:
    """Generate a cautious automatic interpretation from the computed metrics."""
    if crimes_with_distances.empty or distance_metrics is None or center is None:
        return build_empty_interpretation()

    top_cell = critical_cells.iloc[0] if not critical_cells.empty else None
    concentration_text = build_concentration_text(top_cell)
    radius_text = f"{distance_metrics.average_distance_km:.2f} km"
    std_text = f"{distance_metrics.spatial_std_km:.2f} km"

    return {
        "possivel_zona_atuacao": (
            "Os registros se distribuem em torno do centro medio "
            f"({center.latitude:.6f}, {center.longitude:.6f}), com distancia media "
            f"de {radius_text}. Essa faixa pode orientar uma zona inicial de atuacao."
        ),
        "area_maior_concentracao": concentration_text,
        "hipotese_zona_conforto": (
            "Como hipotese inicial, a zona de conforto pode estar proxima ao centro "
            "medio ou a celula mais critica, especialmente se os crimes mais proximos "
            "mantiverem padrao semelhante de bairro, horario ou modus operandi."
        ),
        "limitacoes_analise": (
            "Esta analise e exploratoria. Ela nao considera rede viaria, barreiras "
            "urbanas, oportunidade criminal, subnotificacao, intervalo temporal, "
            "perfil da vitima ou deslocamento real. Os resultados devem apoiar "
            "investigacao, nao substituir avaliacao tecnica."
        ),
        "dispersao_espacial": (
            f"O desvio padrao espacial e de {std_text}. Valores maiores indicam "
            "ocorrencias mais dispersas; valores menores sugerem concentracao local."
        ),
    }


def build_concentration_text(top_cell: pd.Series | None) -> str:
    """Build interpretation text for the highest concentration grid cell."""
    if top_cell is None:
        return "Nao ha celulas suficientes para indicar concentracao."

    return (
        f"A celula {top_cell['celula']} concentra {int(top_cell['total_crimes'])} "
        f"crime(s), representando {top_cell['densidade_relativa']:.1%} da base. "
        f"Bairros associados: {top_cell['bairros']}."
    )


def build_empty_interpretation() -> dict[str, str]:
    """Return default interpretation for empty datasets."""
    return {
        "possivel_zona_atuacao": "Sem dados suficientes para estimar zona de atuacao.",
        "area_maior_concentracao": "Sem dados suficientes para estimar concentracao.",
        "hipotese_zona_conforto": "Sem dados suficientes para formular hipotese.",
        "limitacoes_analise": "Cadastre ocorrencias validas para iniciar a analise.",
        "dispersao_espacial": "Sem dados suficientes para calcular dispersao.",
    }


def haversine_distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Calculate distance in kilometers between two WGS84 coordinates."""
    earth_radius_km = 6371.0088
    lat_a = radians(latitude_a)
    lat_b = radians(latitude_b)
    delta_lat = radians(latitude_b - latitude_a)
    delta_lon = radians(longitude_b - longitude_a)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_km * c


def crime_row_to_summary(row: pd.Series) -> dict[str, object]:
    """Convert a crime row into a compact summary dictionary."""
    date_value = row.get("data")
    date_label = date_value.strftime("%d/%m/%Y") if hasattr(date_value, "strftime") else "-"

    return {
        "id": int(row["id"]) if pd.notna(row.get("id")) else "-",
        "tipo_crime": row.get("tipo_crime", "-"),
        "data": date_label,
        "bairro": row.get("bairro", "-"),
        "distancia_centro_km": round(float(row.get("distancia_centro_km", 0)), 3),
    }


def join_unique_values(values: pd.Series) -> str:
    """Join unique non-empty values for grid summaries."""
    unique_values = sorted(
        {
            str(value).strip()
            for value in values
            if pd.notna(value) and str(value).strip()
        }
    )
    return ", ".join(unique_values) if unique_values else "-"


def summarize_geographic_profile(crimes: pd.DataFrame) -> dict[str, str | int]:
    """Return a compact geographic summary for the dashboard."""
    if crimes.empty:
        return {
            "status": "Sem dados validos para analise.",
            "total_pontos": 0,
        }

    geodata = create_geodataframe(crimes)
    center = calculate_central_point(crimes)
    bounds = calculate_map_bounds(crimes)

    return {
        "status": "Resumo inicial gerado.",
        "total_pontos": len(geodata),
        "sistema_referencia": str(geodata.crs),
        "ponto_central": (
            f"{center.latitude:.6f}, {center.longitude:.6f}" if center else "-"
        ),
        "limites_mapa": (
            f"{bounds.southwest.latitude:.6f}, {bounds.southwest.longitude:.6f} | "
            f"{bounds.northeast.latitude:.6f}, {bounds.northeast.longitude:.6f}"
            if bounds
            else "-"
        ),
    }
