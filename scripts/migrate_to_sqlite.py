"""CLI wrapper to migrate the legacy data/crimes.csv seed into the SQLite database.

Usage: python -m scripts.migrate_to_sqlite
"""

from __future__ import annotations

from src.data_manager import DEFAULT_CASO_NOME, bootstrap_case_database, list_casos
from src.db import DB_PATH


def main() -> None:
    db_existed = DB_PATH.exists()
    bootstrap_case_database()

    if db_existed:
        print(f"Banco de dados já existia em {DB_PATH}; nada foi migrado.")
        return

    casos = list_casos()
    seed_row = casos[casos["nome"] == DEFAULT_CASO_NOME]
    total = int(seed_row["total_crimes"].iloc[0]) if not seed_row.empty else 0
    print(f"Banco de dados criado em {DB_PATH}.")
    print(f"Migrado '{DEFAULT_CASO_NOME}' com {total} ocorrência(s) a partir de data/crimes.csv.")


if __name__ == "__main__":
    main()
