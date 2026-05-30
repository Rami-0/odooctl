"""Tests for the M10 onboarding catalog: schema, registry, render, CLI, setup integration."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from odooctl.catalog.schema import (
    AddonPack,
    AddonSource,
    CompanionService,
    StackTemplate,
)
from odooctl.catalog.registry import get_entry, get_stack_templates, list_entries, load_manifest
from odooctl.catalog.render import render_stack_template
from odooctl.commands.catalog import app as catalog_app
from odooctl.commands.setup import KNOWN_STACKS, run as setup_run, scaffold_project

runner = CliRunner()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestStackTemplateSchema:
    def test_valid_stack_template(self) -> None:
        st = StackTemplate(
            id="odoo-19-community",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        assert st.kind == "StackTemplate"
        assert st.id == "odoo-19-community"

    def test_defaults(self) -> None:
        st = StackTemplate(
            id="test",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        assert st.http_port == 8069
        assert st.volumes == []
        assert st.description == ""

    def test_addon_source_schema(self) -> None:
        src = AddonSource(
            id="oca-web",
            repo_url="https://github.com/OCA/web",
            ref="18.0",
        )
        assert src.kind == "AddonSource"
        assert src.auth_env is None
        assert src.subpath is None

    def test_addon_source_with_auth_env(self) -> None:
        src = AddonSource(
            id="private-addon",
            repo_url="https://github.com/myorg/addons",
            ref="main",
            auth_env="GITHUB_TOKEN",
        )
        assert src.auth_env == "GITHUB_TOKEN"

    def test_addon_pack_schema(self) -> None:
        pack = AddonPack(id="oca-essentials", sources=["oca-web", "oca-server-tools"])
        assert pack.kind == "AddonPack"
        assert len(pack.sources) == 2

    def test_companion_service_schema(self) -> None:
        svc = CompanionService(
            id="pgadmin",
            service_name="pgadmin",
            image="dpage/pgadmin4:8.6",
        )
        assert svc.kind == "CompanionService"
        assert svc.ports == []
        assert svc.environment == {}
        assert svc.volumes == []


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_bundled_entries_load(self) -> None:
        entries = list_entries()
        assert len(entries) > 0

    def test_bundled_has_odoo19(self) -> None:
        entry = get_entry("odoo-19-community")
        assert isinstance(entry, StackTemplate)
        assert entry.odoo_version == "19.0"

    def test_bundled_has_odoo18(self) -> None:
        entry = get_entry("odoo-18-community")
        assert isinstance(entry, StackTemplate)
        assert entry.odoo_version == "18.0"

    def test_bundled_has_companions(self) -> None:
        pgadmin = get_entry("pgadmin")
        assert isinstance(pgadmin, CompanionService)

    def test_bundled_has_addon_sources(self) -> None:
        src = get_entry("oca-web")
        assert isinstance(src, AddonSource)

    def test_get_entry_returns_none_for_unknown(self) -> None:
        assert get_entry("nonexistent-id-xyz") is None

    def test_get_stack_templates_keys(self) -> None:
        stacks = get_stack_templates()
        assert "odoo-19-community" in stacks
        assert "odoo-18-community" in stacks
        assert all(isinstance(v, StackTemplate) for v in stacks.values())

    def test_bundled_stacks_no_floating_latest(self) -> None:
        for entry in list_entries():
            if isinstance(entry, StackTemplate):
                assert entry.odoo_image != "odoo:latest", f"{entry.id} uses floating odoo:latest"
                assert ":latest" not in entry.postgres_image, f"{entry.id} uses floating postgres:latest"
            if isinstance(entry, CompanionService):
                assert ":latest" not in entry.image, f"{entry.id} uses floating :latest"

    def test_load_manifest_single_dict(self, tmp_path: Path) -> None:
        manifest = tmp_path / "test.yaml"
        manifest.write_text(yaml.dump({
            "kind": "StackTemplate",
            "id": "test-stack",
            "odoo_version": "19.0",
            "odoo_image": "odoo:19.0",
            "postgres_image": "postgres:16-alpine",
        }))
        entries = load_manifest(manifest)
        assert len(entries) == 1
        assert entries[0].id == "test-stack"

    def test_load_manifest_list(self, tmp_path: Path) -> None:
        manifest = tmp_path / "test.yaml"
        manifest.write_text(yaml.dump([
            {"kind": "AddonSource", "id": "src-a", "repo_url": "https://example.com/a", "ref": "main"},
            {"kind": "AddonSource", "id": "src-b", "repo_url": "https://example.com/b", "ref": "18.0"},
        ]))
        entries = load_manifest(manifest)
        assert len(entries) == 2
        assert entries[0].id == "src-a"
        assert entries[1].id == "src-b"

    def test_load_manifest_unknown_kind_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "bad.yaml"
        manifest.write_text("kind: UnknownThing\nid: x\n")
        with pytest.raises(Exception):
            load_manifest(manifest)

    def test_extra_entries_extend_list(self) -> None:
        extra = [AddonSource(id="extra-src", repo_url="https://example.com", ref="main")]
        entries = list_entries(extra=extra)
        assert any(e.id == "extra-src" for e in entries)

    def test_get_entry_finds_extra(self) -> None:
        extra = [AddonSource(id="extra-only", repo_url="https://example.com", ref="main")]
        entry = get_entry("extra-only", extra=extra)
        assert entry is not None
        assert entry.id == "extra-only"

    def test_get_entry_does_not_return_extra_without_extra_arg(self) -> None:
        # "extra-only-2" is not in the bundled catalog; calling without extra returns None.
        assert get_entry("extra-only-2") is None


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

class TestRender:
    def test_render_project_section(self) -> None:
        st = StackTemplate(
            id="odoo-19-community",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        cfg = render_stack_template(st, "my-project")
        assert cfg["project"]["name"] == "my-project"
        assert cfg["project"]["odoo_version"] == "19.0"

    def test_render_uses_template_image(self) -> None:
        st = StackTemplate(
            id="odoo-18-community",
            odoo_version="18.0",
            odoo_image="odoo:18.0",
            postgres_image="postgres:15-alpine",
        )
        cfg = render_stack_template(st, "acme")
        assert cfg["odoo"]["image"] == "odoo:18.0"

    def test_render_postgres_section_has_password_env(self) -> None:
        st = StackTemplate(
            id="test",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        cfg = render_stack_template(st, "proj")
        assert "postgres" in cfg
        assert "password_env" in cfg["postgres"]

    def test_render_secrets_not_inline(self) -> None:
        st = StackTemplate(
            id="test",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        cfg = render_stack_template(st, "proj")
        rendered = yaml.dump(cfg)
        assert "password_env" in rendered
        assert "password: " not in rendered

    def test_render_has_production_environment(self) -> None:
        st = StackTemplate(
            id="test",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        cfg = render_stack_template(st, "proj")
        assert "environments" in cfg
        assert "production" in cfg["environments"]

    def test_render_db_name_uses_project_name(self) -> None:
        st = StackTemplate(
            id="test",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        cfg = render_stack_template(st, "acme-corp")
        assert cfg["environments"]["production"]["db_name"] == "acme-corp_prod"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCatalogCLI:
    def test_catalog_list_exits_zero(self) -> None:
        result = runner.invoke(catalog_app, ["list"])
        assert result.exit_code == 0

    def test_catalog_list_shows_odoo19(self) -> None:
        result = runner.invoke(catalog_app, ["list"])
        assert "odoo-19-community" in result.output

    def test_catalog_list_shows_odoo18(self) -> None:
        result = runner.invoke(catalog_app, ["list"])
        assert "odoo-18-community" in result.output

    def test_catalog_show_odoo19(self) -> None:
        result = runner.invoke(catalog_app, ["show", "odoo-19-community"])
        assert result.exit_code == 0
        assert "19.0" in result.output

    def test_catalog_show_odoo18(self) -> None:
        result = runner.invoke(catalog_app, ["show", "odoo-18-community"])
        assert result.exit_code == 0
        assert "18.0" in result.output

    def test_catalog_show_unknown_exits_nonzero(self) -> None:
        result = runner.invoke(catalog_app, ["show", "nonexistent-xyz"])
        assert result.exit_code != 0

    def test_catalog_add_valid_manifest(self, tmp_path: Path) -> None:
        manifest = tmp_path / "user.yaml"
        manifest.write_text(yaml.dump({
            "kind": "StackTemplate",
            "id": "my-custom-stack",
            "odoo_version": "19.0",
            "odoo_image": "myregistry/odoo:19.0-custom",
            "postgres_image": "postgres:16-alpine",
        }))
        result = runner.invoke(catalog_app, ["add", str(manifest)])
        assert result.exit_code == 0
        assert "my-custom-stack" in result.output

    def test_catalog_add_multi_entry_manifest(self, tmp_path: Path) -> None:
        manifest = tmp_path / "multi.yaml"
        manifest.write_text(yaml.dump([
            {"kind": "AddonSource", "id": "my-src-a", "repo_url": "https://example.com/a", "ref": "main"},
            {"kind": "AddonSource", "id": "my-src-b", "repo_url": "https://example.com/b", "ref": "18.0"},
        ]))
        result = runner.invoke(catalog_app, ["add", str(manifest)])
        assert result.exit_code == 0
        assert "my-src-a" in result.output
        assert "my-src-b" in result.output

    def test_catalog_add_invalid_kind_reports_error(self, tmp_path: Path) -> None:
        manifest = tmp_path / "bad.yaml"
        manifest.write_text("kind: UnknownKind\nid: x\n")
        result = runner.invoke(catalog_app, ["add", str(manifest)])
        assert result.exit_code != 0

    def test_catalog_add_missing_file_reports_error(self, tmp_path: Path) -> None:
        result = runner.invoke(catalog_app, ["add", str(tmp_path / "nope.yaml")])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Setup wizard integration
# ---------------------------------------------------------------------------

class TestSetupCatalogIntegration:
    def test_known_stacks_has_odoo19(self) -> None:
        assert "odoo-19-community" in KNOWN_STACKS

    def test_known_stacks_has_odoo18(self) -> None:
        assert "odoo-18-community" in KNOWN_STACKS

    def test_known_stacks_has_legacy_odoo17(self) -> None:
        assert "odoo-17-community" in KNOWN_STACKS

    def test_scaffold_odoo18_from_catalog(self, tmp_path: Path) -> None:
        output = tmp_path / "odooctl.yml"
        scaffold_project(project_name="test-proj", stack="odoo-18-community", output_path=output)
        cfg = yaml.safe_load(output.read_text())
        assert cfg["project"]["odoo_version"] == "18.0"
        assert "18.0" in cfg["odoo"]["image"]

    def test_scaffold_odoo19_uses_catalog_image(self, tmp_path: Path) -> None:
        output = tmp_path / "odooctl.yml"
        scaffold_project(project_name="test-proj", stack="odoo-19-community", output_path=output)
        cfg = yaml.safe_load(output.read_text())
        assert cfg["odoo"]["image"] != "odoo:latest"

    def test_scaffold_catalog_stack_has_password_env(self, tmp_path: Path) -> None:
        output = tmp_path / "odooctl.yml"
        scaffold_project(project_name="test-proj", stack="odoo-18-community", output_path=output)
        cfg = yaml.safe_load(output.read_text())
        assert "password_env" in cfg["postgres"]
        assert "password: " not in output.read_text()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_stack_template_rejects_latest_odoo_image(self) -> None:
        with pytest.raises(Exception):
            StackTemplate(
                id="test",
                odoo_version="19.0",
                odoo_image="odoo:latest",
                postgres_image="postgres:16-alpine",
            )

    def test_stack_template_rejects_latest_postgres_image(self) -> None:
        with pytest.raises(Exception):
            StackTemplate(
                id="test",
                odoo_version="19.0",
                odoo_image="odoo:19.0",
                postgres_image="postgres:latest",
            )

    def test_companion_service_rejects_latest_image(self) -> None:
        with pytest.raises(Exception):
            CompanionService(id="test", service_name="test", image="myimage:latest")

    def test_stack_template_accepts_pinned_images(self) -> None:
        st = StackTemplate(
            id="test",
            odoo_version="19.0",
            odoo_image="odoo:19.0",
            postgres_image="postgres:16-alpine",
        )
        assert st.odoo_image == "odoo:19.0"

    def test_companion_service_accepts_pinned_image(self) -> None:
        svc = CompanionService(id="test", service_name="test", image="redis:7.2-alpine")
        assert svc.image == "redis:7.2-alpine"

    def test_addon_source_auth_env_accepts_uppercase_name(self) -> None:
        src = AddonSource(
            id="x", repo_url="https://example.com", ref="main", auth_env="GITHUB_TOKEN"
        )
        assert src.auth_env == "GITHUB_TOKEN"

    def test_addon_source_auth_env_accepts_none(self) -> None:
        src = AddonSource(id="x", repo_url="https://example.com", ref="main", auth_env=None)
        assert src.auth_env is None

    def test_addon_source_auth_env_rejects_dollar_reference(self) -> None:
        with pytest.raises(Exception):
            AddonSource(
                id="x",
                repo_url="https://example.com",
                ref="main",
                auth_env="${GITHUB_TOKEN}",
            )

    def test_addon_source_auth_env_rejects_value_with_spaces(self) -> None:
        with pytest.raises(Exception):
            AddonSource(
                id="x",
                repo_url="https://example.com",
                ref="main",
                auth_env="my token value",
            )


# ---------------------------------------------------------------------------
# Setup wizard — user manifest via --catalog
# ---------------------------------------------------------------------------

class TestSetupUserCatalog:
    def test_scaffold_with_extra_catalog_uses_custom_stack(self, tmp_path: Path) -> None:
        manifest = tmp_path / "user.yaml"
        manifest.write_text(yaml.dump({
            "kind": "StackTemplate",
            "id": "custom-19",
            "odoo_version": "19.0",
            "odoo_image": "myregistry/odoo:19.0-custom",
            "postgres_image": "postgres:16-alpine",
        }))
        extra = load_manifest(manifest)
        output = tmp_path / "odooctl.yml"
        scaffold_project(
            project_name="test-proj",
            stack="custom-19",
            output_path=output,
            extra_catalog=extra,
        )
        cfg = yaml.safe_load(output.read_text())
        assert cfg["odoo"]["image"] == "myregistry/odoo:19.0-custom"
        assert cfg["project"]["odoo_version"] == "19.0"

    def test_scaffold_extra_catalog_has_password_env(self, tmp_path: Path) -> None:
        manifest = tmp_path / "user.yaml"
        manifest.write_text(yaml.dump({
            "kind": "StackTemplate",
            "id": "custom-18",
            "odoo_version": "18.0",
            "odoo_image": "myregistry/odoo:18.0-internal",
            "postgres_image": "postgres:15-alpine",
        }))
        extra = load_manifest(manifest)
        output = tmp_path / "odooctl.yml"
        scaffold_project(
            project_name="acme",
            stack="custom-18",
            output_path=output,
            extra_catalog=extra,
        )
        cfg = yaml.safe_load(output.read_text())
        assert "password_env" in cfg["postgres"]

    def test_scaffold_extra_catalog_does_not_affect_global_known_stacks(
        self, tmp_path: Path
    ) -> None:
        manifest = tmp_path / "user.yaml"
        manifest.write_text(yaml.dump({
            "kind": "StackTemplate",
            "id": "ephemeral-stack",
            "odoo_version": "19.0",
            "odoo_image": "myregistry/odoo:19.0-tmp",
            "postgres_image": "postgres:16-alpine",
        }))
        extra = load_manifest(manifest)
        # ephemeral-stack is in extra but not in the global KNOWN_STACKS
        assert "ephemeral-stack" not in KNOWN_STACKS
        output = tmp_path / "odooctl.yml"
        scaffold_project(
            project_name="proj",
            stack="ephemeral-stack",
            output_path=output,
            extra_catalog=extra,
        )
        cfg = yaml.safe_load(output.read_text())
        assert "myregistry/odoo:19.0-tmp" in cfg["odoo"]["image"]

    def test_run_with_catalog_path_uses_custom_stack(self, tmp_path: Path) -> None:
        manifest = tmp_path / "user.yaml"
        manifest.write_text(yaml.dump({
            "kind": "StackTemplate",
            "id": "enterprise-19",
            "odoo_version": "19.0",
            "odoo_image": "registry.example.com/odoo:19.0-enterprise",
            "postgres_image": "postgres:16-alpine",
        }))
        output = tmp_path / "odooctl.yml"
        setup_run(yes=True, stack="enterprise-19", name="ent-proj", output=output, catalog=manifest)
        cfg = yaml.safe_load(output.read_text())
        assert "registry.example.com/odoo:19.0-enterprise" in cfg["odoo"]["image"]

    def test_run_with_invalid_catalog_raises(self, tmp_path: Path) -> None:
        bad_manifest = tmp_path / "bad.yaml"
        bad_manifest.write_text("kind: UnknownKind\nid: x\n")
        output = tmp_path / "odooctl.yml"
        import typer
        with pytest.raises(typer.BadParameter):
            setup_run(yes=True, stack="odoo-19-community", name="test", output=output, catalog=bad_manifest)

    def test_run_without_catalog_preserves_existing_behavior(self, tmp_path: Path) -> None:
        output = tmp_path / "odooctl.yml"
        setup_run(yes=True, stack="odoo-19-community", name="legacy-proj", output=output)
        cfg = yaml.safe_load(output.read_text())
        assert cfg["project"]["odoo_version"] == "19.0"


# ---------------------------------------------------------------------------
# Root CLI — catalog subcommand registration
# ---------------------------------------------------------------------------

class TestRootCLICatalog:
    def test_root_app_catalog_list_exits_zero(self) -> None:
        from odooctl.main import app as main_app
        result = runner.invoke(main_app, ["catalog", "list"])
        assert result.exit_code == 0

    def test_root_app_catalog_list_shows_stacks(self) -> None:
        from odooctl.main import app as main_app
        result = runner.invoke(main_app, ["catalog", "list"])
        assert "odoo-19-community" in result.output
        assert "odoo-18-community" in result.output

    def test_root_app_catalog_show_entry(self) -> None:
        from odooctl.main import app as main_app
        result = runner.invoke(main_app, ["catalog", "show", "odoo-19-community"])
        assert result.exit_code == 0
        assert "19.0" in result.output
