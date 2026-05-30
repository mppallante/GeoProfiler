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
class ProfileZone:
    """Investigative geographic profiling zone."""

    title: str
    center: Coordinate | None
    radius_km: float
    description: str
    evidence: str


@dataclass(frozen=True)
class OffenderClassification:
    """Automatic geographic offender classification hypothesis."""

    category: str
    confidence: float
    justification: str


@dataclass(frozen=True)
class GeographicAnalysis:
    """Full geographic analysis result used by the dashboard."""

    center: Coordinate | None
    crimes_with_distances: pd.DataFrame
    distance_metrics: DistanceMetrics | None
    grid: pd.DataFrame
    critical_cells: pd.DataFrame
    density_surface: list[list[float]]
    comfort_zone: ProfileZone
    operations_base: ProfileZone
    security_zone: ProfileZone
    offender_classification: OffenderClassification
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
            density_surface=[],
            comfort_zone=build_empty_zone("Zona de Conforto"),
            operations_base=build_empty_zone("Base de Operações"),
            security_zone=build_empty_zone("Zona de Segurança"),
            offender_classification=OffenderClassification(
                category="Indeterminado",
                confidence=0.0,
                justification="Sem dados suficientes para classificação geográfica.",
            ),
            interpretation=build_empty_interpretation(),
        )

    center = calculate_central_point(crimes)
    crimes_with_distances = calculate_crime_distances(crimes, center)
    distance_metrics = calculate_distance_metrics(crimes_with_distances)
    grid = create_geographic_grid(crimes_with_distances, grid_size_degrees)
    critical_cells = rank_critical_cells(grid)
    density_surface = build_density_surface(crimes_with_distances, distance_metrics)
    comfort_zone = estimate_comfort_zone(crimes_with_distances, critical_cells, distance_metrics)
    operations_base = estimate_operations_base(crimes_with_distances, comfort_zone, distance_metrics)
    security_zone = estimate_security_zone(crimes_with_distances, center, distance_metrics)
    offender_classification = classify_geographic_offender(
        crimes_with_distances,
        critical_cells,
        distance_metrics,
    )
    interpretation = generate_geographic_interpretation(
        crimes_with_distances=crimes_with_distances,
        distance_metrics=distance_metrics,
        critical_cells=critical_cells,
        center=center,
        comfort_zone=comfort_zone,
        operations_base=operations_base,
        security_zone=security_zone,
        offender_classification=offender_classification,
    )

    return GeographicAnalysis(
        center=center,
        crimes_with_distances=crimes_with_distances,
        distance_metrics=distance_metrics,
        grid=grid,
        critical_cells=critical_cells,
        density_surface=density_surface,
        comfort_zone=comfort_zone,
        operations_base=operations_base,
        security_zone=security_zone,
        offender_classification=offender_classification,
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


def build_density_surface(
    crimes: pd.DataFrame,
    distance_metrics: DistanceMetrics | None,
    grid_steps: int = 28,
) -> list[list[float]]:
    """Build a smooth kernel-density-like surface for heatmap rendering."""
    if crimes.empty:
        return []

    min_lat = float(crimes["latitude"].min())
    max_lat = float(crimes["latitude"].max())
    min_lon = float(crimes["longitude"].min())
    max_lon = float(crimes["longitude"].max())

    lat_padding = max((max_lat - min_lat) * 0.2, 0.004)
    lon_padding = max((max_lon - min_lon) * 0.2, 0.004)
    min_lat -= lat_padding
    max_lat += lat_padding
    min_lon -= lon_padding
    max_lon += lon_padding

    bandwidth = 0.75
    if distance_metrics is not None:
        bandwidth = max(distance_metrics.average_distance_km * 0.75, 0.35)

    lat_values = [
        min_lat + (max_lat - min_lat) * index / max(grid_steps - 1, 1)
        for index in range(grid_steps)
    ]
    lon_values = [
        min_lon + (max_lon - min_lon) * index / max(grid_steps - 1, 1)
        for index in range(grid_steps)
    ]

    raw_surface = []
    max_density = 0.0
    for latitude in lat_values:
        for longitude in lon_values:
            density = 0.0
            for _, crime in crimes.iterrows():
                distance = haversine_distance_km(
                    latitude,
                    longitude,
                    crime["latitude"],
                    crime["longitude"],
                )
                density += gaussian_kernel(distance, bandwidth)
            max_density = max(max_density, density)
            raw_surface.append([latitude, longitude, density])

    if max_density == 0:
        return []

    return [
        [latitude, longitude, round(density / max_density, 4)]
        for latitude, longitude, density in raw_surface
        if density / max_density >= 0.08
    ]


def gaussian_kernel(distance_km: float, bandwidth_km: float) -> float:
    """Return a simple Gaussian kernel weight."""
    return 2.718281828459045 ** (-0.5 * (distance_km / bandwidth_km) ** 2)


def estimate_comfort_zone(
    crimes: pd.DataFrame,
    critical_cells: pd.DataFrame,
    distance_metrics: DistanceMetrics | None,
) -> ProfileZone:
    """Estimate the area of highest criminal incidence."""
    if crimes.empty or critical_cells.empty:
        return build_empty_zone("Zona de Conforto")

    top_cell = critical_cells.iloc[0]
    center = Coordinate(
        latitude=float(top_cell["centro_latitude"]),
        longitude=float(top_cell["centro_longitude"]),
    )
    radius = 0.5
    if distance_metrics is not None:
        radius = max(0.35, min(distance_metrics.average_distance_km, 2.5))

    total = int(top_cell["total_crimes"])
    density = float(top_cell["densidade_relativa"])

    return ProfileZone(
        title="Zona de Conforto",
        center=center,
        radius_km=radius,
        description=(
            "Área de maior incidência criminal, sugerindo familiaridade operacional "
            "do autor com o ambiente."
        ),
        evidence=(
            f"Célula {top_cell['celula']} concentra {total} ocorrência(s), "
            f"equivalente a {density:.1%} da base. Bairros associados: {top_cell['bairros']}."
        ),
    )


def estimate_operations_base(
    crimes: pd.DataFrame,
    comfort_zone: ProfileZone,
    distance_metrics: DistanceMetrics | None,
) -> ProfileZone:
    """Estimate a possible base of operations from the inner activity area."""
    if crimes.empty:
        return build_empty_zone("Base de Operações")

    if "distancia_centro_km" in crimes.columns and distance_metrics is not None:
        threshold = max(distance_metrics.average_distance_km, 0.2)
        inner_crimes = crimes[crimes["distancia_centro_km"] <= threshold]
    else:
        inner_crimes = crimes

    if inner_crimes.empty:
        inner_crimes = crimes

    center = Coordinate(
        latitude=float(inner_crimes["latitude"].mean()),
        longitude=float(inner_crimes["longitude"].mean()),
    )
    radius = 0.45
    if distance_metrics is not None:
        radius = max(0.25, min(distance_metrics.average_distance_km * 0.55, 1.5))

    comfort_reference = ""
    if comfort_zone.center is not None:
        comfort_reference = (
            f" A estimativa fica relacionada a zona de conforto em "
            f"{comfort_zone.center.latitude:.6f}, {comfort_zone.center.longitude:.6f}."
        )

    return ProfileZone(
        title="Base de Operações",
        center=center,
        radius_km=radius,
        description=(
            "Área estimada de residência, trabalho, apoio logístico ou atividade "
            "recorrente do ofensor."
        ),
        evidence=(
            "Calculada a partir das ocorrências mais próximas do Centro de Gravidade "
            f"Criminal (CGC).{comfort_reference}"
        ),
    )


def estimate_security_zone(
    crimes: pd.DataFrame,
    center: Coordinate | None,
    distance_metrics: DistanceMetrics | None,
) -> ProfileZone:
    """Estimate a low-probability or avoided action area."""
    if crimes.empty or center is None or distance_metrics is None:
        return build_empty_zone("Zona de Segurança")

    radius = max(
        distance_metrics.average_distance_km + distance_metrics.spatial_std_km,
        distance_metrics.average_distance_km * 1.35,
        0.75,
    )

    return ProfileZone(
        title="Zona de Segurança",
        center=center,
        radius_km=radius,
        description=(
            "Área externa de menor probabilidade operacional imediata, possivelmente "
            "evitada pelo autor por maior risco de reconhecimento ou menor familiaridade."
        ),
        evidence=(
            "Delimitada por ocorrências acima da dispersão média em torno do CGC. "
            "Deve ser lida como região de baixa prioridade relativa, não como exclusão."
        ),
    )


def classify_geographic_offender(
    crimes: pd.DataFrame,
    critical_cells: pd.DataFrame,
    distance_metrics: DistanceMetrics | None,
) -> OffenderClassification:
    """Classify the geographic pattern as Marauder or Commuter hypothesis."""
    if crimes.empty or distance_metrics is None:
        return OffenderClassification(
            category="Indeterminado",
            confidence=0.0,
            justification="Sem dados suficientes para classificação geográfica.",
        )

    top_density = 0.0
    if not critical_cells.empty:
        top_density = float(critical_cells.iloc[0]["densidade_relativa"])

    average = distance_metrics.average_distance_km
    dispersion = distance_metrics.spatial_std_km
    dispersion_ratio = dispersion / average if average else 0.0

    marauder_score = 0.0
    if top_density >= 0.45:
        marauder_score += 0.45
    elif top_density >= 0.30:
        marauder_score += 0.28
    else:
        marauder_score += 0.12

    if dispersion_ratio <= 0.65:
        marauder_score += 0.40
    elif dispersion_ratio <= 1.0:
        marauder_score += 0.24
    else:
        marauder_score += 0.08

    if average <= 2.0:
        marauder_score += 0.15
    elif average <= 5.0:
        marauder_score += 0.08

    marauder_score = min(marauder_score, 0.95)

    if marauder_score >= 0.55:
        return OffenderClassification(
            category="Marauder (Predador Local)",
            confidence=round(marauder_score * 100, 1),
            justification=(
                "Padrão concentrado, com baixa a moderada dispersão espacial e "
                "ocorrências relativamente próximas do CGC. Hipótese investigativa "
                "compatível com atuação local."
            ),
        )

    commuter_confidence = round((1 - marauder_score) * 100, 1)
    return OffenderClassification(
        category="Commuter (Viajante)",
        confidence=max(commuter_confidence, 55.0),
        justification=(
            "Padrão mais disperso, com deslocamentos relevantes entre ocorrências e "
            "menor concentração em uma única região. Hipótese investigativa compatível "
            "com deslocamento até a área de ataque."
        ),
    )


def generate_geographic_interpretation(
    crimes_with_distances: pd.DataFrame,
    distance_metrics: DistanceMetrics | None,
    critical_cells: pd.DataFrame,
    center: Coordinate | None,
    comfort_zone: ProfileZone | None = None,
    operations_base: ProfileZone | None = None,
    security_zone: ProfileZone | None = None,
    offender_classification: OffenderClassification | None = None,
) -> dict[str, str]:
    """Generate a structured geographic intelligence report."""
    if crimes_with_distances.empty or distance_metrics is None or center is None:
        return build_empty_interpretation()

    top_cell = critical_cells.iloc[0] if not critical_cells.empty else None
    concentration_text = build_concentration_text(top_cell)
    radius_text = f"{distance_metrics.average_distance_km:.2f} km"
    std_text = f"{distance_metrics.spatial_std_km:.2f} km"
    comfort_zone = comfort_zone or build_empty_zone("Zona de Conforto")
    operations_base = operations_base or build_empty_zone("Base de Operações")
    security_zone = security_zone or build_empty_zone("Zona de Segurança")
    offender_classification = offender_classification or OffenderClassification(
        category="Indeterminado",
        confidence=0.0,
        justification="Sem classificação disponível.",
    )

    return {
        "resumo_executivo": (
            f"Foram analisadas {len(crimes_with_distances)} ocorrências válidas. "
            f"O CGC está em {center.latitude:.6f}, {center.longitude:.6f}, com "
            f"distância média de {radius_text} e desvio espacial de {std_text}."
        ),
        "padrao_espacial_identificado": (
            f"{concentration_text} A leitura espacial indica um padrão que deve ser "
            "comparado com horários, modus operandi e contexto urbano antes de qualquer conclusão."
        ),
        "centro_gravidade_criminal": (
            "O Centro de Gravidade Criminal (CGC) representa o ponto médio operacional "
            "das ocorrências e deve ser usado como referência inicial de priorização territorial."
        ),
        "zona_de_conforto": f"{comfort_zone.description} {comfort_zone.evidence}",
        "base_de_operacoes": f"{operations_base.description} {operations_base.evidence}",
        "zona_de_seguranca": f"{security_zone.description} {security_zone.evidence}",
        "classificacao_geografica": (
            f"Hipótese: {offender_classification.category}. Confiança estimada: "
            f"{offender_classification.confidence:.1f}%. {offender_classification.justification}"
        ),
        "hipoteses_investigativas": (
            "Priorizar verificação de vínculos territoriais na zona de conforto e na base "
            "estimada, cruzando com reincidência horária, vias de acesso, registros locais "
            "e padrões de modus operandi."
        ),
        "limitacoes_metodologicas": (
            "Relatório exploratório, não conclusão pericial. Não considera rede viária, "
            "barreiras urbanas, subnotificacao, oportunidade criminal, vitimologia, "
            "tempo de permanência, deslocamento real ou dados externos de inteligência."
        ),
    }


def build_concentration_text(top_cell: pd.Series | None) -> str:
    """Build interpretation text for the highest concentration grid cell."""
    if top_cell is None:
        return "Não há células suficientes para indicar concentração."

    return (
        f"A célula {top_cell['celula']} concentra {int(top_cell['total_crimes'])} "
        f"crime(s), representando {top_cell['densidade_relativa']:.1%} da base. "
        f"Bairros associados: {top_cell['bairros']}."
    )


def build_empty_interpretation() -> dict[str, str]:
    """Return default interpretation for empty datasets."""
    return {
        "resumo_executivo": "Sem dados suficientes para gerar o relatório.",
        "padrao_espacial_identificado": "Sem padrão espacial identificável.",
        "centro_gravidade_criminal": "Sem ocorrências válidas para calcular o CGC.",
        "zona_de_conforto": "Sem dados suficientes para estimar zona de conforto.",
        "base_de_operacoes": "Sem dados suficientes para estimar base de operações.",
        "zona_de_seguranca": "Sem dados suficientes para estimar zona de segurança.",
        "classificacao_geografica": "Sem dados suficientes para classificação.",
        "hipoteses_investigativas": "Cadastre ocorrências válidas para iniciar a análise.",
        "limitacoes_metodologicas": "A análise depende de dados georreferenciados válidos.",
    }


def build_empty_zone(title: str) -> ProfileZone:
    """Build an empty profiling zone."""
    return ProfileZone(
        title=title,
        center=None,
        radius_km=0.0,
        description="Sem dados suficientes para estimativa.",
        evidence="Cadastre ocorrências válidas para gerar esta zona.",
    )


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
            "status": "Sem dados válidos para análise.",
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
