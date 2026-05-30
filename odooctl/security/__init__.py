"""Security primitives for the odooctl control plane.

This package defines the platform security model that gates the future API/UI
surfaces: organizations, users, roles, principals (``principals``), the RBAC
action matrix (``rbac``), the local secret store and rotation metadata
(``secrets``), capability tokens for queued runner actions (``tokens``),
central redaction helpers (``redaction``), and the API/web vs. privileged
runner import contract (``runner_contract``).

These are security *primitives* intended for the future API/runner surfaces
(M12+) and may also be called by service-layer code. They are not yet wired
into the existing CLI command paths, so today's CLI mutating actions are **not**
gated by these RBAC checks — enforcement at the CLI boundary is future work.

Design rules these primitives are built to support:

- Secret *values* are never represented in ``repr``/log/audit surfaces.
- ``rbac.require`` gates an action when a caller invokes it; the matrix and the
  protected/production elevation rule define the policy callers enforce.
- The web/API layer may read state and enqueue work but must never import the
  privileged Docker/Compose/Postgres adapters directly.
"""
from __future__ import annotations

from odooctl.security.principals import (
    Org,
    Principal,
    PrincipalKind,
    Role,
    User,
)
from odooctl.security.rbac import (
    AccessDenied,
    Action,
    is_allowed,
    require,
    role_matrix,
)

__all__ = [
    "Org",
    "User",
    "Role",
    "Principal",
    "PrincipalKind",
    "Action",
    "AccessDenied",
    "is_allowed",
    "require",
    "role_matrix",
]
