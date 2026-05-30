"""Central redaction helpers.

These helpers scrub secret material out of arbitrary strings and mappings
before they reach logs, operation events, audit records, or CLI output. Two
classes of secret are handled:

1. Known literal secret *values* (e.g. a resolved DB password) — replaced with
   a placeholder wherever they appear as substrings.
2. Env-ref interpolations of the form ``${VAR:-default}`` — the default may be
   a real secret, so it is dropped and only the ``${VAR}`` reference is kept.

The functions never raise on unexpected shapes; they recurse through dicts,
lists, and tuples and leave non-string scalars untouched.
"""
from __future__ import annotations

import re
from typing import Any

PLACEHOLDER = "***"

# ${VAR:-default} / ${VAR:default} / ${VAR-default} — capture VAR, drop default.
_ENV_DEFAULT_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-|:)[^}]*\}")

# Keys whose values are treated as secret when redacting mappings.
_SECRET_KEY_TOKENS = ("password", "secret", "token", "key", "passwd", "pass")


def strip_env_defaults(text: str) -> str:
    """Collapse ``${VAR:-default}`` to ``${VAR}`` so secret defaults never leak.

    A bare ``${VAR}`` (no default) is left unchanged.
    """
    return _ENV_DEFAULT_RE.sub(lambda m: "${" + m.group(1) + "}", str(text))


def _is_secret_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    low = key.lower()
    return any(tok in low for tok in _SECRET_KEY_TOKENS)


def redact_text(text: str, secret_values: object = (), *, placeholder: str = PLACEHOLDER) -> str:
    """Redact *text*: drop env-ref defaults, then mask any known secret values.

    *secret_values* is any iterable of literal secret strings to mask. Longer
    values are masked first so a value that contains another is fully covered.
    """
    out = strip_env_defaults(str(text))
    values = sorted(
        {str(v) for v in secret_values if v is not None and str(v) != ""},
        key=len,
        reverse=True,
    )
    for value in values:
        if value:
            out = out.replace(value, placeholder)
    return out


def redact(value: Any, secret_values: object = (), *, placeholder: str = PLACEHOLDER) -> Any:
    """Recursively redact *value* (str / mapping / list / tuple).

    Mapping entries whose key looks secret are masked **regardless of the value
    type** — a numeric, boolean, or nested-mapping value under a ``*password*``
    key is replaced with the placeholder, not passed through. The one exception
    is a string that, after stripping env-ref defaults, is a bare ``${VAR}``
    reference: that carries no secret material and is preserved. All other
    string values additionally have env-ref defaults stripped and known secret
    literals masked.
    """
    if isinstance(value, str):
        return redact_text(value, secret_values, placeholder=placeholder)
    if isinstance(value, dict):
        result: dict = {}
        for k, v in value.items():
            if _is_secret_key(k):
                # Preserve a bare env reference (default stripped); mask anything
                # else under a secret-looking key, whatever its type.
                if isinstance(v, str):
                    stripped = strip_env_defaults(v)
                    result[k] = stripped if stripped.startswith("${") and stripped.endswith("}") else placeholder
                else:
                    result[k] = placeholder
            else:
                result[k] = redact(v, secret_values, placeholder=placeholder)
        return result
    if isinstance(value, (list, tuple)):
        redacted = [redact(item, secret_values, placeholder=placeholder) for item in value]
        return type(value)(redacted)
    return value
