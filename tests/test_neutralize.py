import pytest

from odooctl.odoo.neutralize import (
    build_neutralize_args,
    compose_neutralizer,
    neutralize_compose,
    supports_neutralize,
)


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("19.0", True),
        ("17.0", True),
        ("16.0", True),
        ("15.0", False),
        ("14.0", False),
        ("saas-16.4", False),  # unparseable major falls back to SQL-only
        ("", False),
    ],
)
def test_supports_neutralize_gates_on_major_version(version, expected):
    assert supports_neutralize(version) is expected


def test_build_neutralize_args_minimal():
    assert build_neutralize_args("staging_db") == ["odoo", "neutralize", "-d", "staging_db"]


def test_build_neutralize_args_full_connection():
    args = build_neutralize_args(
        "staging_db", db_host="postgres", db_user="odoo", config_path="/etc/odoo/odoo.conf"
    )
    assert args == [
        "odoo", "neutralize", "-d", "staging_db",
        "-c", "/etc/odoo/odoo.conf",
        "--db_host", "postgres",
        "--db_user", "odoo",
    ]


class FakeCompose:
    def __init__(self):
        self.calls = []

    def exec(self, service, args, *, stream=True, extra_env=None):
        self.calls.append((service, args, stream, extra_env))


def test_neutralize_compose_passes_password_via_env_not_argv(monkeypatch):
    monkeypatch.setenv("ODOO_DB_PASSWORD", "s3cret")
    compose = FakeCompose()
    neutralize_compose(
        compose, "odoo", "staging_db", db_password_env="ODOO_DB_PASSWORD"
    )
    (service, args, stream, extra_env) = compose.calls[0]
    assert service == "odoo"
    assert args[:4] == ["odoo", "neutralize", "-d", "staging_db"]
    assert "s3cret" not in " ".join(args)
    assert extra_env == {"PGPASSWORD": "s3cret"}


def test_neutralize_compose_fails_on_missing_password_env(monkeypatch):
    monkeypatch.delenv("ODOO_DB_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="ODOO_DB_PASSWORD"):
        neutralize_compose(
            FakeCompose(), "odoo", "staging_db", db_password_env="ODOO_DB_PASSWORD"
        )


def test_compose_neutralizer_binds_connection_details():
    compose = FakeCompose()
    runner = compose_neutralizer(
        compose, "odoo", db_host="postgres", db_user="odoo", config_path="/etc/odoo/odoo.conf"
    )
    runner("odoo_staging_incoming")
    (service, args, _stream, _env) = compose.calls[0]
    assert service == "odoo"
    assert args == [
        "odoo", "neutralize", "-d", "odoo_staging_incoming",
        "-c", "/etc/odoo/odoo.conf",
        "--db_host", "postgres",
        "--db_user", "odoo",
    ]
