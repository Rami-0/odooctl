from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from odooctl.context import ProjectContext


@dataclass(frozen=True)
class ScheduleSpec:
    command: str
    environment: str
    project_root: Path
    config_path: Path
    interval: str
    user: str | None = None
    odooctl_bin: str = "odooctl"

    @property
    def unit_name(self) -> str:
        safe_env = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in self.environment)
        return f"odooctl-{self.command}-{safe_env}"

    @property
    def invocation(self) -> str:
        return (
            f"{self.odooctl_bin} --project-dir {self.project_root} "
            f"{self.command} {self.environment} --config {self.config_path}"
        )


def build_spec(
    command: str,
    environment: str,
    config_path: str = "odooctl.yml",
    *,
    interval: str = "daily",
    user: str | None = None,
    odooctl_bin: str = "odooctl",
) -> ScheduleSpec:
    ctx = ProjectContext.from_config_path(config_path)
    cfg = ctx.config
    if command not in {"backup", "doctor", "sync"}:
        raise ValueError("schedule command must be one of: backup, doctor, sync")
    if environment not in cfg.environments:
        raise ValueError(f"Unknown environment: {environment}")
    return ScheduleSpec(
        command=command,
        environment=environment,
        project_root=ctx.root,
        config_path=ctx.config_path,
        interval=interval,
        user=user,
        odooctl_bin=odooctl_bin,
    )


def render_systemd(spec: ScheduleSpec) -> str:
    user_line = f"User={spec.user}\n" if spec.user else ""
    return f"""# /etc/systemd/system/{spec.unit_name}.service
[Unit]
Description=Run odooctl {spec.command} for {spec.environment}

[Service]
Type=oneshot
WorkingDirectory={spec.project_root}
{user_line}ExecStart={spec.invocation}

# /etc/systemd/system/{spec.unit_name}.timer
[Unit]
Description=Schedule odooctl {spec.command} for {spec.environment}

[Timer]
OnCalendar={spec.interval}
Persistent=true

[Install]
WantedBy=timers.target
"""


def render_cron(spec: ScheduleSpec) -> str:
    cron_expr = _cron_expression(spec.interval)
    cd_and_run = f"cd {spec.project_root} && {spec.invocation}"
    if spec.user:
        return f"{cron_expr} {spec.user} {cd_and_run}\n"
    return f"{cron_expr} {cd_and_run}\n"


def _cron_expression(interval: str) -> str:
    aliases = {
        "hourly": "0 * * * *",
        "daily": "0 2 * * *",
        "weekly": "0 2 * * 0",
    }
    return aliases.get(interval, interval)


# Per-command default intervals by output format. `sync` polls the remote, so
# its default is minutes, not days; everything else stays daily.
DEFAULT_INTERVALS: dict[str, dict[str, str]] = {
    "sync": {"systemd": "*:0/5", "cron": "*/5 * * * *"},
}


def render(
    command: str,
    environment: str,
    config_path: str = "odooctl.yml",
    *,
    format: str = "systemd",
    interval: str | None = None,
    user: str | None = None,
    odooctl_bin: str = "odooctl",
) -> str:
    if interval is None:
        interval = DEFAULT_INTERVALS.get(command, {}).get(format, "daily")
    spec = build_spec(command, environment, config_path, interval=interval, user=user, odooctl_bin=odooctl_bin)
    if format == "systemd":
        return render_systemd(spec)
    if format == "cron":
        return render_cron(spec)
    raise ValueError("schedule format must be one of: systemd, cron")
