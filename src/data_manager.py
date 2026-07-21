"""Case and crime data access, validation, and persistence for GeoProfiler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

import pandas as pd

from src import db
from src.utils import normalize_column_names

PROJECT_ROOT = db.PROJECT_ROOT
RUNTIME_ROOT = db.RUNTIME_ROOT
DATA_PATH = RUNTIME_ROOT / "data" / "crimes.csv"

CRIME_COLUMNS = [
    "id",
    "tipo_crime",
    "data",
    "hora",
    "latitude",
    "longitude",
    "cidade",
    "bairro",
    "modus_operandi",
    "observacoes",
]

REQUIRED_COLUMNS = {"tipo_crime", "data", "latitude", "longitude"}

DEFAULT_CASO_NOME = "Caso Exemplo"


@dataclass(frozen=True)
class CrimeInput:
    """Validated form data used to create a crime record."""

    tipo_crime: str
    data: date
    hora: time
    latitude: float
    longitude: float
    cidade: str
    bairro: str
    modus_operandi: str
    observacoes: str


@dataclass(frozen=True)
class CasoInput:
    """Validated form data used to create or update a case."""

    nome: str
    descricao: str
    responsavel: str
    data_abertura: date
    notas: str
    barreiras_geograficas: str = ""


@dataclass(frozen=True)
class Caso:
    """A case (crime series/investigation) and its summary metadata."""

    id: int
    nome: str
    descricao: str
    responsavel: str
    data_abertura: str
    notas: str
    barreiras_geograficas: str
    arquivado: bool
    total_crimes: int
    created_at: str
    updated_at: str


def validate_coordinates(latitude: float, longitude: float) -> None:
    """Validate latitude and longitude ranges."""
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude deve estar entre -90 e 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude deve estar entre -180 e 180.")


def prepare_crime_data(data: pd.DataFrame) -> pd.DataFrame:
    """Apply cleanup and schema normalization needed by the application."""
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    cleaned = data.copy()
    cleaned = add_missing_columns(cleaned)
    cleaned = migrate_legacy_columns(cleaned)

    cleaned["id"] = pd.to_numeric(cleaned["id"], errors="coerce")
    cleaned["data"] = pd.to_datetime(cleaned["data"], errors="coerce")
    cleaned["hora"] = cleaned["hora"].fillna("").astype(str)
    cleaned["latitude"] = pd.to_numeric(cleaned["latitude"], errors="coerce")
    cleaned["longitude"] = pd.to_numeric(cleaned["longitude"], errors="coerce")
    cleaned["tipo_crime"] = cleaned["tipo_crime"].fillna("").astype(str)
    cleaned["cidade"] = cleaned["cidade"].fillna("").astype(str)
    cleaned["bairro"] = cleaned["bairro"].fillna("").astype(str)
    cleaned["modus_operandi"] = cleaned["modus_operandi"].fillna("").astype(str)
    cleaned["observacoes"] = cleaned["observacoes"].fillna("").astype(str)

    cleaned = cleaned.dropna(subset=["data", "latitude", "longitude"])
    cleaned = cleaned[
        cleaned["latitude"].between(-90, 90)
        & cleaned["longitude"].between(-180, 180)
    ]
    cleaned = cleaned.sort_values(["data", "id"], ascending=[False, False])
    cleaned = cleaned.reset_index(drop=True)
    cleaned = cleaned[CRIME_COLUMNS]

    return cleaned


def add_missing_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Add absent schema columns with empty default values."""
    normalized = data.copy()
    for column in CRIME_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    return normalized


def migrate_legacy_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Preserve values from the first sample CSV format."""
    migrated = data.copy()

    if "local" in migrated.columns:
        empty_bairro = migrated["bairro"].isna() | (migrated["bairro"].astype(str) == "")
        migrated.loc[empty_bairro, "bairro"] = migrated.loc[empty_bairro, "local"]

    return migrated


def bootstrap_case_database() -> None:
    """Ensure the SQLite schema exists, migrating the legacy CSV seed once."""
    db_existed = db.DB_PATH.exists()
    db.ensure_schema()

    if not db_existed:
        _migrate_legacy_seed_data()


def _migrate_legacy_seed_data() -> None:
    """One-shot import of the legacy data/crimes.csv into a seed case."""
    if not DATA_PATH.exists():
        return

    raw = pd.read_csv(DATA_PATH)
    crimes = prepare_crime_data(normalize_column_names(raw))
    if crimes.empty:
        return

    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO casos (nome, descricao, responsavel, data_abertura, notas)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_CASO_NOME,
                "Caso gerado automaticamente a partir da base inicial (data/crimes.csv).",
                "",
                crimes["data"].min().date().isoformat(),
                "",
            ),
        )
        caso_id = cursor.lastrowid

        connection.executemany(
            """
            INSERT INTO crimes
                (id, caso_id, tipo_crime, data, hora, latitude, longitude,
                 cidade, bairro, modus_operandi, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    int(row.id),
                    caso_id,
                    row.tipo_crime,
                    row.data.date().isoformat(),
                    row.hora,
                    row.latitude,
                    row.longitude,
                    row.cidade,
                    row.bairro,
                    row.modus_operandi,
                    row.observacoes,
                )
                for row in crimes.itertuples()
            ],
        )
        connection.commit()


def create_caso(caso_input: CasoInput) -> int:
    """Create a new case and return its id."""
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO casos (nome, descricao, responsavel, data_abertura, notas, barreiras_geograficas)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                caso_input.nome.strip(),
                caso_input.descricao.strip(),
                caso_input.responsavel.strip(),
                caso_input.data_abertura.isoformat(),
                caso_input.notas.strip(),
                caso_input.barreiras_geograficas.strip(),
            ),
        )
        connection.commit()
        return cursor.lastrowid


def update_caso(caso_id: int, caso_input: CasoInput) -> None:
    """Update an existing case's metadata."""
    with db.get_connection() as connection:
        connection.execute(
            """
            UPDATE casos
            SET nome = ?, descricao = ?, responsavel = ?, data_abertura = ?, notas = ?,
                barreiras_geograficas = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
            WHERE id = ?
            """,
            (
                caso_input.nome.strip(),
                caso_input.descricao.strip(),
                caso_input.responsavel.strip(),
                caso_input.data_abertura.isoformat(),
                caso_input.notas.strip(),
                caso_input.barreiras_geograficas.strip(),
                caso_id,
            ),
        )
        connection.commit()


def list_casos(include_archived: bool = False) -> pd.DataFrame:
    """List cases with their crime counts, most recently created first.

    Archived cases are excluded by default; pass include_archived=True to
    also list them (used by the "Mostrar arquivados" toggle in casos.py).
    """
    where_clause = "" if include_archived else "WHERE casos.arquivado = 0"
    with db.get_connection() as connection:
        return pd.read_sql_query(
            f"""
            SELECT
                casos.id,
                casos.nome,
                casos.descricao,
                casos.responsavel,
                casos.data_abertura,
                casos.notas,
                casos.barreiras_geograficas,
                casos.arquivado,
                casos.created_at,
                casos.updated_at,
                COUNT(crimes.id) AS total_crimes
            FROM casos
            LEFT JOIN crimes ON crimes.caso_id = casos.id
            {where_clause}
            GROUP BY casos.id
            ORDER BY casos.created_at DESC
            """,
            connection,
        )


def get_caso(caso_id: int) -> Caso | None:
    """Fetch a single case by id, including its crime count."""
    with db.get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                casos.id,
                casos.nome,
                casos.descricao,
                casos.responsavel,
                casos.data_abertura,
                casos.notas,
                casos.barreiras_geograficas,
                casos.arquivado,
                casos.created_at,
                casos.updated_at,
                COUNT(crimes.id) AS total_crimes
            FROM casos
            LEFT JOIN crimes ON crimes.caso_id = casos.id
            WHERE casos.id = ?
            GROUP BY casos.id
            """,
            (caso_id,),
        ).fetchone()

    if row is None:
        return None

    data = dict(row)
    data["arquivado"] = bool(data["arquivado"])
    return Caso(**data)


def set_caso_archived(caso_id: int, arquivado: bool) -> None:
    """Archive or reactivate a case without touching its other metadata."""
    with db.get_connection() as connection:
        connection.execute(
            """
            UPDATE casos
            SET arquivado = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
            WHERE id = ?
            """,
            (1 if arquivado else 0, caso_id),
        )
        connection.commit()


def read_case_crimes(caso_id: int) -> pd.DataFrame:
    """Read all crimes for a case, normalized to the canonical schema."""
    with db.get_connection() as connection:
        raw = pd.read_sql_query(
            "SELECT * FROM crimes WHERE caso_id = ?",
            connection,
            params=(caso_id,),
        )

    raw = raw.drop(columns=["caso_id", "created_at", "updated_at"], errors="ignore")
    return prepare_crime_data(raw)


def save_case_crime_record(caso_id: int, crime_input: CrimeInput) -> pd.DataFrame:
    """Persist a validated crime record for a case and return its updated crimes."""
    with db.get_connection() as connection:
        connection.execute(
            """
            INSERT INTO crimes
                (caso_id, tipo_crime, data, hora, latitude, longitude,
                 cidade, bairro, modus_operandi, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                caso_id,
                crime_input.tipo_crime.strip(),
                crime_input.data.isoformat(),
                crime_input.hora.strftime("%H:%M"),
                crime_input.latitude,
                crime_input.longitude,
                crime_input.cidade.strip(),
                crime_input.bairro.strip(),
                crime_input.modus_operandi.strip(),
                crime_input.observacoes.strip(),
            ),
        )
        connection.commit()

    return read_case_crimes(caso_id)


def save_case_crime_records_bulk(caso_id: int, crimes: pd.DataFrame) -> pd.DataFrame:
    """Bulk-insert already-validated crime records (from prepare_crime_data) for a case.

    Any `id` column on `crimes` is ignored: imported rows always get fresh
    SQLite-assigned ids, since they are new records being added to the case.
    """
    if crimes.empty:
        return read_case_crimes(caso_id)

    with db.get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO crimes
                (caso_id, tipo_crime, data, hora, latitude, longitude,
                 cidade, bairro, modus_operandi, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    caso_id,
                    row.tipo_crime,
                    row.data.date().isoformat(),
                    row.hora,
                    row.latitude,
                    row.longitude,
                    row.cidade,
                    row.bairro,
                    row.modus_operandi,
                    row.observacoes,
                )
                for row in crimes.itertuples()
            ],
        )
        connection.commit()

    return read_case_crimes(caso_id)


def _normalize_pair(caso_id_a: int, caso_id_b: int) -> tuple[int, int]:
    """Order a pair of case ids so the smaller id is always first (caso_id_a)."""
    return (caso_id_a, caso_id_b) if caso_id_a < caso_id_b else (caso_id_b, caso_id_a)


def link_casos(caso_id_a: int, caso_id_b: int) -> None:
    """Create a symmetric link between two cases.

    No-op for a self-link. Idempotent otherwise: linking an already-linked
    pair, in either argument order, changes nothing.
    """
    if caso_id_a == caso_id_b:
        return

    id_a, id_b = _normalize_pair(caso_id_a, caso_id_b)
    with db.get_connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO caso_links (caso_id_a, caso_id_b) VALUES (?, ?)",
            (id_a, id_b),
        )
        connection.commit()


def unlink_casos(caso_id_a: int, caso_id_b: int) -> None:
    """Remove the link between two cases, if any (either argument order)."""
    id_a, id_b = _normalize_pair(caso_id_a, caso_id_b)
    with db.get_connection() as connection:
        connection.execute(
            "DELETE FROM caso_links WHERE caso_id_a = ? AND caso_id_b = ?",
            (id_a, id_b),
        )
        connection.commit()


def list_linked_casos(caso_id: int) -> pd.DataFrame:
    """List the other case in every link involving caso_id.

    Same column shape as list_casos(), so casos.py can reuse the same row
    rendering. Matches caso_id on either side of the pair via a UNION of the
    two link directions, then joins that id set back to casos.
    """
    with db.get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                casos.id,
                casos.nome,
                casos.descricao,
                casos.responsavel,
                casos.data_abertura,
                casos.notas,
                casos.barreiras_geograficas,
                casos.arquivado,
                casos.created_at,
                casos.updated_at,
                COUNT(crimes.id) AS total_crimes
            FROM casos
            LEFT JOIN crimes ON crimes.caso_id = casos.id
            WHERE casos.id IN (
                SELECT caso_id_b FROM caso_links WHERE caso_id_a = ?
                UNION
                SELECT caso_id_a FROM caso_links WHERE caso_id_b = ?
            )
            GROUP BY casos.id
            ORDER BY casos.created_at DESC
            """,
            connection,
            params=(caso_id, caso_id),
        )
