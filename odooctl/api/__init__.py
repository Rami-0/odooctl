"""Optional FastAPI service for odooctl.

Requires the ``api`` optional extra: ``pip install odooctl[api]``.
The web/API layer is intentionally unprivileged — it reads state, enqueues
operations, streams events, and reads the audit trail, but never touches
Docker, Postgres, git, or the filestore directly. All privileged work runs
in the separate ``odooctl.runner`` process.
"""
