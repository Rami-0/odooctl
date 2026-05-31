"""Module readiness scan for Odoo version upgrades."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# Modules that frequently require manual review during upgrades.
_REVIEW_RECOMMENDED: frozenset[str] = frozenset(
    {
        "website_sale",
        "payment",
        "l10n_mx_edi",
        "pos_restaurant",
        "pos_config_generalised",
    }
)

# Well-known Odoo core and OCA module name prefixes.
_KNOWN_PREFIXES: tuple[str, ...] = (
    "account",
    "analytic",
    "base",
    "bus",
    "calendar",
    "contacts",
    "crm",
    "delivery",
    "digest",
    "document",
    "email_",
    "fleet",
    "helpdesk",
    "hr_",
    "im_livechat",
    "l10n_",
    "lunch",
    "mail",
    "mrp",
    "note",
    "payment",
    "point_of_sale",
    "pos_",
    "product",
    "project",
    "purchase",
    "rating",
    "repair",
    "resource",
    "sale",
    "sign",
    "sms",
    "snailmail",
    "social_",
    "stock",
    "survey",
    "timesheet",
    "uom",
    "utm",
    "web",
    "website",
    "portal",
    "phone_",
    "mass_mailing",
    "queue_job",
    "sale_management",
)


@dataclass
class ScanResult:
    from_version: str
    to_version: str
    installed_modules: list[str]
    blockers: list[str]
    warnings: list[str]


def scan_modules(
    *,
    from_version: str,
    to_version: str,
    module_list_fn: Callable[[], list[str]],
    review_recommended: frozenset[str] | None = None,
) -> ScanResult:
    """Scan installed modules for upgrade readiness.

    :param from_version: Source Odoo version (e.g. ``"17.0"``).
    :param to_version: Target Odoo version (e.g. ``"18.0"``).
    :param module_list_fn: Injectable callable returning installed module names.
    :param review_recommended: Override set of modules that always need review.
    """
    if review_recommended is None:
        review_recommended = _REVIEW_RECOMMENDED

    installed = sorted(module_list_fn())
    blockers: list[str] = []
    warnings: list[str] = []

    # Warn about modules known to need manual attention.
    for mod in installed:
        if mod in review_recommended:
            warnings.append(
                f"Module '{mod}' requires manual review before upgrading "
                f"{from_version} → {to_version}"
            )

    # Warn about likely custom/third-party modules.
    for mod in installed:
        is_known = any(mod == p.rstrip("_") or mod.startswith(p) for p in _KNOWN_PREFIXES)
        if not is_known:
            warnings.append(
                f"Custom/third-party module '{mod}' — verify an OpenUpgrade "
                "migration script exists for this module"
            )

    # Block multi-version jumps (e.g. 16.0 → 18.0 must go via 17.0).
    try:
        from_major = int(from_version.split(".")[0])
        to_major = int(to_version.split(".")[0])
        if to_major - from_major > 1:
            blockers.append(
                f"Upgrade spans {to_major - from_major} major versions "
                f"({from_version} → {to_version}); perform sequential hops "
                f"({from_major}.0 → {from_major + 1}.0 → … → {to_major}.0)"
            )
    except (ValueError, IndexError):
        pass

    return ScanResult(
        from_version=from_version,
        to_version=to_version,
        installed_modules=installed,
        blockers=blockers,
        warnings=warnings,
    )
