"""Append-only audit trail with SHA-256 hash chain."""
from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path

from odooctl.operations.models import AuditEntry


def _hash_entry(entry_dict: dict, prev_hash: str) -> str:
    payload = {**entry_dict, "prev_hash": prev_hash}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


class AuditStore:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: AuditEntry) -> AuditEntry:
        # Exclusive lock on a sidecar file guards the read-last-hash + write as one
        # atomic unit across threads and processes, preventing audit-chain forks.
        lock_path = self.path.with_suffix(".lock")
        with lock_path.open("w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            prev_hash = self._last_hash()
            entry.prev_hash = prev_hash
            entry_dict = entry.to_dict()
            entry.current_hash = _hash_entry(entry_dict, prev_hash)
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


def verify_chain(entries: list[AuditEntry]) -> bool:
    """Return True if the hash chain is intact, False if any entry was tampered."""
    prev_hash = ""
    for entry in entries:
        if entry.prev_hash != prev_hash:
            return False
        expected = _hash_entry(entry.to_dict(), prev_hash)
        if entry.current_hash != expected:
            return False
        prev_hash = entry.current_hash
    return True
