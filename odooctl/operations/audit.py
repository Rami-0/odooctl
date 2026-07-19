"""Append-only audit trail with SHA-256 hash chain.

Optional HMAC keying (F13): when the ``ODOOCTL_AUDIT_KEY`` env var is set (or
an explicit ``key`` is passed), each link is computed as
``HMAC-SHA256(key, canonical_json({**entry, "prev_hash": prev_hash}))``
instead of an unkeyed SHA-256. An attacker with file write access can
truncate-and-rehash an unkeyed chain; without the key they cannot forge valid
HMAC links. Unkeyed hashing remains the default for backward compatibility.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path

from odooctl.operations.models import AuditEntry

#: Env var holding the optional audit-chain HMAC key.
AUDIT_KEY_ENV_VAR = "ODOOCTL_AUDIT_KEY"


def _resolve_key(key: str | bytes | None) -> bytes | None:
    """Return the audit HMAC key as bytes, falling back to the environment."""
    if key is None:
        key = os.environ.get(AUDIT_KEY_ENV_VAR) or None
    if key is None:
        return None
    return key.encode("utf-8") if isinstance(key, str) else key


def _hash_entry(entry_dict: dict, prev_hash: str, key: bytes | None = None) -> str:
    payload = {**entry_dict, "prev_hash": prev_hash}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if key:
        return hmac.new(key, canon, hashlib.sha256).hexdigest()
    return hashlib.sha256(canon).hexdigest()


class AuditStore:
    def __init__(self, state_dir: Path, *, key: str | bytes | None = None) -> None:
        self.path = state_dir / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Chain-hash HMAC key; defaults to ODOOCTL_AUDIT_KEY when set, else
        # the chain remains unkeyed (plain SHA-256) for compatibility.
        self._key = _resolve_key(key)

    def append(self, entry: AuditEntry) -> AuditEntry:
        # Exclusive lock on a sidecar file guards the read-last-hash + write as one
        # atomic unit across threads and processes, preventing audit-chain forks.
        lock_path = self.path.with_suffix(".lock")
        with lock_path.open("w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            prev_hash = self._last_hash()
            entry.prev_hash = prev_hash
            entry_dict = entry.to_dict()
            entry.current_hash = _hash_entry(entry_dict, prev_hash, self._key)
            with self.path.open("a") as f:
                f.write(entry.to_json() + "\n")
        return entry

    def _last_hash(self) -> str:
        if not self.path.exists():
            return ""
        lines = [ln.strip() for ln in self.path.read_text().splitlines() if ln.strip()]
        if not lines:
            return ""
        try:
            return json.loads(lines[-1]).get("current_hash", "")
        except Exception:
            return ""

    def load_chain(self) -> list[AuditEntry]:
        if not self.path.exists():
            return []
        entries: list[AuditEntry] = []
        for line in self.path.read_text().splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    entries.append(AuditEntry.from_dict(json.loads(stripped)))
                except Exception:
                    continue
        return entries


def verify_chain(entries: list[AuditEntry], *, key: str | bytes | None = None) -> bool:
    """Return True if the hash chain is intact, False if any entry was tampered.

    When *key* is provided (or ``ODOOCTL_AUDIT_KEY`` is set), links are
    verified as HMAC-SHA256 with that key; a chain rehashed without the key
    fails verification.
    """
    resolved = _resolve_key(key)
    prev_hash = ""
    for entry in entries:
        if entry.prev_hash != prev_hash:
            return False
        expected = _hash_entry(entry.to_dict(), prev_hash, resolved)
        if entry.current_hash != expected:
            return False
        prev_hash = entry.current_hash
    return True
