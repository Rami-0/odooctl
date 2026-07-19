"""M8 review hardening tests for the importer.

These tests pin down two non-negotiable safety properties of the import
detection/preview path:

  1. Detection and preview are strictly read-only — they MUST NOT invoke any
     subprocess/shell command (which is how every Docker/DB mutation is run,
     via odooctl.utils.shell) and MUST NOT write any files.

  2. Literal DB password values are never rendered or inlined. Only env-var
     name references (or the safe fallback name) may appear in the detected
     snapshot, the generated config, and the rendered preview text — including
     literal default values inside ${VAR:-default} interpolations.

They are behavioural guards: production code is intentionally untouched.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from odooctl.importer.detect import detect_from_compose
from odooctl.importer.report import build_preview_report, render_preview_text

# A compose file whose DB passwords are LITERAL secret values, not env-var
# interpolations. The sentinel must never surface anywhere downstream.
_LITERAL_SECRET = "pl4intext-s3cret-NEVER-LEAK"

LITERAL_PASSWORD_COMPOSE = f"""\
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: prod
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: {_LITERAL_SECRET}
    volumes:
      - postgres-data:/var/lib/postgresql/data

  odoo:
    image: odoo:19.0
    environment:
      HOST: db
      USER: odoo
      PASSWORD: {_LITERAL_SECRET}
    ports:
      - "18069:8069"
    volumes:
      - odoo-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons

volumes:
  postgres-data:
  odoo-data:
"""

# A compose file whose DB password is a ${VAR:-default} interpolation. The var
# name SOME_DB_PWD is a safe reference; the default value is itself a secret
# that must never be inlined.
_DEFAULT_SECRET = "interp-default-s3cret-NEVER-LEAK"

INTERPOLATION_DEFAULT_COMPOSE = f"""\
services:
  db:
    image: postgres:17
  odoo:
    image: odoo:19.0
    environment:
      HOST: db
      USER: odoo
      PASSWORD: ${{SOME_DB_PWD:-{_DEFAULT_SECRET}}}
    ports:
      - "18069:8069"
    volumes:
      - odoo-data:/var/lib/odoo
volumes:
  odoo-data:
"""


def _write(tmp_path: Path, body: str) -> Path:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(body)
    return compose_file


# --------------------------------------------------------------------------
# Group 1: detection/preview perform no mutating subprocess/Docker/DB ops
# --------------------------------------------------------------------------

@pytest.fixture
def forbid_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any subprocess/os.system call fail loudly.

    Every Docker, DB, and shell mutation in odooctl is executed through
    odooctl.utils.shell, which calls subprocess.run/Popen. Tripping these
    proves the detection/preview path stays strictly read-only.
    """

    def _boom(name: str):
        def _raise(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            raise AssertionError(
                f"detection/preview must not invoke {name}; "
                f"called with args={args!r} kwargs={kwargs!r}"
            )

        return _raise

    monkeypatch.setattr(subprocess, "run", _boom("subprocess.run"))
    monkeypatch.setattr(subprocess, "Popen", _boom("subprocess.Popen"))
    monkeypatch.setattr(subprocess, "call", _boom("subprocess.call"))
    monkeypatch.setattr(subprocess, "check_call", _boom("subprocess.check_call"))
    monkeypatch.setattr(subprocess, "check_output", _boom("subprocess.check_output"))
    monkeypatch.setattr(os, "system", _boom("os.system"))


def test_detection_invokes_no_subprocess(tmp_path: Path, forbid_subprocess: None) -> None:
    compose_file = _write(tmp_path, LITERAL_PASSWORD_COMPOSE)

    # Would raise AssertionError if any subprocess/os.system call were made.
    detect_from_compose(compose_file)


def test_preview_invokes_no_subprocess(tmp_path: Path, forbid_subprocess: None) -> None:
    compose_file = _write(tmp_path, LITERAL_PASSWORD_COMPOSE)

    detected = detect_from_compose(compose_file)
    report = build_preview_report(detected, project_name="hardening")
    render_preview_text(report)


def test_detection_and_preview_write_no_files(tmp_path: Path) -> None:
    """Detection + preview must not create or modify any file on disk."""
    compose_file = _write(tmp_path, LITERAL_PASSWORD_COMPOSE)

    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")}

    detected = detect_from_compose(compose_file)
    report = build_preview_report(detected, project_name="hardening")
    render_preview_text(report)

    after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")}

    assert after == before  # no new files and no modifications


# --------------------------------------------------------------------------
# Group 2: literal DB password values are never rendered or inlined
# --------------------------------------------------------------------------

def test_detect_literal_password_not_stored_uses_fallback_ref(tmp_path: Path) -> None:
    compose_file = _write(tmp_path, LITERAL_PASSWORD_COMPOSE)

    detected = detect_from_compose(compose_file)

    # The literal secret must not appear in ANY field of the snapshot.
    assert _LITERAL_SECRET not in repr(asdict(detected))
    # A safe fallback env-var name is recorded instead of the literal value.
    assert detected.db_password_ref == "ODOO_DB_PASSWORD"


def test_preview_does_not_inline_literal_password(tmp_path: Path) -> None:
    compose_file = _write(tmp_path, LITERAL_PASSWORD_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="hardening")

    assert _LITERAL_SECRET not in report.generated_config
    assert _LITERAL_SECRET not in render_preview_text(report)
    # Only the env-var reference name is present in the generated config.
    assert "ODOO_DB_PASSWORD" in report.generated_config
    assert "password: " not in report.generated_config


def test_interpolation_default_secret_not_inlined(tmp_path: Path) -> None:
    """A secret hidden in ${VAR:-default} must not leak via its default value."""
    compose_file = _write(tmp_path, INTERPOLATION_DEFAULT_COMPOSE)

    detected = detect_from_compose(compose_file)
    report = build_preview_report(detected, project_name="hardening")
    preview = render_preview_text(report)

    # Only the env-var name is referenced; the default secret never appears.
    assert detected.db_password_ref == "SOME_DB_PWD"
    assert _DEFAULT_SECRET not in repr(asdict(detected))
    assert _DEFAULT_SECRET not in report.generated_config
    assert _DEFAULT_SECRET not in preview
    assert "SOME_DB_PWD" in report.generated_config


def test_generated_config_password_field_is_env_reference_only(tmp_path: Path) -> None:
    """postgres.password_env holds a name; there is no inline password key."""
    import yaml

    compose_file = _write(tmp_path, LITERAL_PASSWORD_COMPOSE)
    detected = detect_from_compose(compose_file)
    report = build_preview_report(detected, project_name="hardening")

    cfg = yaml.safe_load(report.generated_config)

    assert cfg["postgres"]["password_env"] == "ODOO_DB_PASSWORD"
    assert "password" not in cfg["postgres"]  # no literal password key at all


# --------------------------------------------------------------------------
# Group 3: --output path containment (audit finding F20)
# --------------------------------------------------------------------------

def _prepare_import_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Create a compose project dir and a separate cwd; chdir into the cwd."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    proj = tmp_path / "proj"
    proj.mkdir()
    _write(proj, LITERAL_PASSWORD_COMPOSE)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return proj, workdir


def test_import_output_outside_cwd_and_project_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typer

    from odooctl.commands import import_cmd

    proj, _workdir = _prepare_import_dirs(tmp_path, monkeypatch)
    outside = tmp_path / "elsewhere" / "hijacked.yml"
    outside.parent.mkdir()

    with pytest.raises(typer.BadParameter, match="Refusing to write"):
        import_cmd.run(
            proj, yes=True, name="escape-test", output=outside,
            skip_doctor=True, skip_backup=True,
        )
    assert not outside.exists()


def test_import_output_escape_refused_even_with_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--force must not bypass path containment; only --allow-outside may."""
    import typer

    from odooctl.commands import import_cmd

    proj, _workdir = _prepare_import_dirs(tmp_path, monkeypatch)
    victim = tmp_path / "elsewhere" / "victim.yml"
    victim.parent.mkdir()
    victim.write_text("precious")

    with pytest.raises(typer.BadParameter, match="allow-outside"):
        import_cmd.run(
            proj, yes=True, name="escape-test", output=victim, force=True,
            skip_doctor=True, skip_backup=True,
        )
    assert victim.read_text() == "precious"


def test_import_output_traversal_via_dotdot_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typer

    from odooctl.commands import import_cmd

    proj, _workdir = _prepare_import_dirs(tmp_path, monkeypatch)
    sneaky = proj / ".." / "escaped.yml"

    with pytest.raises(typer.BadParameter, match="Refusing to write"):
        import_cmd.run(
            proj, yes=True, name="escape-test", output=sneaky,
            skip_doctor=True, skip_backup=True,
        )
    assert not (tmp_path / "escaped.yml").exists()


def test_import_output_allow_outside_permits_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from odooctl.commands import import_cmd

    proj, _workdir = _prepare_import_dirs(tmp_path, monkeypatch)
    outside = tmp_path / "elsewhere" / "explicit.yml"
    outside.parent.mkdir()

    import_cmd.run(
        proj, yes=True, name="allow-test", output=outside,
        skip_doctor=True, skip_backup=True, allow_outside=True,
    )
    assert outside.exists()


def test_import_output_inside_project_dir_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writing next to the imported compose file keeps working from any cwd."""
    from odooctl.commands import import_cmd

    proj, _workdir = _prepare_import_dirs(tmp_path, monkeypatch)
    output = proj / "odooctl.yml"

    import_cmd.run(
        proj, yes=True, name="inproj-test", output=output,
        skip_doctor=True, skip_backup=True,
    )
    assert output.exists()


def test_import_output_inside_cwd_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from odooctl.commands import import_cmd

    proj, workdir = _prepare_import_dirs(tmp_path, monkeypatch)
    output = workdir / "odooctl.yml"

    import_cmd.run(
        proj, yes=True, name="incwd-test", output=output,
        skip_doctor=True, skip_backup=True,
    )
    assert output.exists()


def test_import_still_refuses_overwrite_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Overwrite protection is independent of containment: --force still required."""
    import typer

    from odooctl.commands import import_cmd

    proj, _workdir = _prepare_import_dirs(tmp_path, monkeypatch)
    output = proj / "odooctl.yml"
    output.write_text("existing")

    with pytest.raises(typer.BadParameter, match="already exists"):
        import_cmd.run(
            proj, yes=True, name="ow-test", output=output,
            skip_doctor=True, skip_backup=True,
        )
    assert output.read_text() == "existing"
