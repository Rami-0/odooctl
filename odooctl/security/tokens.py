"""Capability tokens for queued runner actions.

The web/API layer cannot touch Docker/Postgres directly (see
``runner_contract``). Instead it enqueues an operation and mints a capability
token that authorizes *one* scoped action. The privileged runner verifies the
token before executing, so a leaked queue entry cannot be used against a
different action, environment, or project, and cannot outlive its expiry.

Replay within the TTL: these tokens are **replayable** while unexpired — a
captured token can be presented again for the *same* action/environment/project
until ``exp`` passes. Single-use enforcement is not provided here; it requires
the runner to record consumed ``nonce`` values (or ``jti``) and reject repeats.
The random ``nonce`` exists to make that future single-use tracking possible and
to keep otherwise-identical tokens distinct; it does not, on its own, prevent
replay. Keep TTLs short to bound the replay window.

Tokens are stdlib-only: a base64url ``header.payload.signature`` triple where
the signature is ``HMAC-SHA256`` over ``header.payload`` with the shared runner
key. This is a signed (not encrypted) token — payload fields are readable, so
no secret values are ever placed inside one.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets as _secrets
import time

_ALG = "HS256"

_RESERVED_CLAIMS = frozenset({"act", "env", "proj", "iat", "exp", "nonce", "sub"})

#: Default capability-token lifetime. Kept short (5 minutes) so a captured
#: token's replay window is small; callers may still override ``ttl_seconds``.
DEFAULT_TTL_SECONDS = 300

#: Minimum length (in characters/bytes) accepted for the shared HMAC signing
#: key (``ODOOCTL_API_KEY``). Applied at the operator-facing entry points
#: (``odooctl serve`` / ``odooctl runner`` / API app startup) via
#: :func:`enforce_key_strength`.
MIN_API_KEY_LENGTH = 32


class TokenError(Exception):
    """Base class for capability-token failures."""


class TokenInvalid(TokenError):
    """Malformed token or signature mismatch (tampering)."""


class TokenExpired(TokenError):
    """Token is past its expiry."""


class TokenScopeError(TokenError):
    """Token does not authorize the requested action/environment/project."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(key: bytes, signing_input: bytes) -> str:
    return _b64encode(hmac.new(key, signing_input, hashlib.sha256).digest())


def _coerce_key(key: str | bytes) -> bytes:
    return key.encode("utf-8") if isinstance(key, str) else key


def enforce_key_strength(key: str | bytes, *, source: str = "ODOOCTL_API_KEY") -> None:
    """Reject signing keys shorter than :data:`MIN_API_KEY_LENGTH`.

    A short HMAC key makes both bearer tokens and capability tokens brute-
    forceable offline. Entry points that accept the operator-supplied key
    (``odooctl serve``, ``odooctl runner``, ``create_app``) call this before
    minting or verifying anything.
    """
    if len(key) < MIN_API_KEY_LENGTH:
        raise ValueError(
            f"{source} is too weak: it must be at least {MIN_API_KEY_LENGTH} "
            f"characters (got {len(key)}). Generate one with e.g. "
            "`python -c 'import secrets; print(secrets.token_hex(32))'`."
        )


def mint(
    key: str | bytes,
    *,
    action: str,
    environment: str,
    project: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    subject: str | None = None,
    nonce: str | None = None,
    now: float | None = None,
    **extra_claims: object,
) -> str:
    """Mint a signed capability token scoped to one action/environment/project.

    *ttl_seconds* sets the expiry relative to *now* (defaults to current time).
    A random *nonce* is generated when not supplied so two otherwise-identical
    tokens differ. The nonce does not by itself prevent replay: the token stays
    replayable for the same scope until expiry unless the runner records and
    rejects consumed nonces. It exists to make that future single-use tracking
    possible.

    *extra_claims* are merged into the payload after the required fields, so
    callers can embed ``roles=["operator"]`` for API session tokens without
    changing the verification contract.
    """
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    reserved_overlap = _RESERVED_CLAIMS & set(extra_claims)
    if reserved_overlap:
        raise ValueError(f"extra_claims must not override reserved fields: {sorted(reserved_overlap)}")
    issued = int(now if now is not None else time.time())
    payload = {
        "act": action,
        "env": environment,
        "proj": project,
        "iat": issued,
        "exp": issued + int(ttl_seconds),
        "nonce": nonce or _secrets.token_hex(8),
    }
    if subject is not None:
        payload["sub"] = subject
    payload.update(extra_claims)
    header = {"alg": _ALG, "typ": "ocap"}
    h = _b64encode(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    p = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    sig = _sign(_coerce_key(key), signing_input)
    return f"{h}.{p}.{sig}"


def decode_unverified(token: str) -> dict:
    """Return the payload without verifying the signature (for inspection)."""
    try:
        _, p, _ = token.split(".")
        return json.loads(_b64decode(p))
    except Exception as exc:  # noqa: BLE001 - normalise all parse errors
        raise TokenInvalid("malformed token") from exc


def verify(
    key: str | bytes,
    token: str,
    *,
    action: str | None = None,
    environment: str | None = None,
    project: str | None = None,
    now: float | None = None,
) -> dict:
    """Verify *token* and return its payload, or raise a :class:`TokenError`.

    Checks, in order: structure, signature (tampering), expiry, then scope
    (action/environment/project) when those constraints are provided.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenInvalid("token must have three segments")
    h, p, sig = parts
    expected = _sign(_coerce_key(key), f"{h}.{p}".encode())
    if not hmac.compare_digest(sig, expected):
        raise TokenInvalid("signature mismatch")

    try:
        payload = json.loads(_b64decode(p))
    except Exception as exc:  # noqa: BLE001
        raise TokenInvalid("payload not decodable") from exc

    current = int(now if now is not None else time.time())
    exp = payload.get("exp")
    if not isinstance(exp, int) or current >= exp:
        raise TokenExpired("token has expired")

    if action is not None and payload.get("act") != action:
        raise TokenScopeError(f"token not valid for action '{action}'")
    if environment is not None and payload.get("env") != environment:
        raise TokenScopeError(f"token not valid for environment '{environment}'")
    if project is not None and payload.get("proj") != project:
        raise TokenScopeError(f"token not valid for project '{project}'")

    return payload
