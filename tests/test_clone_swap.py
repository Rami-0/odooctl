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


def test_swap_refuses_protected_target():
    pg = FakePostgres()
    with pytest.raises(RuntimeError, match="protected environment 'production'"):
        swap_temp_database(
            pg,
            temp_db="prod_incoming",
            target_db="prod",
            target_env_name="production",
            is_protected_fn=lambda name: name == "production",
        )
    assert pg.calls == []


def test_swap_refuses_protected_tier_target_with_non_production_name():
    pg = FakePostgres()
    with pytest.raises(RuntimeError, match="protected environment 'prod-eu'"):
        swap_temp_database(
            pg,
            temp_db="prod_eu_incoming",
            target_db="prod_eu",
            target_env_name="prod-eu",
            is_protected_fn=lambda name: True,  # config says tier: production
        )
    assert pg.calls == []


def test_swap_allows_unprotected_target_per_config_policy():
    pg = FakePostgres()
    swap_temp_database(
        pg,
        temp_db="odoo_staging_incoming",
        target_db="odoo_staging",
        target_env_name="staging",
        is_protected_fn=lambda name: name == "production",
    )
    assert len(pg.calls) == 3


def test_database_quoting_handles_special_characters():
    assert quote_identifier('weird"db') == '"weird""db"'
    assert quote_literal("team's db") == "'team''s db'"
