from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

SENSITIVE_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "KEY", "PASSWD")

@dataclass(slots=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

class CommandError(RuntimeError):
    def __init__(self, result: CommandResult):
        super().__init__(f"Command failed ({result.returncode}): {' '.join(result.args)}\n{result.stderr}")
        self.result = result

def redact(text: str, env: Mapping[str, str] | None = None) -> str:
    env = env or os.environ
    redacted = text
    for key, value in env.items():
        if value and any(marker in key.upper() for marker in SENSITIVE_MARKERS):
            redacted = redacted.replace(value, "***REDACTED***")
    return redacted

def run(args: Sequence[str], *, check: bool = True, cwd: str | None = None, env: Mapping[str, str] | None = None, stream: bool = False) -> CommandResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    if stream:
        proc = subprocess.Popen(list(args), cwd=cwd, env=merged_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = []
        assert proc.stdout is not None
        for line in proc.stdout:
            clean = redact(line, merged_env)
            print(clean, end="")
            output.append(clean)
        rc = proc.wait()
        result = CommandResult(list(args), rc, "".join(output), "")
    else:
        proc = subprocess.run(list(args), cwd=cwd, env=merged_env, text=True, capture_output=True)
        result = CommandResult(list(args), proc.returncode, redact(proc.stdout, merged_env), redact(proc.stderr, merged_env))
    if check and result.returncode != 0:
        raise CommandError(result)
    return result

def _merged_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return merged_env


def run_capture_bytes(
    args: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    stdout_path: str | Path,
    check: bool = True,
) -> CommandResult:
    """Run a command and write raw stdout bytes to a file.

    This is binary-safe for PostgreSQL custom-format dumps: stdout never passes
    through Python text decoding or redaction.
    """
    merged_env = _merged_env(env)
    output_path = Path(stdout_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as stdout:
        proc = subprocess.run(list(args), cwd=cwd, env=merged_env, stdout=stdout, stderr=subprocess.PIPE)
    stderr = redact(proc.stderr.decode(errors="replace"), merged_env)
    result = CommandResult(list(args), proc.returncode, str(output_path), stderr)
    if check and result.returncode != 0:
        raise CommandError(result)
    return result


def run_pipe_stdin(
    args: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    stdin_path: str | Path,
    check: bool = True,
) -> CommandResult:
    """Run a command with raw bytes from a file connected to stdin."""
    merged_env = _merged_env(env)
    with Path(stdin_path).open("rb") as stdin:
        proc = subprocess.run(list(args), cwd=cwd, env=merged_env, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = redact(proc.stdout.decode(errors="replace"), merged_env)
    stderr = redact(proc.stderr.decode(errors="replace"), merged_env)
    result = CommandResult(list(args), proc.returncode, stdout, stderr)
    if check and result.returncode != 0:
        raise CommandError(result)
    return result


def join_csv(values: Iterable[str]) -> str:
    return ",".join(v.strip() for v in values if v and v.strip())
