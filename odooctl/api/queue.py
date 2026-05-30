"""Durable operation queue — written by the API, consumed by the runner.

Queue entries are plain JSON files in ``{state_dir}/queue/``. The API writes
``{op_id}.json``; the runner atomically renames it to ``{op_id}.running``
(POSIX rename is atomic within the same filesystem) before executing, then
removes it on success or renames it to ``{op_id}.failed`` on error.

This module has NO privileged imports — it must satisfy the runner contract
(see ``odooctl.security.runner_contract``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QueueEntry:
    op_id: str
    kind: str
    project: str
    environment: str
    actor: str
    params_redacted: dict
    token: str
    created_at: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "op_id": self.op_id,
                "kind": self.kind,
                "project": self.project,
                "environment": self.environment,
                "actor": self.actor,
                "params_redacted": self.params_redacted,
                "token": self.token,
                "created_at": self.created_at,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> "QueueEntry":
        d = json.loads(text)
        return cls(
            op_id=d["op_id"],
            kind=d["kind"],
            project=d["project"],
            environment=d["environment"],
            actor=d["actor"],
            params_redacted=d.get("params_redacted", {}),
            token=d["token"],
            created_at=d.get("created_at", ""),
        )

    @classmethod
    def create(
        cls,
        op_id: str,
        kind: str,
        project: str,
        environment: str,
        actor: str,
        params_redacted: dict,
        token: str,
    ) -> "QueueEntry":
        return cls(
            op_id=op_id,
            kind=kind,
            project=project,
            environment=environment,
            actor=actor,
            params_redacted=params_redacted,
            token=token,
            created_at=_utcnow(),
        )


class OperationQueue:
    """File-backed durable operation queue.

    Each pending entry is ``{state_dir}/queue/{op_id}.json``.
    Claiming renames it to ``{op_id}.running`` atomically (POSIX).
    """

    def __init__(self, state_dir: Path) -> None:
        self._root = state_dir / "queue"
        self._root.mkdir(parents=True, exist_ok=True)

    def enqueue(self, entry: QueueEntry) -> None:
        target = self._root / f"{entry.op_id}.json"
        tmp = self._root / f"{entry.op_id}.json.tmp"
        tmp.write_text(entry.to_json())
        tmp.rename(target)

    def cancel(self, op_id: str) -> None:
        """Remove a pending queue entry so the runner cannot claim it."""
        try:
            (self._root / f"{op_id}.json").unlink()
        except FileNotFoundError:
            pass

    def claim_next(self) -> QueueEntry | None:
        """Atomically claim the oldest pending entry, or return None."""
        candidates = sorted(
            self._root.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        for path in candidates:
            claimed = path.with_suffix(".running")
            try:
                path.rename(claimed)
            except (FileNotFoundError, OSError):
                continue
            try:
                return QueueEntry.from_json(claimed.read_text())
            except Exception:
                claimed.rename(path.with_suffix(".corrupt"))
                continue
        return None

    def complete(self, op_id: str) -> None:
        path = self._root / f"{op_id}.running"
        if path.exists():
            path.unlink()

    def fail(self, op_id: str) -> None:
        path = self._root / f"{op_id}.running"
        if path.exists():
            path.rename(self._root / f"{op_id}.failed")
