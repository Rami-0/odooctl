# Examples

## Generate and validate a starter config

```bash
odooctl init --dry-run
odooctl init
odooctl validate
```

## Clone production into staging

```bash
odooctl clone production staging --sanitize
```

This uses the configured `clone_from`, filestore paths, sanitization rules, and post-clone module update list from `odooctl.yml`.

If you only want to validate the source/target wiring without mutating anything, run `odooctl status --environment staging --json` first and inspect the configured domains and database names.

## Deploy staging from a branch

```bash
odooctl deploy staging --branch staging
```

## Production safety workflow

```bash
odooctl backup production
odooctl deploy production --branch main
odooctl status
```

Production deploys are designed to preserve rollback points by capturing a backup before code changes.

## Restore a backup into staging

```bash
odooctl restore staging --backup latest
```

Use restore when you want to rebuild a staging environment from a known-good backup without re-running a clone flow.

## Generate a GitHub Actions deploy workflow

```bash
odooctl github-actions --dry-run
odooctl github-actions
```

This writes a manual `workflow_dispatch` pipeline that checks out the repository, installs `odooctl`, validates the config, and runs a deployment from GitHub Actions using secrets for the database password. A ready-to-copy example lives at `.github/workflows/odooctl-deploy.yml`, and `examples/github-actions.yml` shows a simpler push-based variant.

The generated workflow is intended for production deploys, but the same pattern can be adapted for staging by changing the branch input or environment selection.
