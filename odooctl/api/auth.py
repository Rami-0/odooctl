"""Authentication and RBAC dependencies for the FastAPI service.

Tokens are verified via ``odooctl.security.tokens``; roles embedded in the
token payload drive RBAC checks via ``odooctl.security.rbac``.

Token format (from ``tokens.mint``):
  ``action="api"``, ``environment="*"``, ``project="*"``, plus
  ``roles=["viewer"]`` / ``roles=["operator"]`` in extra_claims.

No privileged imports — satisfies the runner contract.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request

from odooctl.security import rbac, tokens
from odooctl.security.principals import Principal, PrincipalKind, Role


def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1]


def get_principal(
    request: Request,
    token_str: str = Depends(_bearer_token),
) -> Principal:
    api_key: str = request.app.state.api_key
    # Key-strength floor (F24): refuse to authenticate against any weak server
    # key. ``create_app`` already rejects a weak key at startup; this is a
    # backstop for apps constructed another way, and applies regardless of how
    # the key was supplied.
    if len(api_key) < tokens.MIN_API_KEY_LENGTH:
        raise HTTPException(status_code=500, detail="Server API key is too weak")
    try:
        payload = tokens.verify(api_key, token_str, action="api")
    except tokens.TokenExpired:
        raise HTTPException(status_code=401, detail="Token expired")
    except tokens.TokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Expose the token's project scope claim so routes that are not
    # project-scoped in the path (/operations/{id}...) can enforce that the
    # operation belongs to the project the token was minted for. "*" (the
    # session-token default) means all projects.
    request.state.token_project = str(payload.get("proj") or "*")

    roles_raw = payload.get("roles", ["viewer"])
    role_set: list[Role] = []
    for r in roles_raw:
        try:
            role_set.append(Role(r))
        except ValueError:
            pass
    if not role_set:
        role_set = [Role.VIEWER]

    sub = payload.get("sub", "api-client")
    org_id = payload.get("org", "default")
    return Principal(
        id=sub,
        org_id=org_id,
        kind=PrincipalKind.TOKEN,
        roles=frozenset(role_set),
        display=sub,
    )


def enforce_project_scope(request: Request, project: str) -> None:
    """Reject access when the token's project claim does not cover *project*.

    A token minted with a concrete ``proj`` claim (not ``"*"``) is confined to
    that one project: it must not read from or enqueue against any other
    project. Session tokens use ``proj="*"`` and are unaffected. Responds 404
    (not 403) so a scoped token cannot enumerate which other projects exist.
    """
    claim = str(getattr(request.state, "token_project", None) or "")
    if claim != "*" and claim != project:
        raise HTTPException(status_code=404, detail=f"Project {project!r} not found")


def require_action(action: rbac.Action):
    """Dependency factory: verify bearer token and require *action* via RBAC."""

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        try:
            rbac.require(principal, action)
        except rbac.AccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return principal

    return _dep
