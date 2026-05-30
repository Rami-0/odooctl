"""Per-environment file-based concurrency locks with same-thread reentrancy."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

# Per-thread set of lock file paths currently held by this thread.
# Enables reentrant acquisition from the same thread (e.g. rollback → restore).
_thread_held: threading.local = threading.local()


def _held_set() -> set:
    if not hasattr(_thread_held, "locks"):
        _thread_held.locks = set()
    return _thread_held.locks


class LockAcquisitionError(RuntimeError):
    """Raised when an environment lock cannot be acquired."""


class EnvironmentLock:
    """Atomic per-environment lock backed by an O_EXCL lock file.

    Uses O_CREAT|O_EXCL for atomicity. Stale locks (dead PID) are cleared on
    first acquisition attempt. Reentrant for the same OS thread — a thread that
    already holds the lock can re-acquire it without blocking.
    """

    def __init__(self, environment: str, state_dir: Path, op_id: str = "") -> None:
        self._env = environment
        self._path = state_dir / "locks" / f"{environment}.lock"
        self._op_id = op_id
        self._reentrant = False

    @property
    def path(self) -> Path:
        return self._path

    def __enter__(self) -> "EnvironmentLock":
        held = _held_set()
        if self._path in held:
            self._reentrant = True
            return self
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._try_create()
        held.add(self._path)
        return self

    def _try_create(self, *, retried: bool = False) -> None:
        payload = json.dumps({"pid": os.getpid(), "op_id": self._op_id}).encode()
        try:
            fd = os.open(str(self._path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)
        except FileExistsError:
            if retried:
                raise LockAcquisitionError(
                    f"Environment '{self._env}' is locked (race on stale lock removal)"
                )
            self._handle_existing()

    def _handle_existing(self) -> None:
        try:
            data = json.loads(self._path.read_text())
            pid = int(data.get("pid", 0))
            op_id = data.get("op_id", "")
        except Exception:
            raise LockAcquisitionError(
                f"Environment '{self._env}' is locked (unreadable lock file)"
            )
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            # Stale lock — PID is dead, remove and retry once
            self._path.unlink(missing_ok=True)
            self._try_create(retried=True)
            return
        except PermissionError:
            # PID exists but we lack signal permission — treat as alive
            pass
        raise LockAcquisitionError(
            f"Environment '{self._env}' is locked by operation {op_id!r} (PID {pid})"
        )

    def __exit__(self, *_args: object) -> None:
        if self._reentrant:
            return
        _held_set().discard(self._path)
        self._path.unlink(missing_ok=True)
