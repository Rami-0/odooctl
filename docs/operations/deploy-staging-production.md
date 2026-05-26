# Production, staging, and git workflow

This is the working model for `odooctl` deployments.

## Source of truth

- **Git branch** decides what code is deployable.
- **Environment config** decides where it goes.
- **Staging** should clone from production unless explicitly configured otherwise.
- **Production** is the release boundary and should be treated as immutable during rollback decisions.

## Recommended flow

### 1) Prepare code

1. Merge the feature branch into the environment branch.
2. Run validation locally:
   - `odooctl validate`
3. Ensure the compose file, env vars, and filestore paths exist.
4. Ensure the git worktree is clean before deploys or code rollbacks; commit or stash local edits first.

### 2) Deploy staging first

1. Preview the clone first and confirm the printed mapping: source, target, `clone_from`, source branch, and target branch.
2. Clone or refresh staging from the configured source environment.
3. Apply sanitization.
4. Restart the Odoo service.
5. Run module updates if the environment requires them.
6. Verify the healthcheck URL.

### 3) Promote to production

1. Create a production backup first.
2. Deploy the exact branch that production is pinned to.
3. Pull the image / services.
4. Run module updates.
5. Check health.
6. Record deployment metadata.

### 4) Rollback decision

- Use **code rollback** when the deploy failed or the new code is bad. It targets the last successful deployment commit recorded in metadata and refuses to run if no commit is available.
- Code rollback requires a clean git worktree before it checks out the recorded commit. Commit or stash local edits first.
- Use **full rollback** when database/filestore state must be restored.
- A failed production deploy may restart the Odoo service as a recovery attempt, but it does **not** automatically roll back code or data; run `odooctl rollback production --mode code` or `odooctl rollback production --mode full` deliberately after deciding which state must be restored.
- Keep the previous backup id and deployment metadata attached to the release.

## Git repo integration

A GitHub Actions workflow should:

- validate the config first,
- accept only the branch/environment pair that matches the config,
- run the deploy command with the chosen environment and branch,
- fail early if the pair is invalid.

For manual ops, the branch used in deploy should always match the environment config. That prevents staging being pointed at production code or production being pointed at a feature branch.

## Operator checklist

- [ ] Config validates cleanly
- [ ] Git worktree is clean; local edits are committed or stashed
- [ ] Branch matches environment mapping
- [ ] Each environment has a unique branch, database name, filestore path, and domain
- [ ] Staging clone source is correct
- [ ] Production backup completed
- [ ] Healthcheck endpoint is reachable
- [ ] Metadata saved for the deploy
