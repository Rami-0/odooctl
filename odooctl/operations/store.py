"""Persistent storage for operation records and event streams."""
from __future__ import annotations

from pathlib import Path

from odooctl.operations.models import Event, Operation, OperationStatus, _utcnow


class OperationStore:
    def __init__(self, state_dir: Path) -> None:
        self._root = state_dir / "operations"
        self._root.mkdir(parents=True, exist_ok=True)

    def _op_dir(self, op_id: str) -> Path:
        return self._root / op_id

    def save(self, op: Operation) -> None:
        d = self._op_dir(op.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "operation.json").write_text(op.to_json())

    def load(self, op_id: str) -> Operation:
        path = self._op_dir(op_id) / "operation.json"
        if not path.exists():
            raise KeyError(f"Operation not found: {op_id}")
        return Operation.from_json(path.read_text())

    def list_all(self, *, limit: int = 50) -> list[Operation]:
        ops: list[Operation] = []
        if not self._root.exists():
            return ops
        dirs = sorted(
            (d for d in self._root.iterdir() if d.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for d in dirs:
            path = d / "operation.json"
            if path.exists():
                try:
                    ops.append(Operation.from_json(path.read_text()))
                except Exception:
                    continue
            if len(ops) >= limit:
                break
        return ops

    def update_status(
        self,
        op_id: str,
        status: OperationStatus,
        *,
        error: str | None = None,
        result_ref: str | None = None,
    ) -> Operation:
        op = self.load(op_id)
        op.status = status
        op.updated_at = _utcnow()
        if error is not None:
            op.error = error
        if result_ref is not None:
            op.result_ref = result_ref
        self.save(op)
        return op

    def append_event(self, op_id: str, event: Event) -> None:
        d = self._op_dir(op_id)
        d.mkdir(parents=True, exist_ok=True)
        with (d / "events.jsonl").open("a") as f:
            f.write(event.to_json() + "\n")

    def load_events(self, op_id: str) -> list[Event]:
        path = self._op_dir(op_id) / "events.jsonl"
        if not path.exists():
            return []
        events: list[Event] = []
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    events.append(Event.from_json(stripped))
                except Exception:
                    continue
        return events
