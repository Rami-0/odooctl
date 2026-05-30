# Contributing to odooctl

Thanks for your interest in `odooctl`. This document covers the developer
setup, the checks we run, and the conventions we follow for code, commits,
and docs.

## Ground rules

- `odooctl` operates real Odoo databases and filestores. Default to safe,
  reversible behavior; protect production with explicit confirmation and
  backups.
- Discuss non-trivial changes in an issue before opening a large pull
  request.
- By contributing, you agree that your contributions are licensed under the
  project's MIT License (see `LICENSE`).

## Development setup

`odooctl` uses [`uv`](https://docs.astral.sh/uv/) for dependency
management.

```bash
git clone https://github.com/Rami-0/odooctl.git
cd odooctl
uv venv
uv pip install -e '.[dev]'
```

Optional extras:

- `uv pip install -e '.[dev,s3]'` to work on the real S3 adapter.

Python 3.11 or newer is required.

## Tests, lint, and build

Run the same checks CI expects before opening a pull request:

```bash
uv run pytest -q                                    # unit tests
ODOO_DB_PASSWORD=odoo uv run pytest -q              # same suite with a secret env var set
uv run ruff check .                                 # lint
uv run python -m build                              # sdist + wheel build
```

Notes:

- The default `pytest` configuration excludes the `integration` marker.
- Run integration tests explicitly with `uv run pytest -q -m integration`.
  They require external services (Docker, a running Odoo stack) and are not
  part of the default PR gate.
- The Docker integration fixture lives under
  `experiments/odoo19-community-staging/`. Use it to validate
  backup/restore/clone/update-modules end-to-end before shipping
  changes that touch those code paths. See its `README.md` for usage.

## Branching and commits

- Work from `master`. Create a feature branch named for the change, for
  example `feat/docker-volume-filestore` or `fix/clone-swap-guard`.
- Keep commits focused. Prefer multiple small, well-described commits over
  one large catch-all commit.
- Write commit messages in the imperative mood:
  `Add Docker PostgreSQL adapter`, not `Added` or `Adds`.
- The first line should be a short summary (under ~70 characters). Add a
  body when the change needs justification, links to issues, or
  upgrade/operator notes.
- Reference issues in the body when applicable
  (`Closes #123`, `Refs #456`).

## Pull requests

Each pull request should:

- Stay focused on one logical change.
- Include tests for new behavior or regressions you are fixing.
- Update docs under `docs/` and `examples/` when user-visible behavior,
  configuration, or commands change.
- Pass `uv run pytest -q`, `uv run ruff check .`, and
  `uv run python -m build` locally.
- Note any deliberate skips (for example, integration runs that require a
  live Docker/Odoo fixture you could not reproduce locally).

## Code conventions

- Target Python 3.11+; respect the typing already used in the codebase.
- Keep adapters (`odooctl/adapters/`) free of CLI/UX concerns; route
  user-facing output through `odooctl/commands/`.
- Treat process working directory as untrusted: anchor file paths through
  `ProjectContext` instead of `os.getcwd()`.
- Do not log raw secrets. Use the redaction helpers and respect
  `redaction.min_secret_length` / `redaction.ignore_values`.
- Sanitization SQL must remain idempotent and guarded so it can run against
  any clone without raising on missing tables.

## Tests

- New unit tests belong under `tests/` and should run without Docker, a
  network, or environment variables that are not provided by the test.
- Use the `integration` marker for tests that require Docker or a real
  Odoo stack. They will be skipped by default and run explicitly with
  `-m integration`.
- The `docker` marker is reserved for tests that require Docker
  specifically.

## Documentation

- Update the relevant page in `docs/` for any user-visible change
  (commands, flags, config fields, defaults, safety behavior).
- Keep `README.md` examples in sync with actual CLI behavior.
- If you add or change a command, also update `examples/odooctl.yml` and
  the matching page under `docs/`.

## Reporting bugs and proposing features

- File a GitHub issue with a clear reproduction, your `odooctl` version,
  Python version, host OS, and execution mode (`host` or `docker`).
- For security issues, follow `SECURITY.md` instead of opening a public
  issue.

## Code of Conduct

Participation in this project is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md). By contributing, you agree to abide
by its terms.
