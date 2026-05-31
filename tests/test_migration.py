"""M15 Migration and Upgrade Assistant tests."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_DIST = Path(__file__).parent.parent / "odooctl" / "web" / "dist"


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------


def test_load_matrix_returns_paths():
    from odooctl.migration.matrix import load_matrix

    paths = load_matrix()
    assert len(paths) > 0


def test_matrix_path_fields():
    from odooctl.migration.matrix import load_matrix

    for p in load_matrix():
        assert p.from_version
        assert p.to_version
        assert isinstance(p.requires_openupgrade, bool)
        assert isinstance(p.notes, str)


def test_matrix_adjacent_versions_only():
    """All listed paths are adjacent major-version upgrades (N → N+1)."""
    from odooctl.migration.matrix import load_matrix

    for p in load_matrix():
        from_major = int(p.from_version.split(".")[0])
        to_major = int(p.to_version.split(".")[0])
        assert to_major - from_major == 1, (
            f"Non-adjacent path: {p.from_version} → {p.to_version}"
        )


def test_supported_paths_filter_from():
    from odooctl.migration.matrix import supported_paths

    result = supported_paths(from_version="17.0")
    assert all(p.from_version == "17.0" for p in result)
    assert len(result) >= 1


def test_supported_paths_filter_to():
    from odooctl.migration.matrix import supported_paths

    result = supported_paths(to_version="18.0")
    assert all(p.to_version == "18.0" for p in result)
    assert len(result) >= 1


def test_supported_paths_no_match():
    from odooctl.migration.matrix import supported_paths

    result = supported_paths(from_version="12.0", to_version="19.0")
    assert result == []


def test_format_matrix_contains_header():
    from odooctl.migration.matrix import format_matrix

    output = format_matrix()
    assert "From" in output
    assert "To" in output
    assert "OpenUpgrade" in output


def test_format_matrix_contains_versions():
    from odooctl.migration.matrix import format_matrix

    output = format_matrix()
    assert "17.0" in output
    assert "18.0" in output


def test_format_matrix_empty():
    from odooctl.migration.matrix import format_matrix

    output = format_matrix(paths=[])
    assert "no paths defined" in output


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def test_scan_result_fields():
    from odooctl.migration.scan import scan_modules

    result = scan_modules(
        from_version="17.0",
        to_version="18.0",
        module_list_fn=lambda: ["base", "mail", "sale"],
    )
    assert result.from_version == "17.0"
    assert result.to_version == "18.0"
    assert "base" in result.installed_modules
    assert "mail" in result.installed_modules
    assert isinstance(result.blockers, list)
    assert isinstance(result.warnings, list)


def test_scan_modules_sorted():
    from odooctl.migration.scan import scan_modules

    result = scan_modules(
        from_version="17.0",
        to_version="18.0",
        module_list_fn=lambda: ["sale", "base", "mail"],
    )
    assert result.installed_modules == sorted(result.installed_modules)


def test_scan_no_blockers_adjacent_versions():
    from odooctl.migration.scan import scan_modules

    result = scan_modules(
        from_version="17.0",
        to_version="18.0",
        module_list_fn=lambda: ["base", "mail"],
    )
    assert result.blockers == []


def test_scan_blocker_multi_version_jump():
    from odooctl.migration.scan import scan_modules

    result = scan_modules(
        from_version="16.0",
        to_version="18.0",
        module_list_fn=lambda: ["base"],
    )
    assert len(result.blockers) == 1
    assert "sequential hops" in result.blockers[0]


def test_scan_warns_custom_module():
    from odooctl.migration.scan import scan_modules

    result = scan_modules(
        from_version="17.0",
        to_version="18.0",
        module_list_fn=lambda: ["my_custom_addon"],
    )
    custom_warnings = [w for w in result.warnings if "my_custom_addon" in w]
    assert len(custom_warnings) >= 1
    assert "OpenUpgrade" in custom_warnings[0]


def test_scan_known_module_no_custom_warning():
    """A well-known base module should not trigger the custom-module warning."""
    from odooctl.migration.scan import scan_modules

    result = scan_modules(
        from_version="17.0",
        to_version="18.0",
        module_list_fn=lambda: ["base"],
    )
    custom_warnings = [w for w in result.warnings if "Custom" in w and "base" in w]
    assert custom_warnings == []


def test_scan_review_recommended_warning(monkeypatch):
    from odooctl.migration.scan import scan_modules

    result = scan_modules(
        from_version="17.0",
        to_version="18.0",
        module_list_fn=lambda: ["website_sale"],
        review_recommended=frozenset({"website_sale"}),
    )
    review_warnings = [w for w in result.warnings if "website_sale" in w and "manual review" in w]
    assert len(review_warnings) >= 1


# ---------------------------------------------------------------------------
# OpenUpgrade
# ---------------------------------------------------------------------------


def test_openupgrade_meta_known_version():
    from odooctl.migration.openupgrade import get_openupgrade_meta

    meta = get_openupgrade_meta("18.0")
    assert meta is not None
    assert meta.branch == "18.0"
    assert "OCA/OpenUpgrade" in meta.repo
    assert meta.upgrade_command
    assert meta.addons_path


def test_openupgrade_meta_unknown_version():
    from odooctl.migration.openupgrade import get_openupgrade_meta

    assert get_openupgrade_meta("13.0") is None
    assert get_openupgrade_meta("20.0") is None


def test_openupgrade_branch_pinned():
    """Each supported version must use its own pinned branch, not a floating ref."""
    from odooctl.migration.openupgrade import get_openupgrade_meta, PINNED_BRANCHES

    for version, expected_branch in PINNED_BRANCHES.items():
        meta = get_openupgrade_meta(version)
        assert meta is not None
        assert meta.branch == expected_branch, (
            f"Version {version}: expected branch {expected_branch!r}, got {meta.branch!r}"
        )


def test_openupgrade_db_command_includes_db_name():
    from odooctl.migration.openupgrade import openupgrade_db_command

    cmd = openupgrade_db_command("my_throwaway_db", "18.0")
    assert cmd is not None
    assert "my_throwaway_db" in cmd


def test_openupgrade_db_command_unknown_version():
    from odooctl.migration.openupgrade import openupgrade_db_command

    assert openupgrade_db_command("any_db", "13.0") is None


# ---------------------------------------------------------------------------
# Rehearsal — safety contract
# ---------------------------------------------------------------------------


def test_rehearsal_raises_if_throwaway_matches_source():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    with pytest.raises(RuntimeError, match="must differ"):
        rehearse_upgrade(
            source_env="production",
            source_version="17.0",
            target_version="18.0",
            source_db="prod_db",
            db_adapter=MagicMock(),
            healthcheck_fn=lambda url: True,
            upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
            throwaway_suffix="",  # empty → throwaway == source
        )


def test_rehearsal_dumps_from_source_not_throwaway(tmp_path):
    """dump() must target source_db; restore() must target throwaway_db only."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True, installed_after=["base"]),
        throwaway_suffix="_mig_rehearsal",
    )

    # dump must be called on the SOURCE db
    mock_db.dump.assert_called_once()
    assert mock_db.dump.call_args[0][0] == "prod_db"

    # restore must be called on the THROWAWAY db, never the source
    mock_db.restore.assert_called_once()
    throwaway_db_used = mock_db.restore.call_args[0][0]
    assert throwaway_db_used == "prod_db_mig_rehearsal"
    assert throwaway_db_used != "prod_db"


def test_rehearsal_upgrade_fn_receives_throwaway_db():
    """upgrade_fn must receive the throwaway DB name, never the source DB name."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    called_with: list[str] = []

    def _track_upgrade(db: str, ver: str) -> UpgradeResult:
        called_with.append(db)
        return UpgradeResult(ok=True)

    rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        upgrade_fn=_track_upgrade,
        throwaway_suffix="_mig_rehearsal",
    )

    assert len(called_with) == 1
    assert called_with[0] == "prod_db_mig_rehearsal"
    assert called_with[0] != "prod_db"


def test_rehearsal_drops_throwaway_on_success():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
    )

    mock_db.drop.assert_called_once()
    assert mock_db.drop.call_args[0][0] == "prod_db_mig_rehearsal"


def test_rehearsal_drops_throwaway_on_upgrade_failure():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=False, warnings=["oops"]),
    )

    assert result.status == "failed"
    mock_db.drop.assert_called_once()
    assert mock_db.drop.call_args[0][0] == "prod_db_mig_rehearsal"


def test_rehearsal_drops_throwaway_on_healthcheck_failure():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: False,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
    )

    assert result.status == "failed"
    assert result.healthcheck_status == "failed"
    mock_db.drop.assert_called_once()


def test_rehearsal_drops_throwaway_on_exception():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    mock_db.dump.side_effect = RuntimeError("dump failed")
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
    )

    assert result.status == "failed"
    assert "dump failed" in (result.message or "")
    mock_db.drop.assert_called_once()


def test_rehearsal_keep_skips_drop():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
        keep=True,
    )

    mock_db.drop.assert_not_called()
    assert result.cleanup_status == "kept"


def test_rehearsal_never_drops_source_db():
    """Cleanup must only target the throwaway DB, never the source."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
    )

    dropped = [c[0][0] for c in mock_db.drop.call_args_list]
    assert "prod_db" not in dropped


# ---------------------------------------------------------------------------
# Rehearsal — report
# ---------------------------------------------------------------------------


def test_rehearsal_report_fields_success():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    result = rehearse_upgrade(
        source_env="staging",
        source_version="17.0",
        target_version="18.0",
        source_db="staging_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(
            ok=True,
            installed_after=["base", "mail"],
            failed_modules=[],
            warnings=[],
        ),
    )

    assert result.status == "success"
    assert result.source_env == "staging"
    assert result.source_version == "17.0"
    assert result.target_version == "18.0"
    assert result.installed_modules == ["base", "mail"]
    assert result.failed_modules == []
    assert result.healthcheck_status == "passed"
    assert result.cleanup_status == "cleaned"
    assert result.duration_seconds >= 0
    assert result.next_actions


def test_rehearsal_report_saved_on_failure(tmp_path):
    """Failed rehearsal must still persist the report to disk."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    report_dir = tmp_path / "reports"
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(
            ok=False, warnings=["module X failed"]
        ),
        report_dir=report_dir,
    )

    assert result.status == "failed"
    assert report_dir.exists()
    report_files = list(report_dir.glob("*.json"))
    assert len(report_files) == 1
    data = json.loads(report_files[0].read_text())
    assert data["status"] == "failed"
    assert data["source_env"] == "production"
    assert data["target_version"] == "18.0"


def test_rehearsal_report_saved_on_success(tmp_path):
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    report_dir = tmp_path / "reports"
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True, installed_after=["base"]),
        report_dir=report_dir,
    )

    assert result.status == "success"
    report_files = list(report_dir.glob("*.json"))
    assert len(report_files) == 1


def test_rehearsal_report_contains_all_required_fields(tmp_path):
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    report_dir = tmp_path / "reports"
    rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True, installed_after=["base"]),
        report_dir=report_dir,
    )

    data = json.loads(next(report_dir.glob("*.json")).read_text())
    required = {
        "status",
        "source_env",
        "source_version",
        "target_version",
        "installed_modules",
        "failed_modules",
        "warnings",
        "duration_seconds",
        "healthcheck_status",
        "log_path",
        "cleanup_status",
        "next_actions",
    }
    assert required.issubset(data.keys())


def test_rehearsal_failed_report_has_next_actions():
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(
            ok=False, failed_modules=["my_module"]
        ),
    )

    assert result.status == "failed"
    assert len(result.next_actions) >= 1
    any_mentions_module = any("my_module" in a for a in result.next_actions)
    assert any_mentions_module


def test_rehearsal_cleanup_failed_status():
    """If drop() raises, cleanup_status is 'cleanup_failed' (not a crash)."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    mock_db.drop.side_effect = RuntimeError("cannot drop")
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda url: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
    )

    assert result.cleanup_status == "cleanup_failed"


# ---------------------------------------------------------------------------
# Rehearsal — healthcheck targets throwaway DB, not source env URL
# ---------------------------------------------------------------------------


def test_rehearsal_healthcheck_fn_receives_throwaway_db():
    """healthcheck_fn must be called with the throwaway DB name, not the source env public URL."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    called_with: list[str] = []

    def _track_healthcheck(db_name: str) -> bool:
        called_with.append(db_name)
        return True

    rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=_track_healthcheck,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
        throwaway_suffix="_mig_rehearsal",
    )

    assert len(called_with) == 1
    assert called_with[0] == "prod_db_mig_rehearsal"
    assert called_with[0] != "prod_db"
    # Must not be a URL — the source env's public URL must never be the target
    assert not called_with[0].startswith("http")


def test_rehearsal_healthcheck_fn_not_called_when_upgrade_fails():
    """healthcheck_fn must not be called when the upgrade itself fails."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    called_with: list[str] = []

    rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda db: called_with.append(db) or True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=False, warnings=["failed"]),
    )

    assert called_with == [], "healthcheck_fn must not be called when upgrade_fn returns ok=False"


# ---------------------------------------------------------------------------
# Rehearsal — requires_openupgrade enforcement
# ---------------------------------------------------------------------------


def test_rehearsal_fails_when_requires_openupgrade_without_flag():
    """Rehearsal must fail immediately and clearly when path requires OpenUpgrade but flag not set."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    mock_db = MagicMock()
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=mock_db,
        healthcheck_fn=lambda db: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
        requires_openupgrade=True,
        use_openupgrade=False,
    )

    assert result.status == "failed"
    assert "openupgrade" in (result.message or "").lower()
    # No DB operations must have occurred — the early exit must fire before any clone
    mock_db.dump.assert_not_called()
    mock_db.restore.assert_not_called()
    mock_db.drop.assert_not_called()


def test_rehearsal_fails_openupgrade_required_has_next_action():
    """Failed report for missing --openupgrade must include a corrective next action."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    result = rehearse_upgrade(
        source_env="staging",
        source_version="17.0",
        target_version="18.0",
        source_db="staging_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda db: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
        requires_openupgrade=True,
        use_openupgrade=False,
    )

    assert result.status == "failed"
    assert any("openupgrade" in a.lower() for a in result.next_actions)


def test_rehearsal_fails_openupgrade_required_saved_to_report_dir(tmp_path):
    """Even the early-exit report must be written to report_dir when provided."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    report_dir = tmp_path / "reports"
    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda db: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
        requires_openupgrade=True,
        use_openupgrade=False,
        report_dir=report_dir,
    )

    assert result.status == "failed"
    report_files = list(report_dir.glob("*.json"))
    assert len(report_files) == 1
    import json
    data = json.loads(report_files[0].read_text())
    assert data["status"] == "failed"
    assert "openupgrade" in (data.get("message") or "").lower()


def test_rehearsal_proceeds_when_requires_openupgrade_and_flag_set():
    """Rehearsal must proceed normally when requires_openupgrade=True and use_openupgrade=True."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    result = rehearse_upgrade(
        source_env="production",
        source_version="17.0",
        target_version="18.0",
        source_db="prod_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda db: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
        requires_openupgrade=True,
        use_openupgrade=True,
    )

    assert result.status == "success"


def test_rehearsal_proceeds_when_not_requires_openupgrade_and_no_flag():
    """Rehearsal must proceed when requires_openupgrade=False regardless of use_openupgrade."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult

    result = rehearse_upgrade(
        source_env="staging",
        source_version="17.0",
        target_version="18.0",
        source_db="staging_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda db: True,
        upgrade_fn=lambda db, ver: UpgradeResult(ok=True),
        requires_openupgrade=False,
        use_openupgrade=False,
    )

    assert result.status == "success"


def test_runner_healthcheck_fn_targets_throwaway_db_not_source_url():
    """Runner's _healthcheck_fn must call db_adapter.ping with the throwaway DB name, not a URL."""
    import inspect
    from odooctl.runner import worker

    src = inspect.getsource(worker)
    # Find the _healthcheck_fn definition inside the MIGRATE_REHEARSAL dispatch
    migrate_section = src.split("OperationKind.MIGRATE_REHEARSAL")[1] if "MIGRATE_REHEARSAL" in src else ""
    # Must not build an hc_url using env_cfg.domain for rehearsal healthcheck
    assert "env_cfg.domain" not in migrate_section.split("elif kind")[0] or "hc_url" not in migrate_section.split("elif kind")[0], (
        "Runner migrate_rehearsal dispatch must not construct a source-env URL for healthcheck"
    )
    # Must use db_adapter.ping not check_url
    assert "db_adapter.ping" in migrate_section


def test_cli_healthcheck_fn_targets_throwaway_db_not_source_url():
    """CLI _healthcheck_fn must call db_adapter.ping, not check_url against source env URL."""
    import inspect
    import odooctl.commands.migrate as migrate_mod

    src = inspect.getsource(migrate_mod)
    # Must use db_adapter.ping
    assert "db_adapter.ping" in src
    # Must not use check_url inside _healthcheck_fn (check_url is for HTTP; rehearsal needs DB ping)
    # The only acceptable use of check_url is outside the rehearsal healthcheck
    rehearse_section = src.split("def rehearse")[1] if "def rehearse" in src else src
    assert "check_url" not in rehearse_section, (
        "CLI rehearse command must not use check_url (HTTP) for rehearsal healthcheck; use db_adapter.ping"
    )


# ---------------------------------------------------------------------------
# OperationKind integration
# ---------------------------------------------------------------------------


def test_migrate_rehearsal_operation_kind():
    from odooctl.operations.models import OperationKind

    assert OperationKind.MIGRATE_REHEARSAL.value == "migrate_rehearsal"


def test_api_routes_map_migrate_rehearsal():
    """API routes must include migrate_rehearsal in the kind→action map."""
    from odooctl.api.routes_operations import _KIND_ACTION

    assert "migrate_rehearsal" in _KIND_ACTION


def test_runner_maps_migrate_rehearsal():
    """Runner worker must include migrate_rehearsal in its RBAC action map."""
    from odooctl.runner.worker import _KIND_ACTION

    assert "migrate_rehearsal" in _KIND_ACTION


def test_runner_passes_keep_param_to_rehearsal():
    """Runner must preserve the UI/API keep flag so operators can inspect throwaway DBs."""
    import inspect
    from odooctl.runner import worker

    src = inspect.getsource(worker)
    migrate_section = src.split("OperationKind.MIGRATE_REHEARSAL")[1]
    assert 'params.get("keep", False)' in migrate_section
    assert "keep=keep_throwaway" in migrate_section


# ---------------------------------------------------------------------------
# SPA — migration rehearsal affordance
# ---------------------------------------------------------------------------


def test_app_js_has_migrate_rehearsal_operation_kind():
    """SPA must enqueue the migrate_rehearsal operation kind."""
    content = _DIST.joinpath("app.js").read_text()
    assert "migrate_rehearsal" in content


def test_app_js_has_migrate_target_version_control():
    """SPA must include a target version input for migration rehearsal."""
    content = _DIST.joinpath("app.js").read_text()
    assert "migrate-to" in content


def test_app_js_has_openupgrade_control():
    """SPA must include an openupgrade toggle for migration rehearsal."""
    content = _DIST.joinpath("app.js").read_text()
    assert "openupgrade" in content.lower()


def test_app_js_has_migrate_keep_control():
    """SPA must include a keep-throwaway-db control for migration rehearsal."""
    content = _DIST.joinpath("app.js").read_text()
    assert "migrate-keep" in content


def test_app_js_has_rehearse_confirmation_keyword():
    """SPA must use 'rehearse' as the typed confirmation keyword."""
    content = _DIST.joinpath("app.js").read_text()
    assert "rehearse" in content


def test_app_js_has_migrate_tab():
    """SPA must render a Migrate tab in the environment detail view."""
    content = _DIST.joinpath("app.js").read_text()
    assert "migrate" in content and "tab" in content


# ---------------------------------------------------------------------------
# OpenUpgrade safety — unsupported version must not run empty command
# ---------------------------------------------------------------------------


def test_openupgrade_unsupported_version_rehearsal_fails_with_message():
    """When upgrade_fn raises ValueError for unsupported OpenUpgrade version, rehearsal fails clearly."""
    from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult
    from odooctl.migration.openupgrade import openupgrade_db_command

    def _upgrade_fn_with_none_check(throwaway_db: str, tgt_ver: str) -> UpgradeResult:
        cmd = openupgrade_db_command(throwaway_db, tgt_ver)
        if cmd is None:
            raise ValueError(
                f"OpenUpgrade does not support target version {tgt_ver!r}"
            )
        return UpgradeResult(ok=True)

    result = rehearse_upgrade(
        source_env="staging",
        source_version="12.0",
        target_version="13.0",
        source_db="staging_db",
        db_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        upgrade_fn=_upgrade_fn_with_none_check,
    )

    assert result.status == "failed"
    assert "13.0" in (result.message or "")


def test_runner_openupgrade_none_not_substituted_with_empty_list():
    """Runner must not use 'or []' to substitute None openupgrade command — must raise ValueError."""
    import inspect
    from odooctl.runner import worker

    src = inspect.getsource(worker)
    parts = src.split("openupgrade_db_command")
    for i, part in enumerate(parts[1:], 1):
        first_line = part.split("\n")[0]
        assert "or []" not in first_line, (
            f"Runner silently substitutes [] for None openupgrade command (occurrence {i}). "
            "Must raise ValueError instead."
        )


def test_cli_openupgrade_none_not_substituted_with_empty_list():
    """CLI _upgrade_fn must not use 'or []' to substitute None openupgrade command."""
    import inspect
    import odooctl.commands.migrate as migrate_mod

    src = inspect.getsource(migrate_mod)
    parts = src.split("openupgrade_db_command")
    for i, part in enumerate(parts[1:], 1):
        first_line = part.split("\n")[0]
        assert "or []" not in first_line, (
            f"CLI silently substitutes [] for None openupgrade command (occurrence {i}). "
            "Must raise ValueError instead."
        )


# ---------------------------------------------------------------------------
# Unsupported path rejection — matrix guard in CLI and runner
# ---------------------------------------------------------------------------


def test_cli_rehearse_rejects_unsupported_path():
    """CLI rehearse must reject paths absent from supported_paths before any DB work."""
    import inspect
    import odooctl.commands.migrate as migrate_mod

    src = inspect.getsource(migrate_mod)
    rehearse_fn_src = src.split("def rehearse")[1].split("\ndef ")[0]

    assert "not matrix_paths" in rehearse_fn_src, (
        "CLI rehearse must guard 'if not matrix_paths' to reject unsupported paths"
    )
    assert "BadParameter" in rehearse_fn_src, (
        "CLI rehearse must raise typer.BadParameter for unsupported paths"
    )


def test_runner_dispatch_rejects_unsupported_path():
    """Runner dispatch must raise ValueError for version pairs absent from supported_paths."""
    import inspect
    from odooctl.runner import worker

    src = inspect.getsource(worker)
    migrate_section = src.split("OperationKind.MIGRATE_REHEARSAL")[1].split("elif kind")[0]

    assert "not matrix_paths" in migrate_section, (
        "Runner dispatch must guard 'if not matrix_paths' to reject unsupported paths"
    )
    assert "ValueError" in migrate_section, (
        "Runner dispatch must raise ValueError for unsupported paths"
    )


def test_cli_rehearse_guard_precedes_rehearse_upgrade_call():
    """The unsupported-path guard must appear before the rehearse_upgrade() call in CLI source."""
    import inspect
    import odooctl.commands.migrate as migrate_mod

    src = inspect.getsource(migrate_mod)
    rehearse_fn_src = src.split("def rehearse")[1].split("\ndef ")[0]

    guard_pos = rehearse_fn_src.find("not matrix_paths")
    call_pos = rehearse_fn_src.find("rehearse_upgrade(")
    assert guard_pos != -1, "Guard 'not matrix_paths' not found in CLI rehearse"
    assert call_pos != -1, "rehearse_upgrade() call not found in CLI rehearse"
    assert guard_pos < call_pos, (
        "CLI unsupported-path guard must appear before rehearse_upgrade() call"
    )


def test_runner_dispatch_guard_precedes_rehearse_upgrade_call():
    """The unsupported-path guard must appear before the rehearse_upgrade() call in runner source."""
    import inspect
    from odooctl.runner import worker

    src = inspect.getsource(worker)
    migrate_section = src.split("OperationKind.MIGRATE_REHEARSAL")[1].split("elif kind")[0]

    guard_pos = migrate_section.find("not matrix_paths")
    call_pos = migrate_section.find("rehearse_upgrade(")
    assert guard_pos != -1, "Guard 'not matrix_paths' not found in runner dispatch"
    assert call_pos != -1, "rehearse_upgrade() call not found in runner dispatch"
    assert guard_pos < call_pos, (
        "Runner unsupported-path guard must appear before rehearse_upgrade() call"
    )
