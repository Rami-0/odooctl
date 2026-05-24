# Examples

## Generate a starter config

```bash
odooctl init --dry-run
odooctl init
```

## Clone production into staging

```bash
odooctl clone production staging --sanitize
```

This uses the configured `clone_from`, filestore paths, sanitization rules, and post-clone module update list from `odooctl.yml`.

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

## Generate a GitHub Actions deploy workflow

```bash
odooctl github-actions --dry-run
odooctl github-actions
```

This writes a manual `workflow_dispatch` pipeline that checks out the repository, installs `odooctl`, and runs a deployment from GitHub Actions using secrets for the database password.
