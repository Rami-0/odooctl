"""API/web vs. privileged runner import contract.

The security boundary (see ``docs/plans/m11-security-architecture.md``): the
web/API process never mounts the Docker socket and never runs Docker, Postgres,
git, or tar work. It may only read state, enqueue operations, stream events,
and read the audit trail. All privileged work happens in the runner.

This module encodes that split structurally and provides a static check that
will catch a *future* API/web package importing a privileged adapter directly.
There is no API package yet, so the check tolerates missing packages and is
designed to fail loudly the moment one is added with a forbidden import.

Both absolute imports (``import odooctl.adapters.postgres`` /
``from odooctl.adapters.postgres import ...``) and *relative* imports
(``from ..adapters.postgres import ...`` inside ``odooctl.api.routes``) are
resolved to absolute module names before checking, so a relative escape into a
privileged package is caught too.

Out of scope (static analysis cannot see these): dynamic imports via
``importlib.import_module`` / ``__import__`` with computed names. The contract
is a structural guardrail, not a sandbox; runtime privilege separation (the
runner process boundary) remains the real enforcement.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from importlib import util as import_util
from pathlib import Path

# Modules only the privileged runner may import. Importing any of these from an
# API/web package violates the contract.
PRIVILEGED_MODULE_PREFIXES: tuple[str, ...] = (
    "odooctl.adapters",          # docker_compose, postgres, db, filestore, s3, reverse_proxy
    "odooctl.odoo",              # db_swap, module_update, sanitize, healthcheck
)

# Packages that represent the unprivileged API/web surface (may not exist yet).
API_PACKAGES: tuple[str, ...] = (
    "odooctl.api",
    "odooctl.web",
)

# What the API/web layer is permitted to do, documented for the runner contract.
API_ALLOWED_CAPABILITIES: tuple[str, ...] = (
    "read state",
    "enqueue operations",
    "stream events",
    "read audit (per RBAC)",
)

RUNNER_ALLOWED_CAPABILITIES: tuple[str, ...] = (
    "access Docker/Compose",
    "run Postgres commands",
    "manage filestore archives",
    "run git operations",
)


class RunnerContractViolation(Exception):
    """Raised when an API/web package imports a privileged module directly."""


@dataclass(frozen=True)
class ImportViolation:
    package: str
    module: str         # the imported privileged module
    source_file: str
    lineno: int

    def __str__(self) -> str:
        return f"{self.package}: {self.source_file}:{self.lineno} imports privileged '{self.module}'"


def _is_privileged(module: str) -> bool:
    return any(module == p or module.startswith(p + ".") for p in PRIVILEGED_MODULE_PREFIXES)


def _resolve_relative(module: str | None, level: int, anchor_package: str) -> str | None:
    """Resolve a relative ``ImportFrom`` (``level > 0``) to an absolute module.

    *anchor_package* is the ``__package__`` the importing module belongs to
    (e.g. ``odooctl.api`` for the module ``odooctl.api.routes``). Mirrors
    CPython's relative-import resolution. Returns ``None`` when the import walks
    beyond the top-level package — such an import would fail at runtime and
    cannot resolve to a privileged module inside our tree, so it is tolerated.
    """
    if not anchor_package:
        return None
    bits = anchor_package.rsplit(".", level - 1)
    if len(bits) < level:
        return None  # beyond top-level package
    base = bits[0]
    return f"{base}.{module}" if module else base


def _anchor_package(package_name: str, module_name: str | None, filename: str) -> str:
    """Return the package that relative imports in this source resolve against.

    A package's ``__init__`` source anchors on the package itself; any other
    module anchors on its parent package. With no module context we fall back to
    treating the source as *package_name*'s own ``__init__``.
    """
    if module_name is None:
        return package_name
    if Path(filename).name == "__init__.py":
        return module_name
    return module_name.rsplit(".", 1)[0] if "." in module_name else ""


def _imported_modules(tree: ast.AST, anchor_package: str) -> list[tuple[str, int]]:
    """Return (module, lineno) pairs for every import statement in *tree*.

    Relative ``from`` imports are resolved to absolute names against
    *anchor_package*; unresolvable ones are dropped.
    """
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    found.append((node.module, node.lineno))
            else:
                resolved = _resolve_relative(node.module, node.level, anchor_package)
                if resolved:
                    found.append((resolved, node.lineno))
    return found


def scan_source_for_violations(
    package_name: str,
    source: str,
    *,
    filename: str = "<source>",
    module_name: str | None = None,
) -> list[ImportViolation]:
    """Scan a single source string for privileged imports (used by tests).

    *package_name* is the API/web package being scanned (used in the report and
    as the relative-import anchor when *module_name* is not given). Pass
    *module_name* (the importing module's fully-qualified name, e.g.
    ``odooctl.api.routes``) to resolve relative imports precisely.
    """
    tree = ast.parse(source, filename=filename)
    anchor = _anchor_package(package_name, module_name, filename)
    return [
        ImportViolation(package=package_name, module=module, source_file=filename, lineno=lineno)
        for module, lineno in _imported_modules(tree, anchor)
        if _is_privileged(module)
    ]


def _package_dir(package_name: str) -> Path | None:
    try:
        spec = import_util.find_spec(package_name)
    except (ModuleNotFoundError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(next(iter(spec.submodule_search_locations)))


def find_violations(packages: tuple[str, ...] = API_PACKAGES) -> list[ImportViolation]:
    """Statically scan each API/web *package* for privileged imports.

    Missing packages are skipped (the API package may not exist yet). Returns a
    flat list of violations across all scanned packages.
    """
    violations: list[ImportViolation] = []
    for package_name in packages:
        pkg_dir = _package_dir(package_name)
        if pkg_dir is None:
            continue
        for py_file in sorted(pkg_dir.rglob("*.py")):
            try:
                source = py_file.read_text()
            except OSError:
                continue
            parts = list(py_file.relative_to(pkg_dir).with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            module_name = ".".join([package_name, *parts]) if parts else package_name
            violations.extend(
                scan_source_for_violations(
                    package_name, source, filename=str(py_file), module_name=module_name
                )
            )
    return violations


def assert_api_does_not_import_privileged(packages: tuple[str, ...] = API_PACKAGES) -> None:
    """Raise :class:`RunnerContractViolation` if any API/web package is dirty."""
    violations = find_violations(packages)
    if violations:
        detail = "\n".join(f"  - {v}" for v in violations)
        raise RunnerContractViolation(
            "API/web packages must not import privileged adapters directly:\n" + detail
        )
