from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib

import click

from odooctl.context import ProjectContext


@dataclass(frozen=True)
class RegisteredProject:
    name: str
    path: Path
    config: str = "odooctl.yml"


@dataclass(frozen=True)
class Registry:
    path: Path
    active: str | None
    projects: dict[str, RegisteredProject]


def default_registry_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / "odooctl" / "config.toml"
    return Path.home() / ".config" / "odooctl" / "config.toml"


def load_registry(path: str | Path | None = None) -> Registry:
    registry_path = Path(path).expanduser() if path is not None else default_registry_path()
    if not registry_path.exists():
        return Registry(path=registry_path, active=None, projects={})

    data = tomllib.loads(registry_path.read_text())
    raw_projects = data.get("projects", {}) or {}
    projects: dict[str, RegisteredProject] = {}
    for name, raw in raw_projects.items():
        if not isinstance(raw, dict) or "path" not in raw:
            continue
        projects[name] = RegisteredProject(
            name=name,
            path=Path(str(raw["path"])).expanduser(),
            config=str(raw.get("config", "odooctl.yml")),
        )
    active = data.get("active")
    if active is not None:
        active = str(active)
    return Registry(path=registry_path, active=active, projects=projects)


def save_registry(registry: Registry) -> None:
    registry.path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if registry.active:
        lines.append(f'active = "{_toml_escape(registry.active)}"')
        lines.append("")
    if registry.projects:
        lines.append("[projects]")
        for name in sorted(registry.projects):
            project = registry.projects[name]
            lines.append(
                f'"{_toml_escape(name)}" = {{ path = "{_toml_escape(str(project.path))}", '
                f'config = "{_toml_escape(project.config)}" }}'
            )
    registry.path.write_text("\n".join(lines).rstrip() + "\n")


def add_project(name: str, path: str | Path, config: str = "odooctl.yml", *, make_active: bool = True) -> RegisteredProject:
    registry = load_registry()
    root = Path(path).expanduser().resolve()
    config_path = Path(config).expanduser()
    resolved_config = config_path if config_path.is_absolute() else root / config_path
    if not resolved_config.exists():
        raise click.ClickException(f"Config file not found for project {name!r}: {resolved_config}")
    project = RegisteredProject(name=name, path=root, config=str(config))
    projects = dict(registry.projects)
    projects[name] = project
    active = name if make_active or registry.active is None else registry.active
    save_registry(Registry(path=registry.path, active=active, projects=projects))
    return project


def remove_project(name: str) -> None:
    registry = load_registry()
    if name not in registry.projects:
        raise click.ClickException(f"Unknown project: {name}")
    projects = dict(registry.projects)
    projects.pop(name)
    active = registry.active
    if active == name:
        active = next(iter(sorted(projects)), None)
    save_registry(Registry(path=registry.path, active=active, projects=projects))


def use_project(name: str) -> RegisteredProject:
    registry = load_registry()
    project = registry.projects.get(name)
    if project is None:
        raise click.ClickException(f"Unknown project: {name}")
    save_registry(Registry(path=registry.path, active=name, projects=registry.projects))
    return project


def resolve_project_context(
    *,
    project: str | None = None,
    project_dir: str | Path | None = None,
    config: str | Path = "odooctl.yml",
) -> ProjectContext:
    """Resolve project context with precedence: -p > -C > cwd/config."""

    if project:
        registry = load_registry()
        registered = registry.projects.get(project)
        if registered is None:
            raise click.ClickException(f"Unknown project: {project}")
        return ProjectContext.from_config_path(registered.config, root=registered.path)
    if project_dir is not None:
        return ProjectContext.from_config_path(config, root=project_dir)
    return ProjectContext.from_config_path(config)


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
