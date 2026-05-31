"""Static SPA package for the odooctl web dashboard.

The ``dist/`` subdirectory contains packaged vanilla JS/CSS/HTML assets
served by ``odooctl serve`` through the FastAPI static SPA fallback route.

No privileged imports — satisfies the runner contract.
All data access goes through the odooctl API (``/projects``, ``/operations``, etc.).
"""
