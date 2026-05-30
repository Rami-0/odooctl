"""Branch status service — compute per-environment drift and deployment state."""
from __future__ import annotations

from typing import TYPE_CHECKING

from odooctl.metadata.store import MetadataStore
from odooctl.services.models import BranchStatus
from odooctl.utils.shell import run

if TYPE_CHECKING:
    from odooctl.services.context import ServiceContext


def _git_rev(ref: str, cwd: str | None = None) -> str | None:
    result = run(["git", "rev-parse", "--short", ref], check=False, cwd=cwd)
    stdout = result.stdout.strip()
    return stdout if stdout else None


def _git_count(a: str, b: str, cwd: str | None = None) -> int | None:
    result = run(["git", "rev-list", "--count", f"{a}..{b}"], check=False, cwd=cwd)
    try:
        return int(result.stdout.strip())
    except (ValueError, TypeError):
        return None


def _compute_drift(
    current: str | None, deployed: str | None, cwd: str | None
) -> tuple[int | None, int | None, str]:
    if current is None or deployed is None:
        return None, None, "unknown"
    if current == deployed:
        return 0, 0, "clean"
    ahead = _git_count(deployed, current, cwd=cwd)
    behind = _git_count(current, deployed, cwd=cwd)
    if ahead is None or behind is None:
        return ahead, behind, "unknown"
    if ahead > 0 and behind == 0:
        return ahead, 0, "ahead"
    if ahead == 0 and behind > 0:
        return 0, behind, "behind"
    if ahead > 0 and behind > 0:
        return ahead, behind, "diverged"
    return 0, 0, "clean"


def get_branch_statuses(ctx: ServiceContext) -> list[BranchStatus]:
    cfg = ctx.project.config
    meta = MetadataStore(ctx.project.state_dir)
    cwd = str(ctx.project.root)
    statuses = []
    for name, env in sorted(cfg.environments.items()):
        current_commit = _git_rev(env.branch, cwd=cwd)
        last_dep = meta.latest_deployment(name)
        last_deployed_commit = last_dep.get("commit") if last_dep else None
        ahead, behind, drift = _compute_drift(current_commit, last_deployed_commit, cwd=cwd)
        effective_tier = env.tier or ("production" if name == "production" else None)
        statuses.append(
            BranchStatus(
                environment=name,
                tier=effective_tier,
                branch=env.branch,
                current_commit=current_commit,
                last_deployed_commit=last_deployed_commit,
                ahead=ahead,
                behind=behind,
                drift=drift,
            )
        )
    return statuses
