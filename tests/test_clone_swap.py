from __future__ import annotations

import pytest

from odooctl.odoo.db_swap import quote_identifier, quote_literal, swap_temp_database


class FakePostgres:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def psql(self, db_name: str, sql: str) -> None:
        self.calls.append((db_name, sql))


def test_swap_temp_database_terminates_drops_and_renames_target():
    pg = FakePostgres()

    swap_temp_database(pg, temp_db="odoo_staging_incoming", target_db="odoo_staging", target_env_name="staging")

    assert pg.calls == [
        (
            "postgres",
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'odoo_staging' AND pid <> pg_backend_pid();",
        ),
        ("postgres", 'DROP DATABASE IF EXISTS "odoo_staging";'),
        ("postgres", 'ALTER DATABASE "odoo_staging_incoming" RENAME TO "odoo_staging";'),
    ]


def test_swap_refuses_production_target():
    with pytest.raises(RuntimeError, match="production"):
        swap_temp_database(FakePostgres(), temp_db="prod_incoming", target_db="prod", target_env_name="production")


def test_database_quoting_handles_special_characters():
    assert quote_identifier('weird"db') == '"weird""db"'
    assert quote_literal("team's db") == "'team''s db'"
