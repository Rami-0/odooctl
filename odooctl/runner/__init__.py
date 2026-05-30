"""Privileged runner — claims queued operations and executes them.

This package is intentionally privileged: it imports Docker, Postgres, and
git adapters. It must NEVER be imported by ``odooctl.api`` or ``odooctl.web``
(enforced by ``odooctl.security.runner_contract``).
"""
