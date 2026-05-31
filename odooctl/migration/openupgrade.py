"""Optional pinned OpenUpgrade integration metadata.

OpenUpgrade (https://github.com/OCA/OpenUpgrade) is the OCA community upgrade
framework for Odoo.  It is OPTIONAL — odooctl also supports the standard
``odoo --update all --stop-after-init`` upgrade path without it.

When the ``--openupgrade`` flag is used, the pinned branch for the target
version is selected.  Never reference a floating ``main`` or ``master`` branch.
"""
from __future__ import annotations

from dataclasses import dataclass

OPENUPGRADE_REPO: str = "https://github.com/OCA/OpenUpgrade"

# Pinned branch per target Odoo version.
# Extend this table when new Odoo releases gain OpenUpgrade support.
PINNED_BRANCHES: dict[str, str] = {
    "14.0": "14.0",
    "15.0": "15.0",
    "16.0": "16.0",
    "17.0": "17.0",
    "18.0": "18.0",
    "19.0": "19.0",
}


@dataclass
class OpenUpgradeMeta:
    repo: str
    branch: str
    addons_path: str
    upgrade_command: list[str]
    notes: str


def get_openupgrade_meta(to_version: str) -> OpenUpgradeMeta | None:
    """Return pinned OpenUpgrade metadata for *to_version*, or ``None`` if unsupported."""
    branch = PINNED_BRANCHES.get(to_version)
    if branch is None:
        return None
    return OpenUpgradeMeta(
        repo=OPENUPGRADE_REPO,
        branch=branch,
        addons_path="/opt/odoo/openupgrade",
        upgrade_command=[
            "python",
            "/opt/odoo/openupgrade/odoo-bin",
            "--upgrade-path=/opt/odoo/openupgrade/openupgrade_scripts/scripts",
            "--update=all",
            "--stop-after-init",
        ],
        notes=(
            f"Clone {OPENUPGRADE_REPO} at branch {branch!r} into the container "
            "before running the upgrade.  See the OpenUpgrade README for "
            "addons_path and upgrade_path setup."
        ),
    )


def openupgrade_db_command(db_name: str, to_version: str) -> list[str] | None:
    """Return the full upgrade command list for *db_name* / *to_version*, or ``None``."""
    meta = get_openupgrade_meta(to_version)
    if meta is None:
        return None
    return meta.upgrade_command + ["--database", db_name]
