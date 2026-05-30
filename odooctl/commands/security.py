"""odooctl security — RBAC matrix, secret store, capability tokens, runner contract.

Secret-safety rules enforced here:

- A raw secret value is *never* accepted as a command-line argument (it would
  leak via shell history / ``ps``). Values arrive via ``--value-env`` (read
  from a named env var) or ``--stdin``.
- ``secret get`` prints only value-free metadata unless ``--reveal`` is passed.
- Signing keys for tokens are read from an env var, never from argv.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from odooctl.security import rbac, tokens
from odooctl.security.principals import Role
from odooctl.security.runner_contract import (
    API_ALLOWED_CAPABILITIES,
    RUNNER_ALLOWED_CAPABILITIES,
    find_violations,
)
from odooctl.security.secrets import SecretNotFound, open_store

app = typer.Typer(help="RBAC, secrets, capability tokens, and runner-contract checks.", add_completion=False)
secret_app = typer.Typer(help="Manage the local secret store (encrypted / env-referenced).", add_completion=False)
token_app = typer.Typer(help="Mint and verify capability tokens for runner actions.", add_completion=False)
app.add_typer(secret_app, name="secret")
app.add_typer(token_app, name="token")

console = Console()

RUNNER_KEY_ENV = "ODOOCTL_RUNNER_KEY"


def _resolve_state_dir(config: str, state_dir: Path | None) -> Path:
    if state_dir is not None:
        return state_dir
    from odooctl.services.context import ServiceContext

    return ServiceContext.from_config_path(config).project.state_dir


def _read_value(value_env: str | None, stdin: bool) -> str:
    """Read a raw secret value from an env var or stdin (never from argv)."""
    if value_env is not None:
        if value_env not in os.environ:
            typer.echo(f"Environment variable {value_env} is not set", err=True)
            raise typer.Exit(1)
        return os.environ[value_env]
    if stdin:
        return sys.stdin.readline().rstrip("\n")
    typer.echo("Provide the secret value via --value-env NAME or --stdin", err=True)
    raise typer.Exit(1)


# --------------------------------------------------------------------------- #
# RBAC matrix
# --------------------------------------------------------------------------- #
@app.command("rbac")
def show_rbac(json_output: bool = typer.Option(False, "--json", "--json-output")) -> None:
    """Display the role → action permission matrix."""
    matrix = rbac.role_matrix()
    if json_output:
        typer.echo(json.dumps(matrix, indent=2))
        return
    table = Table(title="RBAC action matrix")
    table.add_column("Action", style="bold")
    for role in Role:
        table.add_column(role.value)
    for action in rbac.Action:
        row = [action.value]
        for role in Role:
            row.append("✓" if matrix[role.value][action.value] else "·")
        table.add_row(*row)
    console.print(table)
    console.print(
        "[dim]Destructive actions on protected/production environments require "
        "admin or higher.[/dim]"
    )


# --------------------------------------------------------------------------- #
# Secrets
# --------------------------------------------------------------------------- #
@secret_app.command("put")
def secret_put(
    name: str = typer.Argument(..., help="Secret name (config references this, never the value)."),
    reference: str | None = typer.Option(None, "--reference", "-r", help="Register an env-var reference by name."),
    value_env: str | None = typer.Option(None, "--value-env", help="Read the value to encrypt-store from this env var."),
    stdin: bool = typer.Option(False, "--stdin", help="Read the value to encrypt-store from stdin."),
    rotate_days: int | None = typer.Option(None, "--rotate-days", help="Rotation interval in days (metadata)."),
    config: str = "odooctl.yml",
    state_dir: Path | None = typer.Option(None, "--state-dir", help="State directory override (advanced/testing)."),
) -> None:
    """Store an encrypted secret, or register an env-var reference."""
    store = open_store(_resolve_state_dir(config, state_dir))
    if reference is not None:
        record = store.put_reference(name, reference, rotation_interval_days=rotate_days)
    else:
        value = _read_value(value_env, stdin)
        record = store.put(name, value, rotation_interval_days=rotate_days)
    typer.echo(f"Stored secret '{record.name}' (source={record.source}).")


@secret_app.command("get")
def secret_get(
    name: str = typer.Argument(...),
    reveal: bool = typer.Option(False, "--reveal", help="Print the raw secret value (use with care)."),
    config: str = "odooctl.yml",
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    """Show secret metadata; only print the value with explicit --reveal."""
    store = open_store(_resolve_state_dir(config, state_dir))
    try:
        record = store.metadata(name)
    except SecretNotFound:
        typer.echo(f"No secret named '{name}'", err=True)
        raise typer.Exit(1)
    if not reveal:
        typer.echo(json.dumps(record.to_public_dict(), indent=2))
        return
    try:
        value = store.get(name)
    except SecretNotFound as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    # The single place a raw secret value is ever emitted, behind --reveal.
    typer.echo(value.reveal())


@secret_app.command("list")
def secret_list(
    json_output: bool = typer.Option(False, "--json", "--json-output"),
    config: str = "odooctl.yml",
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    """List stored/referenced secrets (metadata only — never values)."""
    store = open_store(_resolve_state_dir(config, state_dir))
    records = store.list_metadata()
    if json_output:
        typer.echo(json.dumps([r.to_public_dict() for r in records], indent=2))
        return
    table = Table(title="Secrets")
    table.add_column("Name", style="bold")
    table.add_column("Source")
    table.add_column("Version")
    table.add_column("Rotated")
    table.add_column("Interval (days)")
    table.add_column("Due")
    for r in records:
        table.add_row(
            r.name,
            r.source if r.source == "stored" else f"env:{r.env_var}",
            str(r.version),
            r.rotated_at or "-",
            str(r.rotation_interval_days) if r.rotation_interval_days else "-",
            "yes" if r.is_due_for_rotation() else "no",
        )
    console.print(table)


@secret_app.command("rotate")
def secret_rotate(
    name: str = typer.Argument(...),
    value_env: str | None = typer.Option(None, "--value-env", help="New value for a stored secret (from env var)."),
    stdin: bool = typer.Option(False, "--stdin", help="Read the new value from stdin."),
    config: str = "odooctl.yml",
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    """Rotate a secret: re-encrypt a stored value or stamp an env reference."""
    store = open_store(_resolve_state_dir(config, state_dir))
    try:
        record = store.metadata(name)
    except SecretNotFound:
        typer.echo(f"No secret named '{name}'", err=True)
        raise typer.Exit(1)
    new_value = None
    if record.source == "stored":
        new_value = _read_value(value_env, stdin)
    try:
        record = store.rotate(name, new_value)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"Rotated '{record.name}' to version {record.version}.")


# --------------------------------------------------------------------------- #
# Capability tokens
# --------------------------------------------------------------------------- #
def _runner_key(key_env: str) -> bytes:
    if key_env not in os.environ:
        typer.echo(f"Signing key env var {key_env} is not set", err=True)
        raise typer.Exit(1)
    raw = os.environ[key_env]
    if raw == "":
        typer.echo(f"Signing key env var {key_env} is empty", err=True)
        raise typer.Exit(1)
    return raw.encode("utf-8")


@token_app.command("mint")
def token_mint(
    action: str = typer.Option(..., "--action", help="Scoped action, e.g. backup/deploy/clone."),
    environment: str = typer.Option(..., "--env", "--environment", help="Target environment."),
    project: str = typer.Option(..., "--project", help="Target project."),
    ttl: int = typer.Option(300, "--ttl", help="Time-to-live in seconds."),
    subject: str | None = typer.Option(None, "--subject", help="Optional subject (principal identity)."),
    key_env: str = typer.Option(RUNNER_KEY_ENV, "--key-env", help="Env var holding the runner signing key."),
    role: list[str] = typer.Option([], "--role", help="Role to embed in the token (repeatable, e.g. --role operator)."),
) -> None:
    """Mint a signed capability token for a single scoped runner action."""
    key = _runner_key(key_env)
    extra: dict = {"roles": role} if role else {}
    token = tokens.mint(
        key,
        action=action,
        environment=environment,
        project=project,
        ttl_seconds=ttl,
        subject=subject,
        **extra,
    )
    typer.echo(token)


@token_app.command("verify")
def token_verify(
    token: str | None = typer.Argument(None, help="Capability token to verify (or use --stdin)."),
    action: str | None = typer.Option(None, "--action"),
    environment: str | None = typer.Option(None, "--env", "--environment"),
    project: str | None = typer.Option(None, "--project"),
    key_env: str = typer.Option(RUNNER_KEY_ENV, "--key-env"),
    stdin: bool = typer.Option(False, "--stdin", help="Read the token from stdin instead of argv."),
) -> None:
    """Verify a capability token's signature, expiry, and scope.

    The token may be passed as a positional argument or, to keep it out of
    shell history and ``ps``, read from stdin with ``--stdin``.
    """
    if stdin:
        token = sys.stdin.readline().strip()
    if not token:
        typer.echo("Provide a token as an argument or via --stdin", err=True)
        raise typer.Exit(1)
    key = _runner_key(key_env)
    try:
        payload = tokens.verify(
            key, token, action=action, environment=environment, project=project
        )
    except tokens.TokenError as exc:
        typer.echo(f"INVALID: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


# --------------------------------------------------------------------------- #
# Runner contract
# --------------------------------------------------------------------------- #
@app.command("runner-check")
def runner_check() -> None:
    """Verify the API/web layer does not import privileged adapters directly."""
    violations = find_violations()
    if violations:
        typer.echo("Runner contract VIOLATED:", err=True)
        for v in violations:
            typer.echo(f"  - {v}", err=True)
        raise typer.Exit(1)
    typer.echo("Runner contract OK: no API/web package imports privileged adapters.")
    typer.echo("API/web may: " + ", ".join(API_ALLOWED_CAPABILITIES))
    typer.echo("Runner may: " + ", ".join(RUNNER_ALLOWED_CAPABILITIES))
