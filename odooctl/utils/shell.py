from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
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

def join_csv(values: Iterable[str]) -> str:
    return ",".join(v.strip() for v in values if v and v.strip())
