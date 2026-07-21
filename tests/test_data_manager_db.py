"""Tests for the SQLite-backed multi-case data layer in src/data_manager.py."""

from __future__ import annotations

from datetime import date, time

import pandas as pd
import pytest

from src import data_manager, db


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Point the database and legacy CSV seed at a throwaway temp directory."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "geoprofiler.db")
    monkeypatch.setattr(data_manager, "DATA_PATH", tmp_path / "crimes.csv")


def _write_seed_csv(path, rows=2):
    header = "id,tipo_crime,data,hora,latitude,longitude,cidade,bairro,modus_operandi,observacoes\n"
    lines = [
        f"{i},Furto,2026-01-0{i},10:00,-23.5,-46.6,Sao Paulo,Centro,Teste,Registro {i}\n"
        for i in range(1, rows + 1)
    ]
    path.write_text(header + "".join(lines), encoding="utf-8")


def test_bootstrap_creates_schema_without_seed_csv():
    data_manager.bootstrap_case_database()
    assert db.DB_PATH.exists()
    assert data_manager.list_casos().empty


def test_bootstrap_migrates_legacy_csv_once():
    _write_seed_csv(data_manager.DATA_PATH, rows=3)

    data_manager.bootstrap_case_database()
    casos = data_manager.list_casos()
    assert len(casos) == 1
    assert casos.iloc[0]["nome"] == data_manager.DEFAULT_CASO_NOME
    assert int(casos.iloc[0]["total_crimes"]) == 3

    # Running bootstrap again must not duplicate the migrated case.
    data_manager.bootstrap_case_database()
    assert len(data_manager.list_casos()) == 1


def test_create_and_list_casos():
    data_manager.bootstrap_case_database()
    caso_id = data_manager.create_caso(
        data_manager.CasoInput(
            nome="Caso Teste",
            descricao="Descrição",
            responsavel="Investigador",
            data_abertura=date(2026, 1, 1),
            notas="",
        )
    )

    casos = data_manager.list_casos()
    assert len(casos) == 1
    assert casos.iloc[0]["id"] == caso_id
    assert casos.iloc[0]["total_crimes"] == 0


def test_save_case_crime_record_scopes_to_its_case():
    data_manager.bootstrap_case_database()
    caso_a = data_manager.create_caso(
        data_manager.CasoInput("Caso A", "", "", date(2026, 1, 1), "")
    )
    caso_b = data_manager.create_caso(
        data_manager.CasoInput("Caso B", "", "", date(2026, 1, 1), "")
    )

    data_manager.save_case_crime_record(
        caso_a,
        data_manager.CrimeInput(
            tipo_crime="Roubo",
            data=date(2026, 1, 5),
            hora=time(10, 0),
            latitude=-23.5,
            longitude=-46.6,
            cidade="Sao Paulo",
            bairro="Centro",
            modus_operandi="",
            observacoes="",
        ),
    )

    assert len(data_manager.read_case_crimes(caso_a)) == 1
    assert data_manager.read_case_crimes(caso_b).empty

    casos = data_manager.list_casos().set_index("id")
    assert casos.loc[caso_a, "total_crimes"] == 1
    assert casos.loc[caso_b, "total_crimes"] == 0


def test_get_caso_returns_none_for_unknown_id():
    data_manager.bootstrap_case_database()
    assert data_manager.get_caso(999) is None


def test_save_case_crime_records_bulk_inserts_all_rows():
    data_manager.bootstrap_case_database()
    caso_id = data_manager.create_caso(
        data_manager.CasoInput("Caso Bulk", "", "", date(2026, 1, 1), "")
    )

    raw = pd.DataFrame(
        {
            "tipo_crime": ["Roubo", "Furto"],
            "data": ["2026-01-05", "2026-01-06"],
            "hora": ["10:00", "11:00"],
            "latitude": [-23.5, -23.6],
            "longitude": [-46.6, -46.7],
            "cidade": ["Sao Paulo", "Sao Paulo"],
            "bairro": ["Centro", "Bela Vista"],
            "modus_operandi": ["", ""],
            "observacoes": ["", ""],
        }
    )
    prepared = data_manager.prepare_crime_data(raw)

    result = data_manager.save_case_crime_records_bulk(caso_id, prepared)

    assert len(result) == 2
    assert data_manager.get_caso(caso_id).total_crimes == 2
    # Ids are freshly assigned by SQLite, not taken from the source data.
    assert result["id"].notna().all()


def test_ensure_schema_migrates_databases_missing_barreiras_column():
    # Simulate a pre-migration database: casos table without barreiras_geograficas.
    with db.get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE casos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT NOT NULL DEFAULT '',
                responsavel TEXT NOT NULL DEFAULT '',
                data_abertura TEXT,
                notas TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )
            """
        )
        connection.commit()

    db.ensure_schema()

    with db.get_connection() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(casos)")}
    assert "barreiras_geograficas" in columns

    # Idempotent: calling again must not raise (would error on a duplicate ALTER TABLE).
    db.ensure_schema()


def test_caso_barreiras_geograficas_round_trips_through_create_and_update():
    data_manager.bootstrap_case_database()
    caso_id = data_manager.create_caso(
        data_manager.CasoInput(
            nome="Caso Barreiras",
            descricao="",
            responsavel="",
            data_abertura=date(2026, 1, 1),
            notas="",
            barreiras_geograficas="Rio Pinheiros a oeste",
        )
    )

    caso = data_manager.get_caso(caso_id)
    assert caso.barreiras_geograficas == "Rio Pinheiros a oeste"

    data_manager.update_caso(
        caso_id,
        data_manager.CasoInput(
            nome="Caso Barreiras",
            descricao="",
            responsavel="",
            data_abertura=date(2026, 1, 1),
            notas="",
            barreiras_geograficas="Marginal Tietê ao norte",
        ),
    )

    updated = data_manager.get_caso(caso_id)
    assert updated.barreiras_geograficas == "Marginal Tietê ao norte"


def test_ensure_schema_migrates_databases_missing_arquivado_column():
    # Simulate a database that already has barreiras_geograficas but predates archival.
    with db.get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE casos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT NOT NULL DEFAULT '',
                responsavel TEXT NOT NULL DEFAULT '',
                data_abertura TEXT,
                notas TEXT NOT NULL DEFAULT '',
                barreiras_geograficas TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )
            """
        )
        connection.commit()

    db.ensure_schema()

    with db.get_connection() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(casos)")}
        connection.execute("INSERT INTO casos (nome) VALUES ('Caso Pré-migração')")
        connection.commit()
        default_value = connection.execute(
            "SELECT arquivado FROM casos WHERE nome = 'Caso Pré-migração'"
        ).fetchone()["arquivado"]
    assert "arquivado" in columns
    assert default_value == 0

    # Idempotent: calling again must not raise (would error on a duplicate ALTER TABLE).
    db.ensure_schema()


def test_ensure_schema_creates_caso_links_table():
    db.ensure_schema()

    with db.get_connection() as connection:
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "caso_links" in table_names

    # Idempotent: calling again must not raise.
    db.ensure_schema()


def test_create_caso_defaults_to_not_archived():
    data_manager.bootstrap_case_database()
    caso_id = data_manager.create_caso(
        data_manager.CasoInput("Caso Novo", "", "", date(2026, 1, 1), "")
    )

    caso = data_manager.get_caso(caso_id)
    assert caso.arquivado is False


def test_set_caso_archived_toggles_and_list_casos_excludes_by_default():
    data_manager.bootstrap_case_database()
    caso_a = data_manager.create_caso(
        data_manager.CasoInput("Caso A", "", "", date(2026, 1, 1), "")
    )
    caso_b = data_manager.create_caso(
        data_manager.CasoInput("Caso B", "", "", date(2026, 1, 1), "")
    )

    data_manager.set_caso_archived(caso_a, True)

    default_list_ids = set(data_manager.list_casos()["id"])
    assert default_list_ids == {caso_b}

    all_list_ids = set(data_manager.list_casos(include_archived=True)["id"])
    assert all_list_ids == {caso_a, caso_b}

    assert data_manager.get_caso(caso_a).arquivado is True

    data_manager.set_caso_archived(caso_a, False)
    assert caso_a in set(data_manager.list_casos()["id"])
    assert data_manager.get_caso(caso_a).arquivado is False


def test_update_caso_does_not_change_archived_status():
    data_manager.bootstrap_case_database()
    caso_id = data_manager.create_caso(
        data_manager.CasoInput("Caso Arquivado", "", "", date(2026, 1, 1), "")
    )
    data_manager.set_caso_archived(caso_id, True)

    data_manager.update_caso(
        caso_id,
        data_manager.CasoInput("Caso Renomeado", "", "", date(2026, 1, 1), ""),
    )

    assert data_manager.get_caso(caso_id).arquivado is True


def test_link_casos_creates_symmetric_link_visible_from_both_sides():
    data_manager.bootstrap_case_database()
    caso_a = data_manager.create_caso(
        data_manager.CasoInput("Caso A", "", "", date(2026, 1, 1), "")
    )
    caso_b = data_manager.create_caso(
        data_manager.CasoInput("Caso B", "", "", date(2026, 1, 1), "")
    )

    data_manager.link_casos(caso_a, caso_b)

    assert list(data_manager.list_linked_casos(caso_a)["id"]) == [caso_b]
    assert list(data_manager.list_linked_casos(caso_b)["id"]) == [caso_a]


def test_link_casos_is_idempotent_regardless_of_argument_order():
    data_manager.bootstrap_case_database()
    caso_a = data_manager.create_caso(
        data_manager.CasoInput("Caso A", "", "", date(2026, 1, 1), "")
    )
    caso_b = data_manager.create_caso(
        data_manager.CasoInput("Caso B", "", "", date(2026, 1, 1), "")
    )

    data_manager.link_casos(caso_a, caso_b)
    data_manager.link_casos(caso_b, caso_a)

    assert len(data_manager.list_linked_casos(caso_a)) == 1


def test_link_casos_ignores_self_link():
    data_manager.bootstrap_case_database()
    caso_a = data_manager.create_caso(
        data_manager.CasoInput("Caso A", "", "", date(2026, 1, 1), "")
    )

    data_manager.link_casos(caso_a, caso_a)

    assert data_manager.list_linked_casos(caso_a).empty


def test_unlink_casos_removes_link_regardless_of_argument_order():
    data_manager.bootstrap_case_database()
    caso_a = data_manager.create_caso(
        data_manager.CasoInput("Caso A", "", "", date(2026, 1, 1), "")
    )
    caso_b = data_manager.create_caso(
        data_manager.CasoInput("Caso B", "", "", date(2026, 1, 1), "")
    )
    data_manager.link_casos(caso_a, caso_b)

    data_manager.unlink_casos(caso_b, caso_a)

    assert data_manager.list_linked_casos(caso_a).empty
    assert data_manager.list_linked_casos(caso_b).empty


def test_list_linked_casos_returns_empty_for_case_with_no_links():
    data_manager.bootstrap_case_database()
    caso_id = data_manager.create_caso(
        data_manager.CasoInput("Caso Solo", "", "", date(2026, 1, 1), "")
    )

    assert data_manager.list_linked_casos(caso_id).empty
