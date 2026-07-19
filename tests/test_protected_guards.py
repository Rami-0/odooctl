"""Audit finding C4/F2: protection policy must be config-driven.

Every policy guard must go through ``OdooCtlConfig.is_protected`` (or an
``is_protected_fn`` derived from it) instead of comparing environment names
against the literal string "production". This test scans the package so any
reintroduced literal comparison fails CI.
"""
from __future__ import annotations

import re
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "odooctl"

# Definitional sites, not policy guards: these define what "production" means.
EXCLUDED_FILES = {
    PACKAGE_ROOT / "config.py",
    PACKAGE_ROOT / "services" / "branch.py",
}

# Matches comparisons in either direction: x == "production", 'production' != x
LITERAL_COMPARISON = re.compile(
    r"""[=!]=\s*(?:"production"|'production')|(?:"production"|'production')\s*[=!]="""
)


def test_no_literal_production_comparisons_remain():
    assert PACKAGE_ROOT.is_dir(), f"package root not found: {PACKAGE_ROOT}"
    offenders: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        if path in EXCLUDED_FILES:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if LITERAL_COMPARISON.search(line):
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, (
        "Literal production-name comparisons found; use cfg.is_protected(name) "
        "(or pass is_protected_fn) instead:\n" + "\n".join(offenders)
    )
