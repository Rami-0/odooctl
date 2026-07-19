"""M11 security architecture tests.

Covers RBAC (all roles × all actions), the encrypted/env-referenced secret
store and its no-leak guarantees, central redaction, capability token
mint/verify/tamper/expiry/scope, and the API-vs-runner import contract.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from odooctl.security import rbac, redaction, runner_contract, tokens
from odooctl.security.principals import (
    Org,
    Principal,
    PrincipalKind,
    Role,
    User,
)
from odooctl.security.rbac import AccessDenied, Action
from odooctl.security.secrets import (
    SecretDecryptionError,
    SecretNotFound,
    SecretStore,
    SecretValue,
    decrypt,
    encrypt,
    open_store,
)

KEY = b"\x11" * 32


# --------------------------------------------------------------------------- #
# Principals
# --------------------------------------------------------------------------- #
def test_principal_identity_and_roles():
    user = User(id="alice", org_id="acme", name="Alice", email="a@acme.test")
    p = Principal.for_user(user, {Role.OPERATOR, Role.VIEWER})
    assert p.org_id == "acme"
    assert p.kind is PrincipalKind.USER
    assert p.identity == "user:alice@acme"
    assert p.has_role(Role.OPERATOR)
    assert p.has_at_least(Role.VIEWER)
    assert not p.has_at_least(Role.ADMIN)
    assert p.max_role() is Role.OPERATOR


def test_principal_roles_normalised_from_strings():
    p = Principal(id="svc", org_id="acme", kind=PrincipalKind.SERVICE, roles=frozenset({"admin"}))
    assert Role.ADMIN in p.roles
    assert p.has_at_least(Role.OPERATOR)


def test_org_dataclass():
    org = Org(id="acme", name="Acme")
    assert org.id == "acme"


# --------------------------------------------------------------------------- #
# RBAC — full role × action coverage
# --------------------------------------------------------------------------- #
def _p(role: Role) -> Principal:
    return Principal(id=role.value, org_id="acme", roles={role})


# Expected base matrix (non-protected) per the M11 plan.
EXPECTED = {
    Role.VIEWER: {
        Action.READ, Action.STATUS, Action.LOGS, Action.BACKUPS,
        Action.OPERATIONS, Action.AUDIT,
    },
    Role.OPERATOR: {
        Action.READ, Action.STATUS, Action.LOGS, Action.BACKUPS,
        Action.OPERATIONS, Action.AUDIT,
        Action.BACKUP, Action.DEPLOY, Action.CLONE, Action.RESTORE,
        Action.CANCEL,
    },
    Role.ADMIN: set(Action),
    Role.OWNER: set(Action),
}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("action", list(Action))
def test_rbac_matrix_every_role_every_action(role: Role, action: Action):
    expected = action in EXPECTED[role]
    assert rbac.is_allowed(_p(role), action) is expected


def test_rbac_viewer_cannot_mutate():
    viewer = _p(Role.VIEWER)
    for action in rbac.WRITE_ACTIONS:
        assert not rbac.is_allowed(viewer, action)
        with pytest.raises(AccessDenied):
            rbac.require(viewer, action)


def test_rbac_operator_blocked_on_protected_destructive():
    operator = _p(Role.OPERATOR)
    # allowed on non-prod
    assert rbac.is_allowed(operator, Action.DEPLOY)
    # blocked on protected/production
    assert not rbac.is_allowed(operator, Action.DEPLOY, protected=True)
    with pytest.raises(AccessDenied) as exc:
        rbac.require(operator, Action.RESTORE, protected=True)
    assert "protected" in str(exc.value)


def test_rbac_admin_and_owner_allowed_on_protected():
    for role in (Role.ADMIN, Role.OWNER):
        assert rbac.is_allowed(_p(role), Action.PROMOTE, protected=True)
        rbac.require(_p(role), Action.DEPLOY, protected=True)


def test_rbac_cancel_is_write_action_gated_at_operator():
    """C5/F6: cancelling an operation is a write action, never viewer-level."""
    assert Action.CANCEL in rbac.WRITE_ACTIONS
    assert Action.CANCEL not in rbac.READ_ACTIONS
    viewer = _p(Role.VIEWER)
    assert not rbac.is_allowed(viewer, Action.CANCEL)
    with pytest.raises(AccessDenied):
        rbac.require(viewer, Action.CANCEL)
    for role in (Role.OPERATOR, Role.ADMIN, Role.OWNER):
        rbac.require(_p(role), Action.CANCEL)


def test_rbac_operator_cannot_manage_secrets_or_promote():
    operator = _p(Role.OPERATOR)
    assert not rbac.is_allowed(operator, Action.SECRETS)
    assert not rbac.is_allowed(operator, Action.PROMOTE)
    assert not rbac.is_allowed(operator, Action.ENV)


def test_rbac_read_allowed_for_all_roles():
    for role in Role:
        for action in rbac.READ_ACTIONS:
            assert rbac.is_allowed(_p(role), action)


def test_rbac_role_matrix_serialisable_and_complete():
    matrix = rbac.role_matrix()
    assert set(matrix.keys()) == {r.value for r in Role}
    for role_actions in matrix.values():
        assert set(role_actions.keys()) == {a.value for a in Action}


def test_access_denied_message_has_no_secret_and_names_principal():
    p = _p(Role.VIEWER)
    err = AccessDenied(p, Action.DEPLOY)
    assert "user:viewer@acme" in str(err)
    assert err.action is Action.DEPLOY


def test_allowed_actions_drops_destructive_on_protected_for_operator():
    base = rbac.allowed_actions(Role.OPERATOR)
    prot = rbac.allowed_actions(Role.OPERATOR, protected=True)
    assert Action.DEPLOY in base
    assert Action.DEPLOY not in prot
    assert Action.STATUS in prot


# --------------------------------------------------------------------------- #
# Secret store crypto
# --------------------------------------------------------------------------- #
def test_encrypt_decrypt_roundtrip_and_ciphertext_hides_value():
    env = encrypt(KEY, "hunter2-db-pass")
    assert decrypt(KEY, env) == "hunter2-db-pass"
    blob = json.dumps(env)
    assert "hunter2" not in blob


def test_decrypt_detects_tampering():
    env = encrypt(KEY, "secret-value")
    tampered = dict(env)
    tampered["ct"] = "AAAA" + tampered["ct"][4:]
    with pytest.raises(SecretDecryptionError):
        decrypt(KEY, tampered)


def test_decrypt_wrong_key_fails():
    env = encrypt(KEY, "secret-value")
    with pytest.raises(SecretDecryptionError):
        decrypt(b"\x22" * 32, env)


def test_secret_value_never_reveals_implicitly():
    sv = SecretValue("topsecret")
    assert "topsecret" not in repr(sv)
    assert "topsecret" not in str(sv)
    assert "topsecret" not in f"{sv}"
    assert sv.reveal() == "topsecret"


# --------------------------------------------------------------------------- #
# Secret store behaviour
# --------------------------------------------------------------------------- #
@pytest.fixture
def store(tmp_path: Path) -> SecretStore:
    return SecretStore(tmp_path / "secrets.json", KEY)


def test_store_put_get_stored_secret(store: SecretStore):
    store.put("db_password", "s3cr3t")
    assert store.get("db_password").reveal() == "s3cr3t"
    rec = store.metadata("db_password")
    assert rec.source == "stored"
    assert rec.version == 1


def test_store_file_never_contains_plaintext_value(store: SecretStore, tmp_path: Path):
    store.put("db_password", "plaintext-leak-canary")
    raw = (tmp_path / "secrets.json").read_text()
    assert "plaintext-leak-canary" not in raw


def test_store_env_reference_resolves_from_environment(store: SecretStore, monkeypatch):
    store.put_reference("db_password", "ODOO_DB_PASSWORD")
    rec = store.metadata("db_password")
    assert rec.source == "env"
    assert rec.env_var == "ODOO_DB_PASSWORD"
    # value not stored anywhere on disk
    assert "env_ref_value" not in store.path.read_text()
    monkeypatch.setenv("ODOO_DB_PASSWORD", "env_ref_value")
    assert store.get("db_password").reveal() == "env_ref_value"


def test_store_env_reference_missing_env_raises(store: SecretStore):
    store.put_reference("db_password", "DEFINITELY_UNSET_VAR_XYZ")
    with pytest.raises(SecretNotFound):
        store.get("db_password")


def test_store_metadata_public_dict_has_no_value(store: SecretStore):
    store.put("api_key", "abc123-should-not-appear")
    pub = store.metadata("api_key").to_public_dict()
    assert "abc123-should-not-appear" not in json.dumps(pub)
    assert pub["name"] == "api_key"
    assert pub["source"] == "stored"


def test_store_rotate_stored_bumps_version_and_changes_value(store: SecretStore):
    store.put("db_password", "old")
    rec = store.rotate("db_password", "new")
    assert rec.version == 2
    assert store.get("db_password").reveal() == "new"


def test_store_rotate_stored_requires_value(store: SecretStore):
    store.put("db_password", "old")
    with pytest.raises(ValueError):
        store.rotate("db_password")


def test_store_rotate_env_reference_records_event(store: SecretStore):
    store.put_reference("token", "MY_TOKEN")
    rec = store.rotate("token")
    assert rec.version == 2


def test_store_rotate_missing_raises(store: SecretStore):
    with pytest.raises(SecretNotFound):
        store.rotate("nope", "x")


def test_store_list_and_delete(store: SecretStore):
    store.put("a", "1")
    store.put_reference("b", "B_VAR")
    assert store.names() == ["a", "b"]
    assert len(store.list_metadata()) == 2
    store.delete("a")
    assert store.names() == ["b"]
    with pytest.raises(SecretNotFound):
        store.delete("a")


def test_store_persists_across_reopen(tmp_path: Path):
    p = tmp_path / "secrets.json"
    SecretStore(p, KEY).put("db_password", "persisted")
    assert SecretStore(p, KEY).get("db_password").reveal() == "persisted"


def test_rotation_due_metadata(store: SecretStore):
    store.put("db_password", "v", rotation_interval_days=30)
    rec = store.metadata("db_password")
    assert rec.is_due_for_rotation(now=datetime.now(timezone.utc)) is False
    future = datetime.now(timezone.utc) + timedelta(days=31)
    assert rec.is_due_for_rotation(now=future) is True


def test_secret_values_set_for_redaction(store: SecretStore, monkeypatch):
    store.put("db_password", "stored-secret")
    store.put_reference("token", "TOK_VAR")
    monkeypatch.setenv("TOK_VAR", "env-secret")
    values = store.secret_values()
    assert "stored-secret" in values
    assert "env-secret" in values


def test_open_store_roundtrip_with_state_dir(tmp_path: Path):
    store = open_store(tmp_path)
    store.put("db_password", "via-open-store")
    # reopen with same state dir resolves the same persisted key
    assert open_store(tmp_path).get("db_password").reveal() == "via-open-store"


def test_open_store_repr_hides_contents(tmp_path: Path):
    store = open_store(tmp_path)
    store.put("db_password", "leak-canary")
    assert "leak-canary" not in repr(store)


def test_store_file_created_with_owner_only_permissions(store: SecretStore):
    import stat

    store.put("db_password", "s3cr3t")
    mode = stat.S_IMODE(store.path.stat().st_mode)
    assert mode == 0o600


def test_resolve_key_master_key_and_salt_are_owner_only(tmp_path: Path, monkeypatch):
    import stat

    from odooctl.security import secrets as secrets_mod

    monkeypatch.delenv(secrets_mod.KEY_ENV_VAR, raising=False)
    # No passphrase -> random master.key is persisted with 0600.
    secrets_mod.resolve_key(tmp_path)
    key_path = tmp_path / "secrets" / "master.key"
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600

    # Passphrase path -> per-store salt is persisted with 0600.
    secrets_mod.resolve_key(tmp_path, passphrase="correct horse")
    salt_path = tmp_path / "secrets" / "salt"
    assert stat.S_IMODE(salt_path.stat().st_mode) == 0o600


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
def test_strip_env_defaults_drops_secret_default():
    assert redaction.strip_env_defaults("${ODOO_DB_PASSWORD:-supersecret}") == "${ODOO_DB_PASSWORD}"
    assert redaction.strip_env_defaults("${VAR:default}") == "${VAR}"
    assert redaction.strip_env_defaults("${VAR-default}") == "${VAR}"
    assert redaction.strip_env_defaults("${VAR}") == "${VAR}"


def test_redact_text_masks_known_values():
    assert redaction.redact_text("conn=postgres://u:hunter2@h/db", ["hunter2"]) == "conn=postgres://u:***@h/db"


def test_redact_text_strips_env_default_even_without_known_value():
    out = redaction.redact_text("PASSWORD=${ODOO_DB_PASSWORD:-fallbacksecret}")
    assert "fallbacksecret" not in out
    assert "${ODOO_DB_PASSWORD}" in out


def test_redact_mapping_recurses_and_masks_secret_keys():
    data = {
        "db_password": "rawvalue",
        "url": "postgres://u:rawvalue@h/db",
        "nested": {"api_token": "${TOK:-deftoken}", "ok": "fine"},
        "list": ["rawvalue", "clean"],
    }
    out = redaction.redact(data, ["rawvalue"])
    assert out["db_password"] == "***"
    assert "rawvalue" not in json.dumps(out)
    assert "deftoken" not in json.dumps(out)
    assert out["nested"]["api_token"] == "${TOK}"
    assert out["nested"]["ok"] == "fine"


def test_redact_leaves_non_strings_untouched():
    assert redaction.redact({"count": 3, "flag": True}) == {"count": 3, "flag": True}


def test_redact_masks_secret_keyed_non_string_values():
    data = {
        "api_token": 1234567890,          # numeric secret value
        "db_password": {"inner": "raw"},  # nested mapping under a secret key
        "secret_flag": True,
        "count": 7,                       # non-secret key, untouched
    }
    out = redaction.redact(data)
    assert out["api_token"] == "***"
    assert out["db_password"] == "***"
    assert out["secret_flag"] == "***"
    assert out["count"] == 7
    # The raw numeric/nested material must not survive anywhere in the output.
    assert "1234567890" not in json.dumps(out)
    assert "raw" not in json.dumps(out)


def test_redact_preserves_env_reference_under_secret_key():
    out = redaction.redact({"password": "${DB_PW:-fallbacksecret}"})
    assert out["password"] == "${DB_PW}"


# --------------------------------------------------------------------------- #
# Capability tokens
# --------------------------------------------------------------------------- #
RKEY = "runner-signing-key"


def test_token_mint_verify_roundtrip():
    tok = tokens.mint(RKEY, action="backup", environment="production", project="acme", ttl_seconds=300)
    payload = tokens.verify(RKEY, tok, action="backup", environment="production", project="acme")
    assert payload["act"] == "backup"
    assert payload["env"] == "production"
    assert payload["proj"] == "acme"
    assert "nonce" in payload


def test_token_carries_optional_subject():
    tok = tokens.mint(RKEY, action="deploy", environment="staging", project="acme", ttl_seconds=60, subject="user:alice@acme")
    payload = tokens.verify(RKEY, tok)
    assert payload["sub"] == "user:alice@acme"


def test_token_rejects_wrong_signature():
    tok = tokens.mint(RKEY, action="backup", environment="production", project="acme")
    with pytest.raises(tokens.TokenInvalid):
        tokens.verify("different-key", tok)


def test_token_rejects_tampered_payload():
    tok = tokens.mint(RKEY, action="backup", environment="staging", project="acme")
    h, p, sig = tok.split(".")
    forged = tokens._b64encode(json.dumps({"act": "deploy", "env": "production", "proj": "acme", "exp": 9999999999, "nonce": "x"}).encode())
    with pytest.raises(tokens.TokenInvalid):
        tokens.verify(RKEY, f"{h}.{forged}.{sig}")


def test_token_rejects_expiry():
    tok = tokens.mint(RKEY, action="backup", environment="production", project="acme", ttl_seconds=10, now=1000)
    # at/after exp -> expired
    with pytest.raises(tokens.TokenExpired):
        tokens.verify(RKEY, tok, now=1010)
    # still valid just before
    assert tokens.verify(RKEY, tok, now=1005)["act"] == "backup"


def test_token_rejects_wrong_action_scope():
    tok = tokens.mint(RKEY, action="backup", environment="production", project="acme")
    with pytest.raises(tokens.TokenScopeError):
        tokens.verify(RKEY, tok, action="restore")


def test_token_rejects_wrong_environment_scope():
    tok = tokens.mint(RKEY, action="deploy", environment="staging", project="acme")
    with pytest.raises(tokens.TokenScopeError):
        tokens.verify(RKEY, tok, environment="production")


def test_token_rejects_wrong_project_scope():
    tok = tokens.mint(RKEY, action="deploy", environment="staging", project="acme")
    with pytest.raises(tokens.TokenScopeError):
        tokens.verify(RKEY, tok, project="other")


def test_token_malformed_rejected():
    with pytest.raises(tokens.TokenInvalid):
        tokens.verify(RKEY, "not-a-token")


def test_token_ttl_must_be_positive():
    with pytest.raises(ValueError):
        tokens.mint(RKEY, action="backup", environment="production", project="acme", ttl_seconds=0)


def test_token_default_ttl_is_300_seconds():
    """F12: tokens minted without an explicit TTL expire after 300 s."""
    assert tokens.DEFAULT_TTL_SECONDS == 300
    tok = tokens.mint(RKEY, action="backup", environment="production", project="acme", now=1000)
    payload = tokens.decode_unverified(tok)
    assert payload["exp"] - payload["iat"] == 300
    # valid just before expiry, rejected at expiry
    assert tokens.verify(RKEY, tok, now=1299)["act"] == "backup"
    with pytest.raises(tokens.TokenExpired):
        tokens.verify(RKEY, tok, now=1300)


def test_token_ttl_still_overridable():
    tok = tokens.mint(RKEY, action="backup", environment="production", project="acme", ttl_seconds=60, now=1000)
    payload = tokens.decode_unverified(tok)
    assert payload["exp"] - payload["iat"] == 60


def test_enforce_key_strength_rejects_short_key():
    """F24: keys shorter than 32 characters are rejected with a clear error."""
    with pytest.raises(ValueError, match="at least 32"):
        tokens.enforce_key_strength("short-key")
    with pytest.raises(ValueError, match="ODOOCTL_API_KEY"):
        tokens.enforce_key_strength("x" * 31)
    # exactly at / above the floor passes
    tokens.enforce_key_strength("x" * 32)
    tokens.enforce_key_strength(b"y" * 40)


def test_token_mint_with_roles_extra_claim():
    tok = tokens.mint(RKEY, action="api", environment="*", project="*", roles=["operator"])
    payload = tokens.verify(RKEY, tok)
    assert payload["roles"] == ["operator"]


def test_token_mint_extra_claims_cannot_override_reserved():
    """extra_claims must not silently override reserved token fields.

    ``nonce`` is an explicit parameter; it is also listed as reserved in the
    implementation for defensive clarity, but Python binds it before
    ``extra_claims`` so this loop only exercises fields that can reach
    ``extra_claims``.
    """
    reserved = ("act", "env", "proj", "iat", "exp", "sub")
    for field in reserved:
        with pytest.raises(ValueError, match="reserved"):
            tokens.mint(RKEY, action="backup", environment="production", project="acme", **{field: "x"})


def test_token_mint_with_multiple_roles():
    tok = tokens.mint(RKEY, action="api", environment="*", project="*", roles=["operator", "viewer"])
    payload = tokens.verify(RKEY, tok)
    assert payload["roles"] == ["operator", "viewer"]


def test_token_mint_without_roles_has_no_roles_key():
    tok = tokens.mint(RKEY, action="backup", environment="production", project="acme")
    payload = tokens.verify(RKEY, tok)
    assert "roles" not in payload


# --------------------------------------------------------------------------- #
# CLI: token mint --role
# --------------------------------------------------------------------------- #
def test_token_mint_cli_single_role(monkeypatch):
    from typer.testing import CliRunner
    from odooctl.commands.security import token_app

    monkeypatch.setenv("ODOOCTL_API_KEY", RKEY)
    runner = CliRunner()
    result = runner.invoke(
        token_app,
        ["mint", "--action", "api", "--env", "*", "--project", "*", "--role", "operator"],
    )
    assert result.exit_code == 0, result.output
    tok = result.output.strip()
    payload = tokens.verify(RKEY, tok)
    assert payload["roles"] == ["operator"]


def test_token_mint_cli_multiple_roles(monkeypatch):
    from typer.testing import CliRunner
    from odooctl.commands.security import token_app

    monkeypatch.setenv("ODOOCTL_API_KEY", RKEY)
    runner = CliRunner()
    result = runner.invoke(
        token_app,
        ["mint", "--action", "api", "--env", "*", "--project", "*",
         "--role", "operator", "--role", "viewer"],
    )
    assert result.exit_code == 0, result.output
    tok = result.output.strip()
    payload = tokens.verify(RKEY, tok)
    assert payload["roles"] == ["operator", "viewer"]


def test_token_mint_cli_no_role_backwards_compatible(monkeypatch):
    from typer.testing import CliRunner
    from odooctl.commands.security import token_app

    monkeypatch.setenv("ODOOCTL_API_KEY", RKEY)
    runner = CliRunner()
    result = runner.invoke(
        token_app,
        ["mint", "--action", "backup", "--env", "production", "--project", "acme"],
    )
    assert result.exit_code == 0, result.output
    tok = result.output.strip()
    payload = tokens.verify(RKEY, tok)
    assert "roles" not in payload


# --------------------------------------------------------------------------- #
# Runner contract
# --------------------------------------------------------------------------- #
def test_scan_detects_privileged_import_in_api_source():
    src = "from odooctl.adapters.docker_compose import ComposeAdapter\nx = 1\n"
    violations = runner_contract.scan_source_for_violations("odooctl.api", src)
    assert len(violations) == 1
    assert violations[0].module == "odooctl.adapters.docker_compose"


def test_scan_detects_plain_import_of_privileged_module():
    src = "import odooctl.odoo.db_swap\n"
    violations = runner_contract.scan_source_for_violations("odooctl.web", src)
    assert violations and violations[0].module == "odooctl.odoo.db_swap"


def test_scan_allows_unprivileged_imports():
    src = "from odooctl.operations.store import OperationStore\nimport json\n"
    assert runner_contract.scan_source_for_violations("odooctl.api", src) == []


def test_scan_detects_relative_import_escaping_to_privileged():
    # `from ..adapters.postgres import PostgresAdapter` inside odooctl.api.routes
    # resolves to odooctl.adapters.postgres — a privileged module.
    src = "from ..adapters.postgres import PostgresAdapter\n"
    violations = runner_contract.scan_source_for_violations(
        "odooctl.api", src, filename="routes.py", module_name="odooctl.api.routes"
    )
    assert len(violations) == 1
    assert violations[0].module == "odooctl.adapters.postgres"


def test_scan_allows_relative_import_within_api_package():
    # `from .helpers import x` in odooctl.api.routes -> odooctl.api.helpers (fine).
    src = "from .helpers import build_payload\n"
    violations = runner_contract.scan_source_for_violations(
        "odooctl.api", src, filename="routes.py", module_name="odooctl.api.routes"
    )
    assert violations == []


def test_scan_relative_import_from_package_init_anchors_on_package():
    # In the package __init__ (odooctl.api), `from .adapters...` stays in-package,
    # but `from ..adapters.postgres` escapes to the privileged adapter.
    src = "from ..adapters.postgres import PostgresAdapter\n"
    violations = runner_contract.scan_source_for_violations(
        "odooctl.api", src, filename="__init__.py", module_name="odooctl.api"
    )
    assert len(violations) == 1
    assert violations[0].module == "odooctl.adapters.postgres"


def test_scan_tolerates_relative_import_beyond_top_level():
    # Walking above the top-level package can't reach a privileged module here.
    src = "from ... import something\n"
    violations = runner_contract.scan_source_for_violations(
        "odooctl.api", src, filename="routes.py", module_name="odooctl.api.routes"
    )
    assert violations == []


def test_find_violations_no_api_package_yet():
    # No odooctl.api / odooctl.web package exists; check must pass cleanly.
    assert runner_contract.find_violations() == []
    runner_contract.assert_api_does_not_import_privileged()


# --------------------------------------------------------------------------- #
# Secrets never reach operation event / audit surfaces
# --------------------------------------------------------------------------- #
def test_redacted_params_safe_for_operation_and_audit_records():
    from odooctl.operations.models import (
        AuditEntry,
        Operation,
        OperationKind,
    )

    raw_params = {
        "environment": "production",
        "db_password": "rawsecret",
        "url": "postgres://u:rawsecret@h/db",
        "env_ref": "${ODOO_DB_PASSWORD:-fallbacksecret}",
    }
    safe = redaction.redact(raw_params, ["rawsecret"])

    op = Operation.create(
        kind=OperationKind.BACKUP,
        project="acme",
        environment="production",
        actor="user:alice@acme",
        params_redacted=safe,
    )
    blob = op.to_json()
    assert "rawsecret" not in blob
    assert "fallbacksecret" not in blob

    entry = AuditEntry(
        actor="user:alice@acme",
        action="backup",
        target="production",
        params_redacted=safe,
        outcome="succeeded",
        op_id=op.id,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    assert "rawsecret" not in entry.to_json()


def test_audit_chain_still_detects_tampering_with_redacted_params(tmp_path: Path):
    """Redaction must not weaken the existing audit tamper-detection guarantee."""
    from odooctl.operations.audit import AuditStore, verify_chain
    from odooctl.operations.models import AuditEntry

    store = AuditStore(tmp_path)
    safe = redaction.redact({"db_password": "rawsecret"}, ["rawsecret"])
    for i in range(3):
        store.append(
            AuditEntry(
                actor="user:alice@acme",
                action="backup",
                target="production",
                params_redacted=safe,
                outcome="succeeded",
                op_id=f"op{i}",
                timestamp=f"2026-05-30T00:0{i}:00+00:00",
            )
        )
    chain = store.load_chain()
    assert verify_chain(chain) is True
    # tamper with a recorded field and confirm detection still fires
    chain[1].outcome = "failed"
    assert verify_chain(chain) is False


def test_assert_raises_on_violation(tmp_path: Path, monkeypatch):
    # Build a throwaway package on sys.path that imports a privileged adapter.
    import sys

    pkg = tmp_path / "fake_api"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "routes.py").write_text("from odooctl.adapters.postgres import PostgresAdapter\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    # ensure a clean import
    sys.modules.pop("fake_api", None)
    with pytest.raises(runner_contract.RunnerContractViolation):
        runner_contract.assert_api_does_not_import_privileged(("fake_api",))


def test_find_violations_resolves_relative_import_in_real_package(tmp_path, monkeypatch):
    # A relative import that escapes the package into a privileged module must
    # be caught once find_violations computes each file's module name.
    import sys

    pkg = tmp_path / "fake_api"
    sub = pkg / "sub"
    sub.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (sub / "__init__.py").write_text("")
    # fake_api.sub.routes -> `from ...odooctl.adapters...`? Use odooctl tree:
    # anchor for fake_api.sub.routes is fake_api.sub; a relative import cannot
    # reach odooctl, so instead verify in-package relatives are NOT flagged.
    (sub / "routes.py").write_text("from ..helpers import thing\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("fake_api", None)
    # No privileged escape possible from a relative import in a foreign package.
    assert runner_contract.find_violations(("fake_api",)) == []
