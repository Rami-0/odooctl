# odooctl Control-Plane Progress

Primary plan index: `docs/plans/README.md`

## Operating rules

- Work milestones M6 → M15 in order unless explicitly reprioritized.
- Before each run: inspect git status, read active milestone plan, inspect current code.
- After each run: update this file with changed files, tests, result, blockers, and next step.
- Do not mark a task complete unless verified.
- Engine-touching milestones require real Odoo fixture evidence.

## Progress log

### 2026-05-30 — V1 scope hardened

- Locked v1 deployment mode: single-host Docker Compose only.
- Locked v1 reverse proxy: Traefik adapter behind explicit reverse proxy abstraction.
- Locked v1 UI: FastAPI API + static SPA served by `odooctl serve`.
- Locked import safety contract: read-only detection, no restart/redeploy/DB writes/volume changes/secret printing, preview-first, backup-after-adoption.

### 2026-05-30 — Plan reset

- Cleared old M0–M5 implementation plan pack from `docs/plans/`.
- Created new control-plane plan pack based on repo state, Odoo 19 experiment, `community-sh` UX research, and Claude Opus planning review.
- Next milestone: M6 service layer.

## Milestone checklist

### M6 — Service layer

- [ ] Create `odooctl/services/` package.
- [ ] Add structured result models.
- [ ] Extract project/status/doctor services.
- [ ] Extract backup/restore/clone/deploy services.
- [ ] Convert CLI commands into thin wrappers.
- [ ] Add service tests.
- [ ] Verify existing CLI output remains compatible.
- [ ] Run full tests/ruff/build.

### M7 — Operation engine

- [ ] Add operation models/store/events/audit/locks.
- [ ] Wrap mutating services in `run_operation`.
- [ ] Add `odooctl ops list/show/logs/cancel`.
- [ ] Add per-environment lock tests.
- [ ] Add audit-chain tests.
- [ ] Verify live backup/clone emits events and audit.

### M8 — Import/takeover + setup wizard

- [ ] Add compose/Odoo detector.
- [ ] Add import preview report.
- [ ] Generate config without redeploy.
- [ ] Register imported project.
- [ ] Run doctor and verified backup after import.
- [ ] Add newcomer `odooctl setup` wizard.
- [ ] Verify import against Odoo 19 fixture.
- [ ] Add tests enforcing import detection has no mutating command calls.
- [ ] Document the import safety contract in CLI help and docs.

### M9 — Environment/branch model

- [ ] Add environment tiers and protected production semantics.
- [ ] Add branch status/drift detection.
- [ ] Add promote staging → production flow.
- [ ] Add ephemeral branch/dev environment flow.
- [ ] Add rollback-on-failed-promote tests.

### M10 — Onboarding catalog

- [ ] Add catalog manifest schema.
- [ ] Add bundled Odoo stack templates.
- [ ] Add OCA/private/Enterprise addon source model.
- [ ] Add companion service templates.
- [ ] Wire catalog into setup wizard.

### M11 — Security architecture

- [ ] Add org/user/role/principal models.
- [ ] Add RBAC action matrix.
- [ ] Add secret store and rotation commands.
- [ ] Add capability tokens.
- [ ] Enforce web/API vs runner privilege split.
- [ ] Expand security docs.

### M12 — API and runner

- [ ] Add optional FastAPI service.
- [ ] Serve static SPA assets from `odooctl serve`.
- [ ] Add durable queue handoff.
- [ ] Add privileged runner.
- [ ] Add operation event streaming.
- [ ] Add API auth/RBAC tests.
- [ ] Verify API-driven backup/clone via runner.

### M13 — Web UI MVP

- [ ] Add web asset/app structure.
- [ ] Projects page.
- [ ] Environment detail page.
- [ ] Doctor/status/backups/operations views.
- [ ] Clone/promote operation buttons.
- [ ] Streaming operation logs.
- [ ] Verify UI only talks to API.

### M14 — Domain/SSL and backup UX

- [ ] Add domain attach/verify/detach service.
- [ ] Add `ReverseProxyAdapter` abstraction.
- [ ] Add Traefik adapter as the only v1 implementation.
- [ ] Add Traefik ACME/DNS-01 support path.
- [ ] Add restore-point browser service.
- [ ] Add restore-to-staging flow.
- [ ] Add DR drill operation.
- [ ] Add encrypted off-site backup option.

### M15 — Migration assistant

- [ ] Add migration matrix.
- [ ] Add module readiness scan.
- [ ] Add upgrade rehearsal operation.
- [ ] Add OpenUpgrade hook support.
- [ ] Add migration report output/API/UI.
