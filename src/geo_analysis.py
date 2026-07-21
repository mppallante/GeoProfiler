"""Geographic analysis helpers for GeoProfiler."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import atan2, cos, radians, sin, sqrt

import numpy as np
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
class CanterCircle:
    """Canter's Circle Hypothesis: a circle whose diameter joins the two
    crimes farthest apart in the series, expected to contain the offender's base."""

    center: Coordinate
    radius_km: float
    farthest_pair: tuple[int, int]


@dataclass(frozen=True)
class GeographicAnalysis:
    """Full geographic analysis result used by the dashboard."""

    center: Coordinate | None
    crimes_with_distances: pd.DataFrame
    distance_metrics: DistanceMetrics | None
    grid: pd.DataFrame
    critical_cells: pd.DataFrame
    density_surface: list[list[float]]
    rossmo_surface: list[list[float]]
    canter_circle: CanterCircle | None
    neighborhood_zones: pd.DataFrame
    decay_comparison: pd.DataFrame
    comfort_zone: ProfileZone
    operations_base: ProfileZone
    security_zone: ProfileZone
    offender_classification: OffenderClassification
    interpretation: dict[str, str]


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


def calculate_canter_circle(crimes: pd.DataFrame) -> CanterCircle | None:
    """Calculate Canter's Circle Hypothesis: the circle whose diameter joins
    the two crimes farthest apart in the series (all-pairs haversine distance).
    """
    if len(crimes) < 2:
        return None

    farthest_distance = -1.0
    farthest_rows: tuple[pd.Series, pd.Series] | None = None
    for row_a, row_b in combinations(crimes.itertuples(), 2):
        distance = haversine_distance_km(
            row_a.latitude, row_a.longitude, row_b.latitude, row_b.longitude
        )
        if distance > farthest_distance:
            farthest_distance = distance
            farthest_rows = (row_a, row_b)

    row_a, row_b = farthest_rows
    center = Coordinate(
        latitude=(row_a.latitude + row_b.latitude) / 2,
        longitude=(row_a.longitude + row_b.longitude) / 2,
    )

    return CanterCircle(
        center=center,
        radius_km=farthest_distance / 2,
        farthest_pair=(int(row_a.id), int(row_b.id)),
    )


def build_heatmap_points(crimes: pd.DataFrame) -> list[list[float]]:
    """Build latitude and longitude pairs for Folium heatmaps."""
    if crimes.empty:
        return []

    return crimes[["latitude", "longitude"]].astype(float).values.tolist()


def run_geographic_analysis(
    crimes: pd.DataFrame,
    grid_size_degrees: float = 0.01,
    buffer_km: float = 0.5,
    barreiras_geograficas: str = "",
) -> GeographicAnalysis:
    """Run the complete initial geographic crime analysis."""
    if crimes.empty:
        return GeographicAnalysis(
            center=None,
            crimes_with_distances=crimes.copy(),
            distance_metrics=None,
            grid=pd.DataFrame(),
            critical_cells=pd.DataFrame(),
            density_surface=[],
            rossmo_surface=[],
            canter_circle=None,
            neighborhood_zones=pd.DataFrame(),
            decay_comparison=pd.DataFrame(),
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
    crimes_with_distances = classify_buffer_zone(crimes_with_distances, buffer_km)
    distance_metrics = calculate_distance_metrics(crimes_with_distances)
    grid = create_geographic_grid(crimes_with_distances, grid_size_degrees)
    critical_cells = rank_critical_cells(grid)
    density_surface = build_density_surface(crimes_with_distances, distance_metrics)
    rossmo_surface = build_rossmo_probability_surface(crimes_with_distances, buffer_km=buffer_km)
    neighborhood_zones = classify_neighborhood_zones(crimes_with_distances)
    decay_comparison = compare_decay_methods(crimes_with_distances, distance_metrics, buffer_km=buffer_km)
    comfort_zone = estimate_comfort_zone(crimes_with_distances, critical_cells, distance_metrics)
    operations_base = estimate_operations_base(crimes_with_distances, comfort_zone, distance_metrics)
    security_zone = estimate_security_zone(crimes_with_distances, center, distance_metrics)
    canter_circle = calculate_canter_circle(crimes)
    offender_classification = classify_geographic_offender(
        crimes_with_distances,
        canter_circle,
        operations_base,
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
        rossmo_surface=rossmo_surface,
        buffer_km=buffer_km,
        barreiras_geograficas=barreiras_geograficas,
    )

    return GeographicAnalysis(
        center=center,
        crimes_with_distances=crimes_with_distances,
        distance_metrics=distance_metrics,
        grid=grid,
        critical_cells=critical_cells,
        density_surface=density_surface,
        rossmo_surface=rossmo_surface,
        canter_circle=canter_circle,
        neighborhood_zones=neighborhood_zones,
        decay_comparison=decay_comparison,
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


def classify_buffer_zone(crimes_with_distances: pd.DataFrame, buffer_km: float) -> pd.DataFrame:
    """Flag each crime as inside or outside the buffer radius around the CGC."""
    classified = crimes_with_distances.copy()
    if classified.empty or "distancia_centro_km" not in classified.columns:
        classified["dentro_zona_buffer"] = pd.Series(dtype=bool)
        return classified

    classified["dentro_zona_buffer"] = classified["distancia_centro_km"] <= buffer_km
    return classified


def classify_neighborhood_zones(crimes_with_distances: pd.DataFrame) -> pd.DataFrame:
    """Classify each bairro as comfort or transition zone by average distance to the CGC.

    Mirrors the course material's own worked example: bairros whose average
    distance to the CGC is at or below the series' overall average distance
    are read as "Zona de Conforto"; farther bairros as "Zona de Transição".
    """
    columns = ["bairro", "total_crimes", "distancia_media_km", "classificacao"]
    if crimes_with_distances.empty or "distancia_centro_km" not in crimes_with_distances.columns:
        return pd.DataFrame(columns=columns)

    data = crimes_with_distances.copy()
    data["bairro"] = data["bairro"].fillna("Não informado").astype(str).replace("", "Não informado")

    overall_average = float(data["distancia_centro_km"].mean())

    grouped = (
        data.groupby("bairro")
        .agg(
            total_crimes=("bairro", "count"),
            distancia_media_km=("distancia_centro_km", "mean"),
        )
        .reset_index()
    )
    grouped["classificacao"] = grouped["distancia_media_km"].apply(
        lambda distance: "Zona de Conforto" if distance <= overall_average else "Zona de Transição"
    )
    grouped["distancia_media_km"] = grouped["distancia_media_km"].round(3)

    return grouped.sort_values("distancia_media_km").reset_index(drop=True)[columns]


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

    lat_values = np.linspace(min_lat, max_lat, grid_steps)
    lon_values = np.linspace(min_lon, max_lon, grid_steps)
    grid_lat, grid_lon = np.meshgrid(lat_values, lon_values, indexing="ij")

    crime_lat = crimes["latitude"].to_numpy(dtype=float)
    crime_lon = crimes["longitude"].to_numpy(dtype=float)

    # Vectorized haversine distance from every grid point to every crime,
    # broadcast to shape (grid_steps, grid_steps, len(crimes)).
    earth_radius_km = 6371.0088
    lat_a = np.radians(grid_lat)[:, :, None]
    lon_a = np.radians(grid_lon)[:, :, None]
    lat_b = np.radians(crime_lat)[None, None, :]
    lon_b = np.radians(crime_lon)[None, None, :]

    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a
    haversine_a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat_a) * np.cos(lat_b) * np.sin(delta_lon / 2) ** 2
    )
    distances = earth_radius_km * 2 * np.arctan2(np.sqrt(haversine_a), np.sqrt(1 - haversine_a))

    density = np.exp(-0.5 * (distances / bandwidth) ** 2).sum(axis=2)
    max_density = float(density.max())

    if max_density == 0:
        return []

    normalized = density / max_density
    surface = []
    for lat_index in range(grid_steps):
        for lon_index in range(grid_steps):
            value = float(normalized[lat_index, lon_index])
            if value >= 0.08:
                surface.append(
                    [float(grid_lat[lat_index, lon_index]), float(grid_lon[lat_index, lon_index]), round(value, 4)]
                )

    return surface


def rossmo_score(distance_km: float, buffer_km: float, f: float, g: float) -> float:
    """Score a single distance under Rossmo's Criminal Geographic Targeting formula.

    Scalar reference implementation of the piecewise CGT formula (minus the
    absolute normalizing constant `k`, since only the relative surface across
    the grid matters for rendering). `build_rossmo_probability_surface` computes
    the same formula vectorized over an entire grid.
    """
    if distance_km > buffer_km:
        return 1 / distance_km**f

    return buffer_km ** (g - f) / (2 * buffer_km - distance_km) ** g


def build_rossmo_probability_surface(
    crimes: pd.DataFrame,
    buffer_km: float = 0.5,
    f: float = 1.2,
    g: float = 1.2,
    grid_steps: int = 28,
) -> list[list[float]]:
    """Build Rossmo's Criminal Geographic Targeting (CGT) probability surface."""
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

    lat_values = np.linspace(min_lat, max_lat, grid_steps)
    lon_values = np.linspace(min_lon, max_lon, grid_steps)
    grid_lat, grid_lon = np.meshgrid(lat_values, lon_values, indexing="ij")

    crime_lat = crimes["latitude"].to_numpy(dtype=float)
    crime_lon = crimes["longitude"].to_numpy(dtype=float)

    earth_radius_km = 6371.0088
    lat_a = np.radians(grid_lat)[:, :, None]
    lon_a = np.radians(grid_lon)[:, :, None]
    lat_b = np.radians(crime_lat)[None, None, :]
    lon_b = np.radians(crime_lon)[None, None, :]

    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a
    haversine_a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat_a) * np.cos(lat_b) * np.sin(delta_lon / 2) ** 2
    )
    distances = earth_radius_km * 2 * np.arctan2(np.sqrt(haversine_a), np.sqrt(1 - haversine_a))

    with np.errstate(divide="ignore", invalid="ignore"):
        outside_score = np.power(distances, -f)
        inside_score = (buffer_km ** (g - f)) / np.power(2 * buffer_km - distances, g)
        score = np.where(distances > buffer_km, outside_score, inside_score).sum(axis=2)

    max_score = float(score.max())
    if max_score == 0:
        return []

    normalized = score / max_score
    surface = []
    for lat_index in range(grid_steps):
        for lon_index in range(grid_steps):
            value = float(normalized[lat_index, lon_index])
            if value >= 0.08:
                surface.append(
                    [float(grid_lat[lat_index, lon_index]), float(grid_lon[lat_index, lon_index]), round(value, 4)]
                )

    return surface


def exponential_decay_score(distance_km: float, decay_rate: float = 1.0) -> float:
    """Score a distance under a negative-exponential decay function."""
    return 2.718281828459045 ** (-decay_rate * distance_km)


def linear_decay_score(distance_km: float, max_distance_km: float) -> float:
    """Score a distance under a linear decay function, zero beyond max_distance_km."""
    if max_distance_km <= 0:
        return 0.0
    return max(0.0, 1 - distance_km / max_distance_km)


def gaussian_decay_score(distance_km: float, bandwidth_km: float) -> float:
    """Score a distance under a Gaussian (normal) kernel.

    Scalar reference for the same kernel `build_density_surface` already uses
    inline; extracting it here does not change that function's computation.
    """
    return 2.718281828459045 ** (-0.5 * (distance_km / bandwidth_km) ** 2)


_DECAY_METHOD_LABELS = {
    "rossmo": "Rossmo (CGT)",
    "exponencial": "Exponencial negativa",
    "linear": "Linear",
    "gaussiana": "Normal (Gaussiana)",
}


def build_decay_comparison_surface(
    crimes: pd.DataFrame,
    decay_type: str,
    buffer_km: float = 0.5,
    decay_rate: float = 1.0,
    max_distance_km: float = 5.0,
    bandwidth_km: float = 0.75,
    f: float = 1.2,
    g: float = 1.2,
    grid_steps: int = 28,
) -> list[list[float]]:
    """Build a probability surface using a selectable distance-decay function."""
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

    lat_values = np.linspace(min_lat, max_lat, grid_steps)
    lon_values = np.linspace(min_lon, max_lon, grid_steps)
    grid_lat, grid_lon = np.meshgrid(lat_values, lon_values, indexing="ij")

    crime_lat = crimes["latitude"].to_numpy(dtype=float)
    crime_lon = crimes["longitude"].to_numpy(dtype=float)

    earth_radius_km = 6371.0088
    lat_a = np.radians(grid_lat)[:, :, None]
    lon_a = np.radians(grid_lon)[:, :, None]
    lat_b = np.radians(crime_lat)[None, None, :]
    lon_b = np.radians(crime_lon)[None, None, :]

    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a
    haversine_a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat_a) * np.cos(lat_b) * np.sin(delta_lon / 2) ** 2
    )
    distances = earth_radius_km * 2 * np.arctan2(np.sqrt(haversine_a), np.sqrt(1 - haversine_a))

    with np.errstate(divide="ignore", invalid="ignore"):
        if decay_type == "rossmo":
            outside_score = np.power(distances, -f)
            inside_score = (buffer_km ** (g - f)) / np.power(2 * buffer_km - distances, g)
            per_crime_score = np.where(distances > buffer_km, outside_score, inside_score)
        elif decay_type == "exponencial":
            per_crime_score = np.exp(-decay_rate * distances)
        elif decay_type == "linear":
            per_crime_score = np.clip(1 - distances / max_distance_km, 0.0, None) if max_distance_km > 0 else np.zeros_like(distances)
        elif decay_type == "gaussiana":
            per_crime_score = np.exp(-0.5 * (distances / bandwidth_km) ** 2)
        else:
            raise ValueError(f"Função de decaimento desconhecida: {decay_type}")

        score = per_crime_score.sum(axis=2)

    max_score = float(score.max())
    if max_score == 0:
        return []

    normalized = score / max_score
    surface = []
    for lat_index in range(grid_steps):
        for lon_index in range(grid_steps):
            value = float(normalized[lat_index, lon_index])
            if value >= 0.08:
                surface.append(
                    [float(grid_lat[lat_index, lon_index]), float(grid_lon[lat_index, lon_index]), round(value, 4)]
                )

    return surface


def compare_decay_methods(
    crimes_with_distances: pd.DataFrame,
    distance_metrics: DistanceMetrics | None,
    buffer_km: float = 0.5,
    grid_steps: int = 28,
) -> pd.DataFrame:
    """Compare where each distance-decay method's peak probability lands.

    Reports, for each method, its own peak-probability grid point and how far
    that point is from Rossmo's peak — a sensitivity check for how much the
    estimated hotspot depends on the chosen decay assumption.
    """
    columns = ["metodo", "pico_latitude", "pico_longitude", "distancia_ao_rossmo_km"]
    if crimes_with_distances.empty or distance_metrics is None:
        return pd.DataFrame(columns=columns)

    bandwidth_km = max(distance_metrics.average_distance_km * 0.75, 0.35)
    max_distance_km = max(distance_metrics.average_distance_km * 2, 0.5)

    peaks: dict[str, tuple[float, float]] = {}
    for decay_type in ("rossmo", "exponencial", "linear", "gaussiana"):
        surface = build_decay_comparison_surface(
            crimes_with_distances,
            decay_type,
            buffer_km=buffer_km,
            max_distance_km=max_distance_km,
            bandwidth_km=bandwidth_km,
            grid_steps=grid_steps,
        )
        if not surface:
            continue
        peak_lat, peak_lon, _ = max(surface, key=lambda point: point[2])
        peaks[decay_type] = (peak_lat, peak_lon)

    if "rossmo" not in peaks:
        return pd.DataFrame(columns=columns)

    rossmo_peak = peaks["rossmo"]
    rows = []
    for decay_type in ("rossmo", "exponencial", "linear", "gaussiana"):
        if decay_type not in peaks:
            continue
        peak_lat, peak_lon = peaks[decay_type]
        distance_to_rossmo = haversine_distance_km(peak_lat, peak_lon, rossmo_peak[0], rossmo_peak[1])
        rows.append(
            {
                "metodo": _DECAY_METHOD_LABELS[decay_type],
                "pico_latitude": round(peak_lat, 6),
                "pico_longitude": round(peak_lon, 6),
                "distancia_ao_rossmo_km": round(distance_to_rossmo, 3),
            }
        )

    return pd.DataFrame(rows, columns=columns)


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
    crimes_with_distances: pd.DataFrame,
    canter_circle: CanterCircle | None,
    operations_base: ProfileZone,
) -> OffenderClassification:
    """Classify the geographic pattern as Marauder or Commuter using Canter's
    Circle Hypothesis: does the estimated operations base fall inside or
    outside the circle whose diameter joins the two farthest-apart crimes?
    """
    if crimes_with_distances.empty or canter_circle is None or operations_base.center is None:
        return OffenderClassification(
            category="Indeterminado",
            confidence=0.0,
            justification="Sem dados suficientes para classificação geográfica.",
        )

    distance_to_circle_center = haversine_distance_km(
        operations_base.center.latitude,
        operations_base.center.longitude,
        canter_circle.center.latitude,
        canter_circle.center.longitude,
    )
    ratio = 0.0 if canter_circle.radius_km <= 0 else distance_to_circle_center / canter_circle.radius_km

    id_a, id_b = canter_circle.farthest_pair
    circle_reference = (
        f"Círculo de Canter (raio {canter_circle.radius_km:.2f} km, definido pelos "
        f"crimes #{id_a} e #{id_b}, os mais distantes entre si da série)"
    )
    base_reference = (
        f"{operations_base.center.latitude:.6f}, {operations_base.center.longitude:.6f}"
    )

    if ratio <= 1.0:
        return OffenderClassification(
            category="Marauder (Predador Local)",
            confidence=round(min(95.0, 60 + (1 - ratio) * 35), 1),
            justification=(
                f"A base estimada ({base_reference}) está dentro do {circle_reference}, "
                "compatível com hipótese de Saqueador/Marauder: o autor atua a partir de "
                "uma base fixa e comete crimes dentro de sua área de familiaridade."
            ),
        )

    return OffenderClassification(
        category="Commuter (Viajante)",
        confidence=round(min(95.0, 60 + min(ratio - 1, 1) * 35), 1),
        justification=(
            f"A base estimada ({base_reference}) está fora do {circle_reference}, "
            "compatível com hipótese de Passageiro/Commuter: o autor se desloca até a "
            "área de ataque, que não coincide com sua região de residência habitual."
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
    rossmo_surface: list[list[float]] | None = None,
    buffer_km: float = 0.5,
    barreiras_geograficas: str = "",
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
    buffer_text = build_buffer_zone_text(crimes_with_distances, buffer_km)
    rossmo_text = build_rossmo_profile_text(rossmo_surface, operations_base)
    barreiras_text = build_barreiras_geograficas_text(barreiras_geograficas)

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
        "zona_de_buffer": buffer_text,
        "perfil_rossmo": rossmo_text,
        "barreiras_geograficas": barreiras_text,
        "hipoteses_investigativas": (
            "Priorizar verificação de vínculos territoriais na zona de conforto e na base "
            "estimada, cruzando com reincidência horária, vias de acesso, registros locais "
            "e padrões de modus operandi."
        ),
        "limitacoes_metodologicas": (
            "Relatório exploratório, não conclusão pericial. Não considera rede viária, "
            "barreiras urbanas, subnotificacao, oportunidade criminal, vitimologia, "
            "tempo de permanência, deslocamento real ou dados externos de inteligência. "
            "O método de Rossmo (CGT) pressupõe: (1) o infrator possui uma única base "
            "estável ao longo da série; (2) cada crime resulta de uma busca geográfica "
            "originada dessa base; (3) o crime ocorre onde o infrator encontra o alvo; "
            "(4) mais de uma base, ou uma base que muda durante a série, distorce e pode "
            "invalidar o perfil; (5) em alguns casos é possível identificar mais de uma "
            "base no próprio padrão espacial."
        ),
    }


def build_buffer_zone_text(crimes_with_distances: pd.DataFrame, buffer_km: float) -> str:
    """Build interpretation text for the buffer-zone crime classification."""
    if "dentro_zona_buffer" not in crimes_with_distances.columns:
        return "Sem dados suficientes para classificar a zona de buffer."

    total = len(crimes_with_distances)
    inside = int(crimes_with_distances["dentro_zona_buffer"].sum())
    outside = total - inside
    inside_pct = (inside / total * 100) if total else 0.0

    return (
        f"Das {total} ocorrências, {inside} ({inside_pct:.1f}%) estão dentro do raio de "
        f"buffer de {buffer_km:.2f} km em torno do CGC e {outside} estão fora. Alta "
        "concentração dentro do buffer sugere padrão Saqueador/Marauder; alta proporção "
        "fora do buffer sugere padrão Passageiro/Commuter ou possível efeito de zona de "
        "segurança (evitação de crimes muito próximos da própria base)."
    )


def build_rossmo_profile_text(
    rossmo_surface: list[list[float]] | None,
    operations_base: ProfileZone,
) -> str:
    """Build interpretation text citing the Rossmo (CGT) probability surface peak."""
    if not rossmo_surface:
        return "Sem dados suficientes para gerar o perfil de Rossmo (CGT)."

    peak_lat, peak_lon, peak_score = max(rossmo_surface, key=lambda point: point[2])
    base_reference = ""
    if operations_base.center is not None:
        base_reference = (
            " Esse ponto deve ser comparado com a Base de Operações estimada em "
            f"{operations_base.center.latitude:.6f}, {operations_base.center.longitude:.6f}."
        )

    return (
        f"O modelo de Rossmo (CGT) aponta maior probabilidade de base do infrator "
        f"próximo a {peak_lat:.6f}, {peak_lon:.6f} (score normalizado {peak_score:.2f})."
        f"{base_reference}"
    )


def build_barreiras_geograficas_text(barreiras_geograficas: str) -> str:
    """Build interpretation text for the analyst's geographic-barriers note."""
    if not barreiras_geograficas.strip():
        return (
            "Nenhuma barreira geográfica foi registrada para este caso. Rios, rodovias e "
            "outras barreiras podem limitar o deslocamento real do infrator além do que a "
            "distância em linha reta indica."
        )

    return (
        f"Barreiras geográficas anotadas pelo analista: {barreiras_geograficas.strip()}. "
        "Essas barreiras devem ser consideradas ao interpretar as zonas estimadas, já que "
        "a análise atual usa apenas distância em linha reta (não considera rede viária real)."
    )


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
        "zona_de_buffer": "Sem dados suficientes para classificar a zona de buffer.",
        "perfil_rossmo": "Sem dados suficientes para gerar o perfil de Rossmo (CGT).",
        "barreiras_geograficas": "Sem dados suficientes para considerar barreiras geográficas.",
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
