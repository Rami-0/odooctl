"""Local secret store with env-var references, encryption, and rotation metadata.

Design constraints:

- Stdlib only. Confidentiality uses an HMAC-SHA256 keystream (counter mode) and
  integrity uses encrypt-then-MAC with a separate HMAC-SHA256 key, so no
  third-party ``cryptography`` dependency is required for single-host v1.
- Secret *values* never appear in ``repr``, ``str``, logs, events, or audit.
  Values are wrapped in :class:`SecretValue`, which hides itself, and the only
  way to obtain the raw string is the explicit ``.reveal()`` call.
- Two secret sources are supported: an encrypted local store and an env-var
  *reference* (only the variable name is persisted; the value lives in the
  process environment).
- Rotation metadata (version, rotated_at, interval) is tracked per secret.

Note: this module is named ``secrets`` but Python 3 absolute imports mean
``import secrets`` below resolves to the stdlib module, not this one.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets as _stdlib_secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

STORE_VERSION = 1
KEY_ENV_VAR = "ODOOCTL_SECRET_KEY"


# --------------------------------------------------------------------------- #
# Value wrapper — never reveals itself except via .reveal()
# --------------------------------------------------------------------------- #
class SecretValue:
    """A revealed secret value that refuses to expose itself implicitly.

    ``repr``/``str`` return a constant mask, so logging or interpolating a
    SecretValue cannot leak the underlying string. Call ``.reveal()`` to obtain
    the raw value at the exact point it is needed.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(***)"

    def __str__(self) -> str:
        return "***"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecretValue):
            return hmac.compare_digest(self._value, other._value)
        return NotImplemented

    def __hash__(self) -> int:  # pragma: no cover - rarely used
        return hash(("SecretValue",))


class SecretNotFound(KeyError):
    """Raised when a secret name is not present in the store."""


class SecretDecryptionError(Exception):
    """Raised when stored ciphertext fails authentication (wrong key/tamper)."""


# --------------------------------------------------------------------------- #
# Stdlib authenticated encryption (encrypt-then-MAC, HMAC-SHA256 keystream)
# --------------------------------------------------------------------------- #
def _derive_subkeys(key: bytes) -> tuple[bytes, bytes]:
    enc = hashlib.sha256(b"odooctl-enc\x00" + key).digest()
    mac = hashlib.sha256(b"odooctl-mac\x00" + key).digest()
    return enc, mac


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def encrypt(key: bytes, plaintext: str) -> dict[str, str]:
    """Return a JSON-serialisable ciphertext envelope for *plaintext*."""
    raw = plaintext.encode("utf-8")
    nonce = _stdlib_secrets.token_bytes(16)
    enc_key, mac_key = _derive_subkeys(key)
    ks = _keystream(enc_key, nonce, len(raw))
    ct = bytes(a ^ b for a, b in zip(raw, ks))
    mac = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    return {
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
        "mac": base64.b64encode(mac).decode("ascii"),
    }


def decrypt(key: bytes, envelope: dict[str, str]) -> str:
    """Authenticate and decrypt a ciphertext envelope produced by :func:`encrypt`."""
    try:
        nonce = base64.b64decode(envelope["nonce"])
        ct = base64.b64decode(envelope["ct"])
        mac = base64.b64decode(envelope["mac"])
    except (KeyError, ValueError, TypeError) as exc:
        raise SecretDecryptionError("malformed ciphertext envelope") from exc
    enc_key, mac_key = _derive_subkeys(key)
    expected = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise SecretDecryptionError("authentication failed (wrong key or tampered data)")
    ks = _keystream(enc_key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks)).decode("utf-8")


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte master key from a passphrase via PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)


# --------------------------------------------------------------------------- #
# Metadata record — carries NO secret value
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SecretRecord:
    """Non-sensitive metadata describing a stored or referenced secret."""

    name: str
    source: str  # "stored" | "env"
    version: int = 1
    created_at: str = ""
    rotated_at: str = ""
    rotation_interval_days: int | None = None
    env_var: str | None = None  # set when source == "env"

    def is_due_for_rotation(self, *, now: datetime | None = None) -> bool:
        if not self.rotation_interval_days or not self.rotated_at:
            return False
        now = now or datetime.now(timezone.utc)
        try:
            rotated = datetime.fromisoformat(self.rotated_at)
        except ValueError:
            return False
        return now >= rotated + timedelta(days=self.rotation_interval_days)

    def to_public_dict(self) -> dict:
        """Public, value-free view safe for CLI/JSON/audit output."""
        return {
            "name": self.name,
            "source": self.source,
            "version": self.version,
            "created_at": self.created_at,
            "rotated_at": self.rotated_at,
            "rotation_interval_days": self.rotation_interval_days,
            "env_var": self.env_var,
            "rotation_due": self.is_due_for_rotation(),
        }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_private_bytes(path: Path, data: bytes) -> None:
    """Atomically create/overwrite *path* readable only by its owner (0600).

    The file is created with mode ``0o600`` in the ``os.open`` call itself, so
    there is no window in which it exists at looser permissions before a
    separate ``chmod`` — the flaw of write-then-chmod. ``fchmod`` on the open
    descriptor additionally tightens a file left over from a prior crash without
    introducing a path-based race.
    """
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        os.fchmod(fh.fileno(), 0o600)
        fh.write(data)


# --------------------------------------------------------------------------- #
# The store
# --------------------------------------------------------------------------- #
class SecretStore:
    """Encrypted local secret store keyed by secret name.

    The on-disk JSON holds only ciphertext envelopes and value-free metadata.
    Stored values are encrypted with *key*; env-referenced secrets persist only
    the env-var name and are resolved from the process environment on read.
    """

    def __init__(self, path: Path, key: bytes) -> None:
        self.path = Path(path)
        self._key = key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    # ----- persistence ---------------------------------------------------- #
    def _load(self) -> dict:
        if not self.path.exists():
            return {"version": STORE_VERSION, "secrets": {}}
        data = json.loads(self.path.read_text())
        data.setdefault("secrets", {})
        return data

    def _save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = json.dumps(self._data, indent=2, sort_keys=True).encode("utf-8")
        _write_private_bytes(tmp, payload)
        tmp.replace(self.path)

    # ----- mutation ------------------------------------------------------- #
    def put(self, name: str, value: str, *, rotation_interval_days: int | None = None) -> SecretRecord:
        """Store (or replace) an encrypted secret value under *name*."""
        now = _utcnow()
        entry = self._data["secrets"].get(name, {})
        record_meta = {
            "source": "stored",
            "cipher": encrypt(self._key, value),
            "version": 1,
            "created_at": entry.get("created_at", now),
            "rotated_at": now,
            "rotation_interval_days": rotation_interval_days
            if rotation_interval_days is not None
            else entry.get("rotation_interval_days"),
        }
        self._data["secrets"][name] = record_meta
        self._save()
        return self.metadata(name)

    def put_reference(self, name: str, env_var: str, *, rotation_interval_days: int | None = None) -> SecretRecord:
        """Register an env-var *reference*; only the variable name is persisted."""
        now = _utcnow()
        entry = self._data["secrets"].get(name, {})
        self._data["secrets"][name] = {
            "source": "env",
            "env_var": env_var,
            "version": entry.get("version", 1),
            "created_at": entry.get("created_at", now),
            "rotated_at": entry.get("rotated_at", now),
            "rotation_interval_days": rotation_interval_days
            if rotation_interval_days is not None
            else entry.get("rotation_interval_days"),
        }
        self._save()
        return self.metadata(name)

    def rotate(self, name: str, new_value: str | None = None) -> SecretRecord:
        """Rotate *name*: bump version and stamp ``rotated_at``.

        Stored secrets require *new_value*. Env references record the rotation
        event only (the value itself rotates in the environment/secret manager).
        """
        if name not in self._data["secrets"]:
            raise SecretNotFound(name)
        entry = self._data["secrets"][name]
        now = _utcnow()
        if entry["source"] == "stored":
            if new_value is None:
                raise ValueError("rotating a stored secret requires a new value")
            entry["cipher"] = encrypt(self._key, new_value)
        entry["version"] = int(entry.get("version", 1)) + 1
        entry["rotated_at"] = now
        self._save()
        return self.metadata(name)

    def delete(self, name: str) -> None:
        if name not in self._data["secrets"]:
            raise SecretNotFound(name)
        del self._data["secrets"][name]
        self._save()

    # ----- read ----------------------------------------------------------- #
    def names(self) -> list[str]:
        return sorted(self._data["secrets"].keys())

    def metadata(self, name: str) -> SecretRecord:
        if name not in self._data["secrets"]:
            raise SecretNotFound(name)
        entry = self._data["secrets"][name]
        return SecretRecord(
            name=name,
            source=entry["source"],
            version=int(entry.get("version", 1)),
            created_at=entry.get("created_at", ""),
            rotated_at=entry.get("rotated_at", ""),
            rotation_interval_days=entry.get("rotation_interval_days"),
            env_var=entry.get("env_var"),
        )

    def list_metadata(self) -> list[SecretRecord]:
        return [self.metadata(name) for name in self.names()]

    def get(self, name: str) -> SecretValue:
        """Return the resolved secret value wrapped in :class:`SecretValue`.

        For ``stored`` secrets this decrypts the envelope; for ``env`` secrets
        it reads the referenced variable from the process environment. Callers
        must explicitly ``.reveal()`` to obtain the raw string.
        """
        if name not in self._data["secrets"]:
            raise SecretNotFound(name)
        entry = self._data["secrets"][name]
        if entry["source"] == "stored":
            return SecretValue(decrypt(self._key, entry["cipher"]))
        env_var = entry["env_var"]
        if env_var not in os.environ:
            raise SecretNotFound(f"environment variable {env_var} for secret '{name}' is not set")
        return SecretValue(os.environ[env_var])

    def secret_values(self) -> set[str]:
        """Return all resolvable raw secret values, for feeding the redactor.

        Used only to build a redaction set; the returned strings must never be
        logged. Unset env references are silently skipped.
        """
        values: set[str] = set()
        for name in self.names():
            try:
                values.add(self.get(name).reveal())
            except SecretNotFound:
                continue
        return values

    def __repr__(self) -> str:  # never reveal contents
        return f"SecretStore(path={self.path!s}, count={len(self._data['secrets'])})"


# --------------------------------------------------------------------------- #
# Key resolution + command-facing helpers
# --------------------------------------------------------------------------- #
def default_store_path(state_dir: Path) -> Path:
    return Path(state_dir) / "secrets" / "secrets.json"


def resolve_key(state_dir: Path, *, passphrase: str | None = None) -> bytes:
    """Resolve the master key for a state dir.

    Preference order:
    1. *passphrase* argument, derived against a persisted per-store salt.
    2. ``ODOOCTL_SECRET_KEY`` env var, derived against the persisted salt.
    3. A random 32-byte key persisted at ``secrets/master.key`` (0600).

    The salt/key file lives beside the store so a single host can reopen it
    without re-entering a passphrase; rotating the passphrase re-derives.
    """
    secrets_dir = Path(state_dir) / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    passphrase = passphrase if passphrase is not None else os.environ.get(KEY_ENV_VAR)

    if passphrase:
        salt_path = secrets_dir / "salt"
        if salt_path.exists():
            salt = salt_path.read_bytes()
        else:
            salt = _stdlib_secrets.token_bytes(16)
            _write_private_bytes(salt_path, salt)
        return derive_key(passphrase, salt)

    key_path = secrets_dir / "master.key"
    if key_path.exists():
        return base64.b64decode(key_path.read_text().strip())
    key = _stdlib_secrets.token_bytes(32)
    _write_private_bytes(key_path, base64.b64encode(key))
    return key


def open_store(state_dir: Path, *, passphrase: str | None = None) -> SecretStore:
    """Open (or create) the secret store for a project state directory."""
    key = resolve_key(state_dir, passphrase=passphrase)
    return SecretStore(default_store_path(state_dir), key)
