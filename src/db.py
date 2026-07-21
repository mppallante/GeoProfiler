"""SQLite connection and schema management for GeoProfiler."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = Path(os.environ.get("GEOPROFILER_RUNTIME_DIR", PROJECT_ROOT))
DB_PATH = RUNTIME_ROOT / "data" / "geoprofiler.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS casos (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                   TEXT NOT NULL,
    descricao              TEXT NOT NULL DEFAULT '',
    responsavel            TEXT NOT NULL DEFAULT '',
    data_abertura          TEXT,
    notas                  TEXT NOT NULL DEFAULT '',
    barreiras_geograficas  TEXT NOT NULL DEFAULT '',
    arquivado              INTEGER NOT NULL DEFAULT 0,
    created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
);

CREATE TABLE IF NOT EXISTS crimes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_id         INTEGER NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
    tipo_crime      TEXT NOT NULL,
    data            TEXT NOT NULL,
    hora            TEXT NOT NULL DEFAULT '',
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    cidade          TEXT NOT NULL DEFAULT '',
    bairro          TEXT NOT NULL DEFAULT '',
    modus_operandi  TEXT NOT NULL DEFAULT '',
    observacoes     TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
);

CREATE INDEX IF NOT EXISTS idx_crimes_caso_id ON crimes(caso_id);

CREATE TABLE IF NOT EXISTS caso_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_id_a   INTEGER NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
    caso_id_b   INTEGER NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    UNIQUE(caso_id_a, caso_id_b),
    CHECK (caso_id_a < caso_id_b)
);

CREATE INDEX IF NOT EXISTS idx_caso_links_caso_id_a ON caso_links(caso_id_a);
CREATE INDEX IF NOT EXISTS idx_caso_links_caso_id_b ON caso_links(caso_id_b);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection to the GeoProfiler SQLite database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def ensure_schema() -> None:
    """Create the casos/crimes/caso_links tables and indexes if they do not exist yet."""
    with get_connection() as connection:
        connection.executescript(SCHEMA)
        _migrate_add_barreiras_geograficas_column(connection)
        _migrate_add_arquivado_column(connection)


def _migrate_add_barreiras_geograficas_column(connection: sqlite3.Connection) -> None:
    """Add casos.barreiras_geograficas for databases created before this column existed."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(casos)")}
    if "barreiras_geograficas" not in columns:
        connection.execute(
            "ALTER TABLE casos ADD COLUMN barreiras_geograficas TEXT NOT NULL DEFAULT ''"
        )
        connection.commit()


def _migrate_add_arquivado_column(connection: sqlite3.Connection) -> None:
    """Add casos.arquivado for databases created before archival existed."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(casos)")}
    if "arquivado" not in columns:
        connection.execute("ALTER TABLE casos ADD COLUMN arquivado INTEGER NOT NULL DEFAULT 0")
        connection.commit()
