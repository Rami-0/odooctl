# Runner architecture — web/API vs. privileged runner

This document describes the privilege split that the security model
(`docs/rbac.md`) depends on. The split is enforced structurally by
`odooctl/security/runner_contract.py` and checked in CI/tests.

## V1 security boundary

V1 is a single-host Docker Compose deployment. Two trust zones run on that one
host:

```
                 RBAC + capability token
  ┌────────────┐  ───────────────────────▶  ┌─────────────────────────┐
  │  web/API   │      enqueue operation       │   privileged runner     │
  │  process   │ ◀───────────────────────     │   (Docker socket, etc.) │
  └────────────┘      events / state          └─────────────────────────┘
   no Docker socket                              Docker / Postgres / git / tar
```

- The **web/API process never mounts the Docker socket** and never runs Docker,
  Postgres, git, or tar work.
- The **privileged runner** performs all of that, on the same host, behind the
  durable operation queue.

Remote runners and hosted multi-tenant worker pools are explicit future work.

## What each side may do

| web/API may | runner may |
| --- | --- |
| read state | access Docker / Compose |
| enqueue operations | run Postgres commands |
| stream operation events | manage filestore archives |
| read the audit trail (per RBAC) | run git operations |

These capability lists are encoded as `API_ALLOWED_CAPABILITIES` and
`RUNNER_ALLOWED_CAPABILITIES` in `runner_contract.py`.

## How the contract is enforced

The privileged adapters live under:

- `odooctl.adapters.*` — `docker_compose`, `postgres`, `db`, `filestore`, `s3`,
  `reverse_proxy`
- `odooctl.odoo.*` — `db_swap`, `module_update`, `sanitize`, `healthcheck`

The future API/web packages (`odooctl.api`, `odooctl.web`) **must not import any
of these directly**. Instead they go through the service/operation layer, which
enqueues work the runner executes.

`runner_contract.py` parses the source of each API/web package (via `ast`,
without importing it) and reports any direct absolute or relative import of a
privileged module. This static check is a guardrail, not a sandbox; dynamic
imports with computed names remain out of scope, and the process boundary is the
real privilege separation:

```python
from odooctl.security.runner_contract import (
    assert_api_does_not_import_privileged,
    find_violations,
)

assert_api_does_not_import_privileged()   # raises RunnerContractViolation if dirty
```

There is no API package yet, so `find_violations()` returns an empty list today.
The check is written so that the moment an `odooctl/api/` or `odooctl/web/`
module lands with a forbidden import, the test in `tests/test_security.py`
fails. Run it manually with:

```console
$ odooctl security runner-check
```

## Capability tokens across the boundary

Because the API cannot act directly, it authorizes the runner per operation
with a signed [capability token](rbac.md#capability-tokens). The token binds the
work to a single action, environment, and project, with a short TTL. A leaked
token cannot be used against a different target or after expiry, but it can be
replayed for the same scope while still valid unless the runner tracks consumed
nonces and rejects repeats.

## Why a stdlib-only crypto core

The secret store and capability tokens use only Python's standard library
(`hmac`, `hashlib`, `secrets`, `base64`, `json`, `time`). For a single-host v1
this avoids adding a `cryptography` dependency while still providing
authenticated encryption (encrypt-then-MAC) for secrets at rest and HMAC-signed,
scope-limited, expiring tokens for runner authorization. If a future milestone
introduces remote runners or at-rest requirements that need AES-GCM or
asymmetric signatures, the `secrets`/`tokens` modules are the contained seams to
upgrade.
