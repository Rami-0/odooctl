# Report 3 — Odoo 18 CE + 19 CE full/api/ctl experiment
Date: 2026-06-01T09:43:21Z
Repo: /home/dev/odooctl
Commit: 97a487a2a22459bdeff1e28d532c2e359f4ea68a
## Scope
Disposable Docker Compose sweeps for official `odoo:18.0` and `odoo:19.0` images with `postgres:16`, docker-native DB/filestore execution, CLI/ctl paths, FastAPI API routes, queued runner operation, backup/clone/restore/update-module/import/setup/status/logs.
## High-level outcome
Completed with 1 command failures or non-zero outcomes; cleanup was still attempted. See command log.

## What worked
- Official image tags `odoo:18.0` and `odoo:19.0` were present and could be pulled.
- Compose stacks reached Postgres health and Odoo `/web/login` readiness.
- `odooctl validate`, `doctor`, `status`, and `logs --no-follow` worked against disposable configs.
- Docker-native production backup with verification, production→staging clone with sanitization, restore-to-env, and staging queued backup via API/runner were exercised where command logs show exit 0.
- FastAPI served OpenAPI and authenticated project/environments/status/backups/audit routes with an HMAC bearer token.

## Failures / differences
- `baseline: full pytest` exited 1. Tail:

```text
py::test_env_list_and_show_json - AssertionError: 
FAILED tests/test_env_cmd.py::test_env_create_writes_valid_config_and_provisions_with_clone
FAILED tests/test_env_cmd.py::test_env_create_can_skip_provision - AssertionE...
FAILED tests/test_env_cmd.py::test_env_destroy_refuses_production_and_removes_non_production
FAILED tests/test_env_cmd.py::test_env_destroy_purge_drops_db_and_filestore_before_removing_config
FAILED tests/test_env_cmd.py::test_env_open_refuses_reserved_name_production
FAILED tests/test_env_cmd.py::test_env_open_refuses_reserved_name_staging - A...
FAILED tests/test_env_cmd.py::test_env_open_refuses_duplicate_environment - A...
FAILED tests/test_env_cmd.py::test_env_open_no_provision_writes_config_without_clone
FAILED tests/test_env_cmd.py::test_env_open_with_provision_clones_sanitized_from_source
FAILED tests/test_promote.py::test_cli_promote_requires_yes_for_protected_target
FAILED tests/test_promote.py::test_cli_promote_yes_flag_bypasses_protection
FAILED tests/test_registry.py::test_global_project_option_resolves_registered_project_config
FAILED tests/test_registry.py::test_project_dir_option_resolves_config_from_non_project_cwd
14 failed, 709 passed in 7.52s
```

## Validation of earlier scan claims
- Confirmed practical dependence on Docker-native DB service execution: this host lacked host `pg_dump`/`psql`, while docker-mode operations could use the Postgres service tools.
- Confirmed the API/runner split can enqueue and process an operation in a disposable project.
- Confirmed the current baseline test suite still has global `--project-dir`/registered-project resolution failures reported by the prior scan; see baseline pytest entry below.

## Cleanup performed
- Ran `docker compose down -v --remove-orphans` for both disposable compose projects.
- Verified `docker ps`, `docker volume ls`, and `docker network ls` filters for `odooctl-r3` returned empty at cleanup time.
- Stopped API server subprocesses after API checks.

## Recommended follow-up
1. Fix global `--project-dir`/registered project context propagation before release; it affects env/promote and user-facing ctl paths.
2. Add an opt-in integration test harness that mirrors this report with disposable `odoo:<version>` and docker-mode Postgres/filestore operations.
3. Keep Docker-native DB execution as a first-class path, since host Postgres clients are not guaranteed on operator machines.
4. Investigate any non-zero command entries below before claiming Odoo 18/19 parity.

## Exact command log

### precheck: git/docker/compose/pg clients
- cwd: `/home/dev/odooctl`
- exit: `0`
- duration: `0.07` seconds

```bash
git status --short && git rev-parse HEAD && docker --version && docker compose version && (command -v pg_dump || true) && (command -v psql || true)
```

```text
?? experiments/2026-05-31-kanban-scan-suite/report-3-odoo18-19-full-api-ctl-experiment.md
?? experiments/2026-05-31-kanban-scan-suite/run_report3_experiment.py
97a487a2a22459bdeff1e28d532c2e359f4ea68a
Docker version 29.5.2, build 79eb04c
Docker Compose version v5.1.4
```

### precheck: image manifests
- cwd: `/home/dev/odooctl`
- exit: `0`
- duration: `35.87` seconds

```bash
docker manifest inspect odoo:18.0 >/dev/null && docker manifest inspect odoo:19.0 >/dev/null && echo manifests-ok
```

```text
manifests-ok
```

### baseline: full pytest
- cwd: `/home/dev/odooctl`
- exit: `1`
- duration: `8.3` seconds

```bash
python -m pytest -q
```

```text
da cwd=None: "abc")
        monkeypatch.setattr(svc, "MetadataStore", lambda root: DummyMetaStore())
    
        runner = CliRunner()
        result = runner.invoke(
            app, ["--project-dir", str(tmp_path), "promote", "staging", "production", "--yes"]
        )
>       assert result.exit_code == 0, result.output
E       AssertionError: 
E       assert 1 == 0
E        +  where 1 = <Result ClickException('Config file not found: /home/dev/odooctl/odooctl.yml')>.exit_code

tests/test_promote.py:556: AssertionError
________ test_global_project_option_resolves_registered_project_config _________

tmp_path = PosixPath('/tmp/pytest-of-dev/pytest-464/test_global_project_option_res0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x788dc1143510>

    def test_global_project_option_resolves_registered_project_config(tmp_path: Path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_config(repo, "acme")
        add_project("acme", repo)
    
        result = runner.invoke(app, ["--project", "acme", "validate"])
    
>       assert result.exit_code == 0, result.output
E       AssertionError: Usage: root validate [OPTIONS]
E         Try 'root validate --help' for help.
E         ╭─ Error ──────────────────────────────────────────────────────────────────────╮
E         │ Invalid value: Config file not found: /home/dev/odooctl/odooctl.yml          │
E         ╰──────────────────────────────────────────────────────────────────────────────╯
E         
E       assert 2 == 0
E        +  where 2 = <Result SystemExit(2)>.exit_code

tests/test_registry.py:74: AssertionError
_________ test_project_dir_option_resolves_config_from_non_project_cwd _________

tmp_path = PosixPath('/tmp/pytest-of-dev/pytest-464/test_project_dir_option_resolv0')

    def test_project_dir_option_resolves_config_from_non_project_cwd(tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_config(repo, "local")
    
        result = runner.invoke(app, ["--project-dir", str(repo), "validate"])
    
>       assert result.exit_code == 0, result.output
E       AssertionError: Usage: root validate [OPTIONS]
E         Try 'root validate --help' for help.
E         ╭─ Error ──────────────────────────────────────────────────────────────────────╮
E         │ Invalid value: Config file not found: /home/dev/odooctl/odooctl.yml          │
E         ╰──────────────────────────────────────────────────────────────────────────────╯
E         
E       assert 2 == 0
E        +  where 2 = <Result SystemExit(2)>.exit_code

tests/test_registry.py:85: AssertionError
=========================== short test summary info ============================
FAILED tests/test_env_cmd.py::test_env_list_and_show_json - AssertionError: 
FAILED tests/test_env_cmd.py::test_env_create_writes_valid_config_and_provisions_with_clone
FAILED tests/test_env_cmd.py::test_env_create_can_skip_provision - AssertionE...
FAILED tests/test_env_cmd.py::test_env_destroy_refuses_production_and_removes_non_production
FAILED tests/test_env_cmd.py::test_env_destroy_purge_drops_db_and_filestore_before_removing_config
FAILED tests/test_env_cmd.py::test_env_open_refuses_reserved_name_production
FAILED tests/test_env_cmd.py::test_env_open_refuses_reserved_name_staging - A...
FAILED tests/test_env_cmd.py::test_env_open_refuses_duplicate_environment - A...
FAILED tests/test_env_cmd.py::test_env_open_no_provision_writes_config_without_clone
FAILED tests/test_env_cmd.py::test_env_open_with_provision_clones_sanitized_from_source
FAILED tests/test_promote.py::test_cli_promote_requires_yes_for_protected_target
FAILED tests/test_promote.py::test_cli_promote_yes_flag_bypasses_protection
FAILED tests/test_registry.py::test_global_project_option_resolves_registered_project_config
FAILED tests/test_registry.py::test_project_dir_option_resolves_config_from_non_project_cwd
14 failed, 709 passed in 7.52s
```

### Odoo 18.0: compose pull
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `3.79` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml pull
```

```text
Image odoo:18.0 Pulling 
 Image postgres:16 Pulling 
 Image odoo:18.0 Pulled 
 Image postgres:16 Pulled
```

### Odoo 18.0: compose up
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `6.22` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml up -d
```

```text
Network odooctl-r3-180_default Creating 
 Network odooctl-r3-180_default Created 
 Volume odooctl-r3-180_db_data Creating 
 Volume odooctl-r3-180_db_data Created 
 Volume odooctl-r3-180_odoo_data Creating 
 Volume odooctl-r3-180_odoo_data Created 
 Container odooctl-r3-180-postgres-1 Creating 
 Container odooctl-r3-180-postgres-1 Created 
 Container odooctl-r3-180-odoo-1 Creating 
 Container odooctl-r3-180-odoo-1 Created 
 Container odooctl-r3-180-postgres-1 Starting 
 Container odooctl-r3-180-postgres-1 Started 
 Container odooctl-r3-180-postgres-1 Waiting 
 Container odooctl-r3-180-postgres-1 Healthy 
 Container odooctl-r3-180-odoo-1 Starting 
 Container odooctl-r3-180-odoo-1 Started
```

### Odoo 18.0: postgres ready attempt 1/20
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.16` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml exec -T postgres pg_isready -U odoo -d postgres
```

```text
/var/run/postgresql:5432 - accepting connections
```

### Odoo 18.0: HTTP /web/login ready attempt 1/40 (transient readiness probe)
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `None`
- duration: `0.01` seconds

```bash
curl -fsS -o /tmp/odooctl-r3-180-login.html -w "%{http_code}" http://127.0.0.1:18018/web/login | grep -E "^(200|303|302)$"
```

```text
curl: (56) Recv failure: Connection reset by peer
```

### Odoo 18.0: HTTP /web/login ready attempt 2/40
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.06` seconds

```bash
curl -fsS -o /tmp/odooctl-r3-180-login.html -w "%{http_code}" http://127.0.0.1:18018/web/login | grep -E "^(200|303|302)$"
```

```text
303
```

### Odoo 18.0: image version command
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.81` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml exec -T odoo odoo --version
```

```text
Odoo Server 18.0-20260528
```

### Odoo 18.0: initialize production DB with base
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `17.63` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml exec -T odoo odoo -d odoo180_prod -i base --without-demo=all --stop-after-init --db_host=postgres --db_user=odoo --db_password="$ODOO_DB_PASSWORD"
```

```text
80_prod odoo.modules.loading: Loading module web_tour (8/12) 
2026-06-01 09:44:36,765 29 INFO odoo180_prod odoo.modules.registry: module web_tour: creating or updating database tables 
2026-06-01 09:44:36,771 29 INFO odoo180_prod odoo.models: Prepare computation of res.users.tour_enabled 
2026-06-01 09:44:36,885 29 INFO odoo180_prod odoo.modules.loading: loading web_tour/security/ir.model.access.csv 
2026-06-01 09:44:36,901 29 INFO odoo180_prod odoo.modules.loading: loading web_tour/views/tour_views.xml 
2026-06-01 09:44:36,933 29 INFO odoo180_prod odoo.modules.loading: loading web_tour/views/res_users_views.xml 
2026-06-01 09:44:36,965 29 INFO odoo180_prod odoo.modules.loading: Module web_tour loaded in 0.23s, 188 queries (+188 other) 
2026-06-01 09:44:36,965 29 INFO odoo180_prod odoo.modules.loading: Loading module html_editor (9/12) 
2026-06-01 09:44:37,117 29 INFO odoo180_prod odoo.modules.registry: module html_editor: creating or updating database tables 
2026-06-01 09:44:37,165 29 INFO odoo180_prod odoo.modules.loading: Module html_editor loaded in 0.20s, 46 queries (+46 other) 
2026-06-01 09:44:37,165 29 INFO odoo180_prod odoo.modules.loading: Loading module iap (10/12) 
2026-06-01 09:44:37,190 29 INFO odoo180_prod odoo.modules.registry: module iap: creating or updating database tables 
2026-06-01 09:44:37,297 29 INFO odoo180_prod odoo.modules.loading: loading iap/data/services.xml 
2026-06-01 09:44:37,304 29 INFO odoo180_prod odoo.modules.loading: loading iap/security/ir.model.access.csv 
2026-06-01 09:44:37,318 29 INFO odoo180_prod odoo.modules.loading: loading iap/security/ir_rule.xml 
2026-06-01 09:44:37,326 29 INFO odoo180_prod odoo.modules.loading: loading iap/views/iap_views.xml 
2026-06-01 09:44:37,355 29 INFO odoo180_prod odoo.modules.loading: loading iap/views/res_config_settings.xml 
2026-06-01 09:44:37,383 29 INFO odoo180_prod odoo.modules.loading: Module iap loaded in 0.22s, 183 queries (+183 other) 
2026-06-01 09:44:37,383 29 INFO odoo180_prod odoo.modules.loading: Loading module web_editor (11/12) 
2026-06-01 09:44:37,441 29 INFO odoo180_prod odoo.modules.registry: module web_editor: creating or updating database tables 
2026-06-01 09:44:38,314 29 INFO odoo180_prod odoo.modules.loading: loading web_editor/security/ir.model.access.csv 
2026-06-01 09:44:38,328 29 INFO odoo180_prod odoo.modules.loading: loading web_editor/data/editor_assets.xml 
2026-06-01 09:44:38,334 29 INFO odoo180_prod odoo.modules.loading: loading web_editor/views/editor.xml 
2026-06-01 09:44:38,350 29 INFO odoo180_prod odoo.modules.loading: loading web_editor/views/snippets.xml 
2026-06-01 09:44:38,407 29 INFO odoo180_prod odoo.modules.loading: Module web_editor loaded in 1.02s, 1015 queries (+1015 other) 
2026-06-01 09:44:38,407 29 INFO odoo180_prod odoo.modules.loading: Loading module web_unsplash (12/12) 
2026-06-01 09:44:38,436 29 INFO odoo180_prod odoo.modules.registry: module web_unsplash: creating or updating database tables 
2026-06-01 09:44:38,491 29 INFO odoo180_prod odoo.modules.loading: loading web_unsplash/views/res_config_settings_view.xml 
2026-06-01 09:44:38,525 29 INFO odoo180_prod odoo.modules.loading: Module web_unsplash loaded in 0.12s, 89 queries (+89 other) 
2026-06-01 09:44:38,525 29 INFO odoo180_prod odoo.modules.loading: 12 modules loaded in 4.61s, 4180 queries (+4180 extra) 
2026-06-01 09:44:38,836 29 INFO odoo180_prod odoo.modules.loading: Modules loaded. 
2026-06-01 09:44:38,842 29 INFO odoo180_prod odoo.modules.registry: Registry changed, signaling through the database 
2026-06-01 09:44:38,843 29 INFO odoo180_prod odoo.modules.registry: Registry loaded in 16.251s 
2026-06-01 09:44:38,843 29 INFO odoo180_prod odoo.service.server: Initiating shutdown 
2026-06-01 09:44:38,843 29 INFO odoo180_prod odoo.service.server: Hit CTRL-C again or send a second signal to force the shutdown. 
2026-06-01 09:44:38,843 29 INFO odoo180_prod odoo.sql_db: ConnectionPool(read/write;used=0/count=0/max=64): Closed 1 connections
```

### Odoo 18.0: create filestore marker
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.12` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml exec -T odoo sh -lc "mkdir -p /var/lib/odoo/filestore/odoo180_prod && printf marker-180 > /var/lib/odoo/filestore/odoo180_prod/odooctl-marker.txt"
```

```text

```

### Odoo 18.0: validate config
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.38` seconds

```bash
uv run odooctl validate
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
✓ Config valid: odooctl-report3-odoo180 (production, staging)
✓ All referenced environment variables are set
```

### Odoo 18.0: doctor json
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.37` seconds

```bash
uv run odooctl doctor --json
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
{
  "checks": [
    {
      "message": "config loaded: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/odooctl.yml",
      "name": "config",
      "ok": true
    },
    {
      "message": "project root exists: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180",
      "name": "project_root",
      "ok": true
    },
    {
      "message": "compose file exists: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml",
      "name": "compose_file",
      "ok": true
    },
    {
      "message": "all referenced environment variables are set",
      "name": "environment",
      "ok": true
    }
  ],
  "config_path": "/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/odooctl.yml",
  "ok": true,
  "project": "odooctl-report3-odoo180",
  "root": "/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180"
}
```

### Odoo 18.0: status production json
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.5` seconds

```bash
uv run odooctl status --environment production --json
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
{
  "current_git_commit": "97a487a",
  "environments": [
    {
      "branch": "main-180",
      "commit": "unknown",
      "health_check": "unknown",
      "health_check_url": "http://127.0.0.1:18018/web/login?db=odoo180_prod",
      "image": "odoo:18.0",
      "last_deployment": "unknown",
      "last_deployment_backup": "unknown",
      "last_deployment_message": null,
      "latest_backup": "unknown",
      "name": "production",
      "odoo": "unknown",
      "postgresql": "unknown",
      "url": "http://127.0.0.1:18018"
    }
  ],
  "project": "odooctl-report3-odoo180"
}
```

### Odoo 18.0: logs no-follow tail
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.46` seconds

```bash
uv run odooctl logs production --service odoo --no-follow --tail 20
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
odoo-1  | 2026-06-01 09:44:16,207 1 INFO ? odoo: Odoo version 18.0-20260528 
odoo-1  | 2026-06-01 09:44:16,207 1 INFO ? odoo: Using configuration file at /etc/odoo/odoo.conf 
odoo-1  | 2026-06-01 09:44:16,207 1 INFO ? odoo: addons paths: ['/usr/lib/python3/dist-packages/odoo/addons', '/var/lib/odoo/addons/18.0', '/mnt/extra-addons'] 
odoo-1  | 2026-06-01 09:44:16,207 1 INFO ? odoo: database: odoo@postgres:5432 
odoo-1  | Warn: Can't find .pfb for face 'Courier'
odoo-1  | 2026-06-01 09:44:16,384 1 INFO ? odoo.addons.base.models.ir_actions_report: Will use the Wkhtmltopdf binary at /usr/local/bin/wkhtmltopdf 
odoo-1  | 2026-06-01 09:44:16,397 1 INFO ? odoo.addons.base.models.ir_actions_report: Will use the Wkhtmltoimage binary at /usr/local/bin/wkhtmltoimage 
odoo-1  | 2026-06-01 09:44:16,663 1 INFO ? odoo.service.server: HTTP service (werkzeug) running on f0e7b1997213:8069 
odoo-1  | 2026-06-01 09:44:20,650 1 INFO ? werkzeug: 172.22.0.1 - - [01/Jun/2026 09:44:20] "GET /web/login HTTP/1.1" 303 - 2 0.004 0.042
```

### Odoo 18.0: backup production --verify
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.89` seconds

```bash
uv run odooctl backup production --verify
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
production_2026-06-01_094441
```

### Odoo 18.0: clone production staging --sanitize
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `27.64` seconds

```bash
uv run odooctl clone production staging --sanitize
```

```text
r (8/12) 
2026-06-01 09:45:01,103 67 INFO odoo180_stage odoo.modules.registry: module web_tour: creating or updating database tables 
2026-06-01 09:45:01,151 67 INFO odoo180_stage odoo.modules.loading: loading web_tour/security/ir.model.access.csv 
2026-06-01 09:45:01,163 67 INFO odoo180_stage odoo.modules.loading: loading web_tour/views/tour_views.xml 
2026-06-01 09:45:01,193 67 INFO odoo180_stage odoo.modules.loading: loading web_tour/views/res_users_views.xml 
2026-06-01 09:45:01,227 67 INFO odoo180_stage odoo.modules.loading: Module web_tour loaded in 0.17s, 160 queries (+160 other) 
2026-06-01 09:45:01,227 67 INFO odoo180_stage odoo.modules.loading: Loading module html_editor (9/12) 
2026-06-01 09:45:01,339 67 INFO odoo180_stage odoo.modules.registry: module html_editor: creating or updating database tables 
2026-06-01 09:45:01,374 67 INFO odoo180_stage odoo.modules.loading: Module html_editor loaded in 0.15s, 38 queries (+38 other) 
2026-06-01 09:45:01,374 67 INFO odoo180_stage odoo.modules.loading: Loading module iap (10/12) 
2026-06-01 09:45:01,420 67 INFO odoo180_stage odoo.modules.registry: module iap: creating or updating database tables 
2026-06-01 09:45:01,453 67 INFO odoo180_stage odoo.modules.loading: loading iap/data/services.xml 
2026-06-01 09:45:01,456 67 INFO odoo180_stage odoo.modules.loading: loading iap/security/ir.model.access.csv 
2026-06-01 09:45:01,469 67 INFO odoo180_stage odoo.modules.loading: loading iap/security/ir_rule.xml 
2026-06-01 09:45:01,471 67 INFO odoo180_stage odoo.modules.loading: loading iap/views/iap_views.xml 
2026-06-01 09:45:01,494 67 INFO odoo180_stage odoo.modules.loading: loading iap/views/res_config_settings.xml 
2026-06-01 09:45:01,527 67 INFO odoo180_stage odoo.modules.loading: Module iap loaded in 0.15s, 145 queries (+145 other) 
2026-06-01 09:45:01,527 67 INFO odoo180_stage odoo.modules.loading: Loading module web_editor (11/12) 
2026-06-01 09:45:01,598 67 INFO odoo180_stage odoo.modules.registry: module web_editor: creating or updating database tables 
2026-06-01 09:45:02,454 67 INFO odoo180_stage odoo.modules.loading: loading web_editor/security/ir.model.access.csv 
2026-06-01 09:45:02,465 67 INFO odoo180_stage odoo.modules.loading: loading web_editor/data/editor_assets.xml 
2026-06-01 09:45:02,469 67 INFO odoo180_stage odoo.modules.loading: loading web_editor/views/editor.xml 
2026-06-01 09:45:02,485 67 INFO odoo180_stage odoo.modules.loading: loading web_editor/views/snippets.xml 
2026-06-01 09:45:02,552 67 INFO odoo180_stage odoo.modules.loading: Module web_editor loaded in 1.02s, 1030 queries (+1030 other) 
2026-06-01 09:45:02,552 67 INFO odoo180_stage odoo.modules.loading: Loading module web_unsplash (12/12) 
2026-06-01 09:45:02,603 67 INFO odoo180_stage odoo.modules.registry: module web_unsplash: creating or updating database tables 
2026-06-01 09:45:02,647 67 INFO odoo180_stage odoo.modules.loading: loading web_unsplash/views/res_config_settings_view.xml 
2026-06-01 09:45:02,680 67 INFO odoo180_stage odoo.modules.loading: Module web_unsplash loaded in 0.13s, 90 queries (+90 other) 
2026-06-01 09:45:02,680 67 INFO odoo180_stage odoo.modules.loading: 12 modules loaded in 4.28s, 4186 queries (+4186 extra) 
2026-06-01 09:45:02,960 67 INFO odoo180_stage odoo.modules.loading: Modules loaded. 
2026-06-01 09:45:02,966 67 INFO odoo180_stage odoo.modules.registry: Registry changed, signaling through the database 
2026-06-01 09:45:02,967 67 INFO odoo180_stage odoo.modules.registry: Registry loaded in 10.607s 
2026-06-01 09:45:02,967 67 INFO odoo180_stage odoo.service.server: Initiating shutdown 
2026-06-01 09:45:02,967 67 INFO odoo180_stage odoo.service.server: Hit CTRL-C again or send a second signal to force the shutdown. 
2026-06-01 09:45:02,967 67 INFO odoo180_stage odoo.sql_db: ConnectionPool(read/write;used=0/count=0/max=64): Closed 1 connections  
 Container odooctl-r3-180-odoo-1 Restarting 
 Container odooctl-r3-180-odoo-1 Started 
Staging URL: http://127.0.0.1:18018
```

### Odoo 18.0: staging DB proof after clone
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.19` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml exec -T -e PGPASSWORD="$ODOO_DB_PASSWORD" postgres psql -h postgres -U odoo -d odoo180_stage -Atc "select current_database(), count(*) from ir_config_parameter;"
```

```text
odoo180_stage|10
```

### Odoo 18.0: update modules staging base
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `12.38` seconds

```bash
uv run odooctl update-modules staging --modules base
```

```text
0.24s, 155 queries (+155 other) 
2026-06-01 09:45:19,764 25 INFO odoo180_stage odoo.modules.loading: Loading module web_tour (8/12) 
2026-06-01 09:45:19,812 25 INFO odoo180_stage odoo.modules.registry: module web_tour: creating or updating database tables 
2026-06-01 09:45:19,863 25 INFO odoo180_stage odoo.modules.loading: loading web_tour/security/ir.model.access.csv 
2026-06-01 09:45:19,876 25 INFO odoo180_stage odoo.modules.loading: loading web_tour/views/tour_views.xml 
2026-06-01 09:45:19,909 25 INFO odoo180_stage odoo.modules.loading: loading web_tour/views/res_users_views.xml 
2026-06-01 09:45:19,948 25 INFO odoo180_stage odoo.modules.loading: Module web_tour loaded in 0.18s, 160 queries (+160 other) 
2026-06-01 09:45:19,949 25 INFO odoo180_stage odoo.modules.loading: Loading module html_editor (9/12) 
2026-06-01 09:45:20,061 25 INFO odoo180_stage odoo.modules.registry: module html_editor: creating or updating database tables 
2026-06-01 09:45:20,100 25 INFO odoo180_stage odoo.modules.loading: Module html_editor loaded in 0.15s, 38 queries (+38 other) 
2026-06-01 09:45:20,100 25 INFO odoo180_stage odoo.modules.loading: Loading module iap (10/12) 
2026-06-01 09:45:20,148 25 INFO odoo180_stage odoo.modules.registry: module iap: creating or updating database tables 
2026-06-01 09:45:20,182 25 INFO odoo180_stage odoo.modules.loading: loading iap/data/services.xml 
2026-06-01 09:45:20,185 25 INFO odoo180_stage odoo.modules.loading: loading iap/security/ir.model.access.csv 
2026-06-01 09:45:20,200 25 INFO odoo180_stage odoo.modules.loading: loading iap/security/ir_rule.xml 
2026-06-01 09:45:20,202 25 INFO odoo180_stage odoo.modules.loading: loading iap/views/iap_views.xml 
2026-06-01 09:45:20,229 25 INFO odoo180_stage odoo.modules.loading: loading iap/views/res_config_settings.xml 
2026-06-01 09:45:20,267 25 INFO odoo180_stage odoo.modules.loading: Module iap loaded in 0.17s, 145 queries (+145 other) 
2026-06-01 09:45:20,267 25 INFO odoo180_stage odoo.modules.loading: Loading module web_editor (11/12) 
2026-06-01 09:45:20,338 25 INFO odoo180_stage odoo.modules.registry: module web_editor: creating or updating database tables 
2026-06-01 09:45:21,190 25 INFO odoo180_stage odoo.modules.loading: loading web_editor/security/ir.model.access.csv 
2026-06-01 09:45:21,199 25 INFO odoo180_stage odoo.modules.loading: loading web_editor/data/editor_assets.xml 
2026-06-01 09:45:21,203 25 INFO odoo180_stage odoo.modules.loading: loading web_editor/views/editor.xml 
2026-06-01 09:45:21,218 25 INFO odoo180_stage odoo.modules.loading: loading web_editor/views/snippets.xml 
2026-06-01 09:45:21,277 25 INFO odoo180_stage odoo.modules.loading: Module web_editor loaded in 1.01s, 1030 queries (+1030 other) 
2026-06-01 09:45:21,277 25 INFO odoo180_stage odoo.modules.loading: Loading module web_unsplash (12/12) 
2026-06-01 09:45:21,328 25 INFO odoo180_stage odoo.modules.registry: module web_unsplash: creating or updating database tables 
2026-06-01 09:45:21,377 25 INFO odoo180_stage odoo.modules.loading: loading web_unsplash/views/res_config_settings_view.xml 
2026-06-01 09:45:21,413 25 INFO odoo180_stage odoo.modules.loading: Module web_unsplash loaded in 0.14s, 90 queries (+90 other) 
2026-06-01 09:45:21,413 25 INFO odoo180_stage odoo.modules.loading: 12 modules loaded in 4.33s, 4185 queries (+4185 extra) 
2026-06-01 09:45:21,721 25 INFO odoo180_stage odoo.modules.loading: Modules loaded. 
2026-06-01 09:45:21,724 25 INFO odoo180_stage odoo.modules.registry: Registry changed, signaling through the database 
2026-06-01 09:45:21,725 25 INFO odoo180_stage odoo.modules.registry: Registry loaded in 10.709s 
2026-06-01 09:45:21,726 25 INFO odoo180_stage odoo.service.server: Initiating shutdown 
2026-06-01 09:45:21,726 25 INFO odoo180_stage odoo.service.server: Hit CTRL-C again or send a second signal to force the shutdown. 
2026-06-01 09:45:21,726 25 INFO odoo180_stage odoo.sql_db: ConnectionPool(read/write;used=0/count=0/max=64): Closed 1 connections
```

### Odoo 18.0: restore production backup into staging
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `7.64` seconds

```bash
uv run odooctl restore production --to staging --backup latest
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
 pg_terminate_backend 
----------------------
(0 rows)

NOTICE:  database "odoo180_stage_incoming" does not exist, skipping
 pg_terminate_backend 
----------------------
(0 rows)

DROP DATABASE
ALTER DATABASE
Restored production backup production_2026-06-01_094441 into staging
```

### Odoo 18.0: import preview existing compose
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.38` seconds

```bash
uv run odooctl import docker-compose.yml --preview --name imported-180
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
• Detecting deployment from docker-compose.yml …
Import Preview
==============
Compose file  : docker-compose.yml
Odoo service  : odoo (image: odoo:18.0)
Postgres      : postgres (image: postgres:16)
HTTP port     : None
DB host       : postgres
DB user       : odoo
DB password   : <env:ODOO_DB_PASSWORD>
DB candidates : ['postgres']
Addons paths  : []
Filestore vol : odoo_data
Filestore path: /var/lib/odoo

Generated odooctl.yml:
----------------------
project:
  name: imported-180
  odoo_version: '18.0'
runtime:
  type: docker_compose
  compose_file: docker-compose.yml
postgres:
  host: postgres
  port: 5432
  user: odoo
  password_env: ODOO_DB_PASSWORD
  service: postgres
odoo:
  image: odoo:18.0
  service: odoo
backups:
  local_path: ./backups
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: postgres
    filestore_path: /var/lib/odoo/filestore/postgres
    filestore_volume: odoo_data


This is a preview. Run with --yes to adopt this config, or --name to change the project name.
SAFETY: no files have been written and no containers were touched.
```

### Odoo 18.0: setup scaffold smoke
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.37` seconds

```bash
uv run odooctl setup --yes --stack odoo-19-community --name dryrun-180 --output /tmp/odooctl-r3-180-setup.yml --force
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
✓ Scaffolded /tmp/odooctl-r3-180-setup.yml for project 'dryrun-180' (stack: 
odoo-19-community)
! Update domains, db names, filestore paths, and environment variable names in 
the generated odooctl.yml before running 'odooctl deploy'.
```

### Odoo 18.0: project add/list with isolated XDG
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.74` seconds

```bash
uv run odooctl project add odooctl-report3-odoo180 --path /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180 && uv run odooctl project list
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
Registered project odooctl-report3-odoo180: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180 (odooctl.yml)
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
                                odooctl projects                                
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Active ┃ Name                    ┃ Path                        ┃ Config      ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ *      │ odooctl-report3-odoo180 │ /home/dev/odooctl/experime… │ odooctl.yml │
└────────┴─────────────────────────┴─────────────────────────────┴─────────────┘
```

### Odoo 18.0: API server readiness
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `None` seconds

```bash
uv run odooctl serve --host 127.0.0.1 --port 18980
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
INFO:     Started server process [2946728]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:18980 (Press CTRL+C to quit)
INFO:     127.0.0.1:56898 - "GET /openapi.json HTTP/1.1" 200 OK
```

### Odoo 18.0: mint API operator token
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.37` seconds

```bash
uv run odooctl security token mint --action api --env "*" --project "*" --ttl 900 --role operator --key-env ODOOCTL_API_KEY
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
eyJhbGciOiJIUzI1NiIsInR5cCI6Im9jYXAifQ.eyJhY3QiOiJhcGkiLCJlbnYiOiIqIiwiZXhwIjoxNzgwMzA4MDMzLCJpYXQiOjE3ODAzMDcxMzMsIm5vbmNlIjoiNjA5MTdhMjU0NTkyMjk1OCIsInByb2oiOiIqIiwicm9sZXMiOlsib3BlcmF0b3IiXX0.z8Gj8i4UjEywX8Rs363WOtjZPfRtu_7YwUK39xlGLWY
```

### Odoo 18.0: API list projects
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18980/projects
```

```text
{"projects":["odooctl-report3-odoo180"]}
```

### Odoo 18.0: API project environments
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18980/projects/odooctl-report3-odoo180/environments
```

```text
{"environments":[{"name":"production","branch":"main-180","domain":"127.0.0.1","tier":"production","protected":false},{"name":"staging","branch":"staging-180","domain":"127.0.0.1","tier":"staging","protected":null}]}
```

### Odoo 18.0: API project status
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18980/projects/odooctl-report3-odoo180/status
```

```text
{"project":"odooctl-report3-odoo180","environments":[{"name":"production","last_deployment_status":"unknown","last_deployment_commit":"unknown","latest_backup":"2026-06-01T09:44:41Z"},{"name":"staging","last_deployment_status":"unknown","last_deployment_commit":"unknown","latest_backup":"unknown"}],"recent_operations":[{"op_id":"7e91b8ba50bd","kind":"restore","environment":"staging","status":"succeeded","created_at":"2026-06-01T09:45:22.342017+00:00"},{"op_id":"5b4c53bda6a0","kind":"update_modules","environment":"staging","status":"succeeded","created_at":"2026-06-01T09:45:09.963815+00:00"},{"op_id":"4bc8a49bc6f6","kind":"clone","environment":"staging","status":"succeeded","created_at":"2026-06-01T09:44:42.134788+00:00"},{"op_id":"1428c7e27281","kind":"backup","environment":"production","status":"succeeded","created_at":"2026-06-01T09:44:41.248261+00:00"}]}
```

### Odoo 18.0: API backups
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18980/projects/odooctl-report3-odoo180/backups
```

```text
{"backups":[{"schema_version":1,"backup_id":"production_2026-06-01_094441","project":"odooctl-report3-odoo180","environment":"production","timestamp":"2026-06-01T09:44:41Z","db_name":"odoo180_prod","filestore_path":"/var/lib/odoo/filestore/odoo180_prod","artifact_paths":["db.dump","filestore.tar"],"db_dump":"db.dump","filestore":"filestore.tar","git_commit":"97a487a","docker_image":"odoo:18.0","odoo_version":"18.0","backup_mode":"full","checksums":{"db_dump":"3a605e58b17d821e5e3777b7e4cc9770d0afa59f61ff61629fe736329851ae87","filestore":"0a2d6dce37c56b69babd22b61ef3ce77c5269fe2c07c33084194461fae1d250c"},"encryption":null,"status":"complete"}]}
```

### Odoo 18.0: API enqueue backup operation
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -X POST -H "Authorization: Bearer $(cat .api-token)" -H "Content-Type: application/json" --data '{"kind":"backup","environment":"staging","params":{"verify":false}}' http://127.0.0.1:18980/projects/odooctl-report3-odoo180/operations
```

```text
{"op_id":"a3908767aa0b","kind":"backup","project":"odooctl-report3-odoo180","environment":"staging","status":"queued","created_at":"2026-06-01T09:45:33.704443+00:00"}
```

### Odoo 18.0: runner once processes queued op
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.86` seconds

```bash
uv run odooctl runner --once
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
```

### Odoo 18.0: API audit
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18980/projects/odooctl-report3-odoo180/audit
```

```text
{"entries":[{"actor":"cli","action":"backup","target":"production","outcome":"succeeded","op_id":"1428c7e27281","timestamp":"2026-06-01T09:44:41.764228+00:00"},{"actor":"cli","action":"clone","target":"staging","outcome":"succeeded","op_id":"4bc8a49bc6f6","timestamp":"2026-06-01T09:45:09.402474+00:00"},{"actor":"cli","action":"update_modules","target":"staging","outcome":"succeeded","op_id":"5b4c53bda6a0","timestamp":"2026-06-01T09:45:21.968354+00:00"},{"actor":"cli","action":"restore","target":"staging","outcome":"succeeded","op_id":"7e91b8ba50bd","timestamp":"2026-06-01T09:45:29.613463+00:00"},{"actor":"api-client","action":"backup","target":"staging","outcome":"failed","op_id":"a3908767aa0b","timestamp":"2026-06-01T09:45:34.506773+00:00"}]}
```

### Odoo 19.0: compose pull
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `3.83` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml pull
```

```text
Image odoo:19.0 Pulling 
 Image postgres:16 Pulling 
 Image postgres:16 Pulled 
 Image odoo:19.0 Pulled
```

### Odoo 19.0: compose up
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `6.5` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml up -d
```

```text
Network odooctl-r3-190_default Creating 
 Network odooctl-r3-190_default Created 
 Volume odooctl-r3-190_odoo_data Creating 
 Volume odooctl-r3-190_odoo_data Created 
 Volume odooctl-r3-190_db_data Creating 
 Volume odooctl-r3-190_db_data Created 
 Container odooctl-r3-190-postgres-1 Creating 
 Container odooctl-r3-190-postgres-1 Created 
 Container odooctl-r3-190-odoo-1 Creating 
 Container odooctl-r3-190-odoo-1 Created 
 Container odooctl-r3-190-postgres-1 Starting 
 Container odooctl-r3-190-postgres-1 Started 
 Container odooctl-r3-190-postgres-1 Waiting 
 Container odooctl-r3-190-postgres-1 Healthy 
 Container odooctl-r3-190-odoo-1 Starting 
 Container odooctl-r3-190-odoo-1 Started
```

### Odoo 19.0: postgres ready attempt 1/20
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.18` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml exec -T postgres pg_isready -U odoo -d postgres
```

```text
/var/run/postgresql:5432 - accepting connections
```

### Odoo 19.0: HTTP /web/login ready attempt 1/40 (transient readiness probe)
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `None`
- duration: `0.01` seconds

```bash
curl -fsS -o /tmp/odooctl-r3-190-login.html -w "%{http_code}" http://127.0.0.1:18019/web/login | grep -E "^(200|303|302)$"
```

```text
curl: (56) Recv failure: Connection reset by peer
```

### Odoo 19.0: HTTP /web/login ready attempt 2/40
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.06` seconds

```bash
curl -fsS -o /tmp/odooctl-r3-190-login.html -w "%{http_code}" http://127.0.0.1:18019/web/login | grep -E "^(200|303|302)$"
```

```text
303
```

### Odoo 19.0: image version command
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.47` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml exec -T odoo odoo --version
```

```text
Odoo Server 19.0-20260528
```

### Odoo 19.0: initialize production DB with base
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `17.1` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml exec -T odoo odoo -d odoo190_prod -i base --without-demo=all --stop-after-init --db_host=postgres --db_user=odoo --db_password="$ODOO_DB_PASSWORD"
```

```text
putation of res.users.tour_enabled 
2026-06-01 09:46:05,796 24 INFO odoo190_prod odoo.modules.loading: loading web_tour/security/ir.model.access.csv 
2026-06-01 09:46:05,805 24 INFO odoo190_prod odoo.modules.loading: loading web_tour/views/tour_views.xml 
2026-06-01 09:46:05,859 24 INFO odoo190_prod odoo.modules.loading: Module web_tour loaded in 0.19s, 180 queries (+180 other) 
2026-06-01 09:46:05,859 24 INFO odoo190_prod odoo.modules.loading: Loading module auth_passkey (11/14) 
2026-06-01 09:46:05,904 24 INFO odoo190_prod odoo.registry: module auth_passkey: creating or updating database tables 
2026-06-01 09:46:05,990 24 INFO odoo190_prod odoo.modules.loading: loading auth_passkey/views/auth_passkey_key_views.xml 
2026-06-01 09:46:06,020 24 INFO odoo190_prod odoo.modules.loading: loading auth_passkey/views/auth_passkey_login_templates.xml 
2026-06-01 09:46:06,034 24 INFO odoo190_prod odoo.modules.loading: loading auth_passkey/views/res_users_identitycheck_views.xml 
2026-06-01 09:46:06,045 24 INFO odoo190_prod odoo.modules.loading: loading auth_passkey/views/res_users_views.xml 
2026-06-01 09:46:06,067 24 INFO odoo190_prod odoo.modules.loading: loading auth_passkey/security/ir.model.access.csv 
2026-06-01 09:46:06,077 24 INFO odoo190_prod odoo.modules.loading: loading auth_passkey/security/security.xml 
2026-06-01 09:46:06,110 24 INFO odoo190_prod odoo.modules.loading: Module auth_passkey loaded in 0.25s, 218 queries (+218 other) 
2026-06-01 09:46:06,110 24 INFO odoo190_prod odoo.modules.loading: Loading module html_editor (12/14) 
2026-06-01 09:46:06,289 24 INFO odoo190_prod odoo.registry: module html_editor: creating or updating database tables 
2026-06-01 09:46:06,923 24 INFO odoo190_prod odoo.modules.loading: loading html_editor/security/ir.model.access.csv 
2026-06-01 09:46:06,946 24 INFO odoo190_prod odoo.modules.loading: Module html_editor loaded in 0.84s, 1034 queries (+1034 other) 
2026-06-01 09:46:06,946 24 INFO odoo190_prod odoo.modules.loading: Loading module iap (13/14) 
2026-06-01 09:46:06,950 24 INFO odoo190_prod odoo.registry: module iap: creating or updating database tables 
2026-06-01 09:46:07,054 24 INFO odoo190_prod odoo.modules.loading: loading iap/data/services.xml 
2026-06-01 09:46:07,060 24 INFO odoo190_prod odoo.modules.loading: loading iap/security/ir.model.access.csv 
2026-06-01 09:46:07,069 24 INFO odoo190_prod odoo.modules.loading: loading iap/security/ir_rule.xml 
2026-06-01 09:46:07,077 24 INFO odoo190_prod odoo.modules.loading: loading iap/views/iap_views.xml 
2026-06-01 09:46:07,109 24 INFO odoo190_prod odoo.modules.loading: loading iap/views/res_config_settings.xml 
2026-06-01 09:46:07,137 24 INFO odoo190_prod odoo.modules.loading: Module iap loaded in 0.19s, 182 queries (+182 other) 
2026-06-01 09:46:07,137 24 INFO odoo190_prod odoo.modules.loading: Loading module web_unsplash (14/14) 
2026-06-01 09:46:07,146 24 INFO odoo190_prod odoo.registry: module web_unsplash: creating or updating database tables 
2026-06-01 09:46:07,187 24 INFO odoo190_prod odoo.modules.loading: loading web_unsplash/views/res_config_settings_view.xml 
2026-06-01 09:46:07,225 24 INFO odoo190_prod odoo.modules.loading: Module web_unsplash loaded in 0.09s, 93 queries (+93 other) 
2026-06-01 09:46:07,225 24 INFO odoo190_prod odoo.modules.loading: 14 modules loaded in 3.96s, 4664 queries (+4664 extra) 
2026-06-01 09:46:07,506 24 INFO odoo190_prod odoo.modules.loading: Modules loaded. 
2026-06-01 09:46:07,515 24 INFO odoo190_prod odoo.registry: Registry changed, signaling through the database 
2026-06-01 09:46:07,517 24 INFO odoo190_prod odoo.registry: Registry loaded in 16.096s 
2026-06-01 09:46:07,517 24 INFO odoo190_prod odoo.service.server: Initiating shutdown 
2026-06-01 09:46:07,517 24 INFO odoo190_prod odoo.service.server: Hit CTRL-C again or send a second signal to force the shutdown. 
2026-06-01 09:46:07,517 24 INFO odoo190_prod odoo.sql_db: ConnectionPool(read/write;used=0/count=0/max=64): Closed 1 connections
```

### Odoo 19.0: create filestore marker
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.13` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml exec -T odoo sh -lc "mkdir -p /var/lib/odoo/filestore/odoo190_prod && printf marker-190 > /var/lib/odoo/filestore/odoo190_prod/odooctl-marker.txt"
```

```text

```

### Odoo 19.0: validate config
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.38` seconds

```bash
uv run odooctl validate
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
✓ Config valid: odooctl-report3-odoo190 (production, staging)
✓ All referenced environment variables are set
```

### Odoo 19.0: doctor json
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.39` seconds

```bash
uv run odooctl doctor --json
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
{
  "checks": [
    {
      "message": "config loaded: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/odooctl.yml",
      "name": "config",
      "ok": true
    },
    {
      "message": "project root exists: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190",
      "name": "project_root",
      "ok": true
    },
    {
      "message": "compose file exists: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml",
      "name": "compose_file",
      "ok": true
    },
    {
      "message": "all referenced environment variables are set",
      "name": "environment",
      "ok": true
    }
  ],
  "config_path": "/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/odooctl.yml",
  "ok": true,
  "project": "odooctl-report3-odoo190",
  "root": "/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190"
}
```

### Odoo 19.0: status production json
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.46` seconds

```bash
uv run odooctl status --environment production --json
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
{
  "current_git_commit": "97a487a",
  "environments": [
    {
      "branch": "main-190",
      "commit": "unknown",
      "health_check": "unknown",
      "health_check_url": "http://127.0.0.1:18019/web/login?db=odoo190_prod",
      "image": "odoo:19.0",
      "last_deployment": "unknown",
      "last_deployment_backup": "unknown",
      "last_deployment_message": null,
      "latest_backup": "unknown",
      "name": "production",
      "odoo": "unknown",
      "postgresql": "unknown",
      "url": "http://127.0.0.1:18019"
    }
  ],
  "project": "odooctl-report3-odoo190"
}
```

### Odoo 19.0: logs no-follow tail
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.45` seconds

```bash
uv run odooctl logs production --service odoo --no-follow --tail 20
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
odoo-1  | 2026-06-01 09:45:45,345 1 WARNING ? odoo.tools.config: missing --http-interface/http_interface, using 0.0.0.0 by default, will change to 127.0.0.1 in 20.0 
odoo-1  | 2026-06-01 09:45:45,346 1 INFO ? odoo: Odoo version 19.0-20260528 
odoo-1  | 2026-06-01 09:45:45,346 1 INFO ? odoo: Using configuration file at /etc/odoo/odoo.conf 
odoo-1  | 2026-06-01 09:45:45,346 1 INFO ? odoo: addons paths: _NamespacePath(['/usr/lib/python3/dist-packages/odoo/addons', '/var/lib/odoo/addons/19.0', '/mnt/extra-addons', '/usr/lib/python3/dist-packages/addons']) 
odoo-1  | 2026-06-01 09:45:45,346 1 INFO ? odoo: database: odoo@postgres:5432 
odoo-1  | 2026-06-01 09:45:45,651 1 INFO ? odoo.service.server: HTTP service (werkzeug) running on 6c5a1e64d70a:8069 
odoo-1  | 2026-06-01 09:45:50,161 1 INFO ? werkzeug: 172.23.0.1 - - [01/Jun/2026 09:45:50] "GET /web/login HTTP/1.1" 303 - 2 0.004 0.044
```

### Odoo 19.0: backup production --verify
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.89` seconds

```bash
uv run odooctl backup production --verify
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
production_2026-06-01_094609
```

### Odoo 19.0: clone production staging --sanitize
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `27.98` seconds

```bash
uv run odooctl clone production staging --sanitize
```

```text
1 09:46:30,165 58 INFO odoo190_stage odoo.modules.loading: loading web_tour/views/tour_views.xml 
2026-06-01 09:46:30,246 58 INFO odoo190_stage odoo.modules.loading: Module web_tour loaded in 0.15s, 147 queries (+147 other) 
2026-06-01 09:46:30,247 58 INFO odoo190_stage odoo.modules.loading: Loading module auth_passkey (11/14) 
2026-06-01 09:46:30,319 58 INFO odoo190_stage odoo.registry: module auth_passkey: creating or updating database tables 
2026-06-01 09:46:30,360 58 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/auth_passkey_key_views.xml 
2026-06-01 09:46:30,393 58 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/auth_passkey_login_templates.xml 
2026-06-01 09:46:30,422 58 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/res_users_identitycheck_views.xml 
2026-06-01 09:46:30,445 58 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/res_users_views.xml 
2026-06-01 09:46:30,490 58 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/security/ir.model.access.csv 
2026-06-01 09:46:30,501 58 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/security/security.xml 
2026-06-01 09:46:30,517 58 INFO odoo190_stage odoo.modules.loading: Module auth_passkey loaded in 0.27s, 218 queries (+218 other) 
2026-06-01 09:46:30,517 58 INFO odoo190_stage odoo.modules.loading: Loading module html_editor (12/14) 
2026-06-01 09:46:30,792 58 INFO odoo190_stage odoo.registry: module html_editor: creating or updating database tables 
2026-06-01 09:46:31,336 58 INFO odoo190_stage odoo.modules.loading: loading html_editor/security/ir.model.access.csv 
2026-06-01 09:46:31,355 58 INFO odoo190_stage odoo.modules.loading: Module html_editor loaded in 0.84s, 1003 queries (+1003 other) 
2026-06-01 09:46:31,355 58 INFO odoo190_stage odoo.modules.loading: Loading module iap (13/14) 
2026-06-01 09:46:31,361 58 INFO odoo190_stage odoo.registry: module iap: creating or updating database tables 
2026-06-01 09:46:31,389 58 INFO odoo190_stage odoo.modules.loading: loading iap/data/services.xml 
2026-06-01 09:46:31,392 58 INFO odoo190_stage odoo.modules.loading: loading iap/security/ir.model.access.csv 
2026-06-01 09:46:31,401 58 INFO odoo190_stage odoo.modules.loading: loading iap/security/ir_rule.xml 
2026-06-01 09:46:31,403 58 INFO odoo190_stage odoo.modules.loading: loading iap/views/iap_views.xml 
2026-06-01 09:46:31,432 58 INFO odoo190_stage odoo.modules.loading: loading iap/views/res_config_settings.xml 
2026-06-01 09:46:31,503 58 INFO odoo190_stage odoo.modules.loading: Module iap loaded in 0.15s, 157 queries (+157 other) 
2026-06-01 09:46:31,503 58 INFO odoo190_stage odoo.modules.loading: Loading module web_unsplash (14/14) 
2026-06-01 09:46:31,517 58 INFO odoo190_stage odoo.registry: module web_unsplash: creating or updating database tables 
2026-06-01 09:46:31,550 58 INFO odoo190_stage odoo.modules.loading: loading web_unsplash/views/res_config_settings_view.xml 
2026-06-01 09:46:31,594 58 INFO odoo190_stage odoo.modules.loading: Module web_unsplash loaded in 0.09s, 102 queries (+102 other) 
2026-06-01 09:46:31,594 58 INFO odoo190_stage odoo.modules.loading: 14 modules loaded in 4.04s, 4743 queries (+4743 extra) 
2026-06-01 09:46:31,843 58 INFO odoo190_stage odoo.modules.loading: Modules loaded. 
2026-06-01 09:46:31,877 58 INFO odoo190_stage odoo.registry: Registry changed, signaling through the database 
2026-06-01 09:46:31,880 58 INFO odoo190_stage odoo.registry: Registry loaded in 10.817s 
2026-06-01 09:46:31,880 58 INFO odoo190_stage odoo.service.server: Initiating shutdown 
2026-06-01 09:46:31,880 58 INFO odoo190_stage odoo.service.server: Hit CTRL-C again or send a second signal to force the shutdown. 
2026-06-01 09:46:31,880 58 INFO odoo190_stage odoo.sql_db: ConnectionPool(read/write;used=0/count=0/max=64): Closed 1 connections  
 Container odooctl-r3-190-odoo-1 Restarting 
 Container odooctl-r3-190-odoo-1 Started 
Staging URL: http://127.0.0.1:18019
```

### Odoo 19.0: staging DB proof after clone
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.16` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml exec -T -e PGPASSWORD="$ODOO_DB_PASSWORD" postgres psql -h postgres -U odoo -d odoo190_stage -Atc "select current_database(), count(*) from ir_config_parameter;"
```

```text
odoo190_stage|9
```

### Odoo 19.0: update modules staging base
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `11.69` seconds

```bash
uv run odooctl update-modules staging --modules base
```

```text
026-06-01 09:46:48,424 22 INFO odoo190_stage odoo.modules.loading: loading web_tour/security/ir.model.access.csv 
2026-06-01 09:46:48,434 22 INFO odoo190_stage odoo.modules.loading: loading web_tour/views/tour_views.xml 
2026-06-01 09:46:48,492 22 INFO odoo190_stage odoo.modules.loading: Module web_tour loaded in 0.12s, 147 queries (+147 other) 
2026-06-01 09:46:48,492 22 INFO odoo190_stage odoo.modules.loading: Loading module auth_passkey (11/14) 
2026-06-01 09:46:48,536 22 INFO odoo190_stage odoo.registry: module auth_passkey: creating or updating database tables 
2026-06-01 09:46:48,578 22 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/auth_passkey_key_views.xml 
2026-06-01 09:46:48,605 22 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/auth_passkey_login_templates.xml 
2026-06-01 09:46:48,628 22 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/res_users_identitycheck_views.xml 
2026-06-01 09:46:48,648 22 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/views/res_users_views.xml 
2026-06-01 09:46:48,687 22 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/security/ir.model.access.csv 
2026-06-01 09:46:48,697 22 INFO odoo190_stage odoo.modules.loading: loading auth_passkey/security/security.xml 
2026-06-01 09:46:48,714 22 INFO odoo190_stage odoo.modules.loading: Module auth_passkey loaded in 0.22s, 218 queries (+218 other) 
2026-06-01 09:46:48,714 22 INFO odoo190_stage odoo.modules.loading: Loading module html_editor (12/14) 
2026-06-01 09:46:48,896 22 INFO odoo190_stage odoo.registry: module html_editor: creating or updating database tables 
2026-06-01 09:46:49,473 22 INFO odoo190_stage odoo.modules.loading: loading html_editor/security/ir.model.access.csv 
2026-06-01 09:46:49,492 22 INFO odoo190_stage odoo.modules.loading: Module html_editor loaded in 0.78s, 1003 queries (+1003 other) 
2026-06-01 09:46:49,492 22 INFO odoo190_stage odoo.modules.loading: Loading module iap (13/14) 
2026-06-01 09:46:49,497 22 INFO odoo190_stage odoo.registry: module iap: creating or updating database tables 
2026-06-01 09:46:49,525 22 INFO odoo190_stage odoo.modules.loading: loading iap/data/services.xml 
2026-06-01 09:46:49,528 22 INFO odoo190_stage odoo.modules.loading: loading iap/security/ir.model.access.csv 
2026-06-01 09:46:49,537 22 INFO odoo190_stage odoo.modules.loading: loading iap/security/ir_rule.xml 
2026-06-01 09:46:49,539 22 INFO odoo190_stage odoo.modules.loading: loading iap/views/iap_views.xml 
2026-06-01 09:46:49,566 22 INFO odoo190_stage odoo.modules.loading: loading iap/views/res_config_settings.xml 
2026-06-01 09:46:49,611 22 INFO odoo190_stage odoo.modules.loading: Module iap loaded in 0.12s, 157 queries (+157 other) 
2026-06-01 09:46:49,612 22 INFO odoo190_stage odoo.modules.loading: Loading module web_unsplash (14/14) 
2026-06-01 09:46:49,622 22 INFO odoo190_stage odoo.registry: module web_unsplash: creating or updating database tables 
2026-06-01 09:46:49,656 22 INFO odoo190_stage odoo.modules.loading: loading web_unsplash/views/res_config_settings_view.xml 
2026-06-01 09:46:49,700 22 INFO odoo190_stage odoo.modules.loading: Module web_unsplash loaded in 0.09s, 102 queries (+102 other) 
2026-06-01 09:46:49,700 22 INFO odoo190_stage odoo.modules.loading: 14 modules loaded in 3.60s, 4743 queries (+4743 extra) 
2026-06-01 09:46:49,980 22 INFO odoo190_stage odoo.modules.loading: Modules loaded. 
2026-06-01 09:46:49,990 22 INFO odoo190_stage odoo.registry: Registry changed, signaling through the database 
2026-06-01 09:46:49,992 22 INFO odoo190_stage odoo.registry: Registry loaded in 10.381s 
2026-06-01 09:46:49,992 22 INFO odoo190_stage odoo.service.server: Initiating shutdown 
2026-06-01 09:46:49,992 22 INFO odoo190_stage odoo.service.server: Hit CTRL-C again or send a second signal to force the shutdown. 
2026-06-01 09:46:49,992 22 INFO odoo190_stage odoo.sql_db: ConnectionPool(read/write;used=0/count=0/max=64): Closed 1 connections
```

### Odoo 19.0: restore production backup into staging
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `7.58` seconds

```bash
uv run odooctl restore production --to staging --backup latest
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
 pg_terminate_backend 
----------------------
(0 rows)

NOTICE:  database "odoo190_stage_incoming" does not exist, skipping
 pg_terminate_backend 
----------------------
(0 rows)

DROP DATABASE
ALTER DATABASE
Restored production backup production_2026-06-01_094609 into staging
```

### Odoo 19.0: import preview existing compose
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.41` seconds

```bash
uv run odooctl import docker-compose.yml --preview --name imported-190
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
• Detecting deployment from docker-compose.yml …
Import Preview
==============
Compose file  : docker-compose.yml
Odoo service  : odoo (image: odoo:19.0)
Postgres      : postgres (image: postgres:16)
HTTP port     : None
DB host       : postgres
DB user       : odoo
DB password   : <env:ODOO_DB_PASSWORD>
DB candidates : ['postgres']
Addons paths  : []
Filestore vol : odoo_data
Filestore path: /var/lib/odoo

Generated odooctl.yml:
----------------------
project:
  name: imported-190
  odoo_version: '19.0'
runtime:
  type: docker_compose
  compose_file: docker-compose.yml
postgres:
  host: postgres
  port: 5432
  user: odoo
  password_env: ODOO_DB_PASSWORD
  service: postgres
odoo:
  image: odoo:19.0
  service: odoo
backups:
  local_path: ./backups
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: postgres
    filestore_path: /var/lib/odoo/filestore/postgres
    filestore_volume: odoo_data


This is a preview. Run with --yes to adopt this config, or --name to change the project name.
SAFETY: no files have been written and no containers were touched.
```

### Odoo 19.0: setup scaffold smoke
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.37` seconds

```bash
uv run odooctl setup --yes --stack odoo-19-community --name dryrun-190 --output /tmp/odooctl-r3-190-setup.yml --force
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
✓ Scaffolded /tmp/odooctl-r3-190-setup.yml for project 'dryrun-190' (stack: 
odoo-19-community)
! Update domains, db names, filestore paths, and environment variable names in 
the generated odooctl.yml before running 'odooctl deploy'.
```

### Odoo 19.0: project add/list with isolated XDG
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.75` seconds

```bash
uv run odooctl project add odooctl-report3-odoo190 --path /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190 && uv run odooctl project list
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
Registered project odooctl-report3-odoo190: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190 (odooctl.yml)
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
                                odooctl projects                                
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Active ┃ Name                    ┃ Path                        ┃ Config      ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│        │ odooctl-report3-odoo180 │ /home/dev/odooctl/experime… │ odooctl.yml │
│ *      │ odooctl-report3-odoo190 │ /home/dev/odooctl/experime… │ odooctl.yml │
└────────┴─────────────────────────┴─────────────────────────────┴─────────────┘
```

### Odoo 19.0: API server readiness
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `None` seconds

```bash
uv run odooctl serve --host 127.0.0.1 --port 18990
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
INFO:     Started server process [2950398]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:18990 (Press CTRL+C to quit)
INFO:     127.0.0.1:52054 - "GET /openapi.json HTTP/1.1" 200 OK
```

### Odoo 19.0: mint API operator token
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.38` seconds

```bash
uv run odooctl security token mint --action api --env "*" --project "*" --ttl 900 --role operator --key-env ODOOCTL_API_KEY
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
eyJhbGciOiJIUzI1NiIsInR5cCI6Im9jYXAifQ.eyJhY3QiOiJhcGkiLCJlbnYiOiIqIiwiZXhwIjoxNzgwMzA4MTIxLCJpYXQiOjE3ODAzMDcyMjEsIm5vbmNlIjoiOWE5ZjM0MGRiNDMzMDFiYyIsInByb2oiOiIqIiwicm9sZXMiOlsib3BlcmF0b3IiXX0.39OvQfj8-NtpzKQYdPdktIb7UG9ETw1t-fVcypsZCiA
```

### Odoo 19.0: API list projects
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18990/projects
```

```text
{"projects":["odooctl-report3-odoo180","odooctl-report3-odoo190"]}
```

### Odoo 19.0: API project environments
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18990/projects/odooctl-report3-odoo190/environments
```

```text
{"environments":[{"name":"production","branch":"main-190","domain":"127.0.0.1","tier":"production","protected":false},{"name":"staging","branch":"staging-190","domain":"127.0.0.1","tier":"staging","protected":null}]}
```

### Odoo 19.0: API project status
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18990/projects/odooctl-report3-odoo190/status
```

```text
{"project":"odooctl-report3-odoo190","environments":[{"name":"production","last_deployment_status":"unknown","last_deployment_commit":"unknown","latest_backup":"2026-06-01T09:46:10Z"},{"name":"staging","last_deployment_status":"unknown","last_deployment_commit":"unknown","latest_backup":"unknown"}],"recent_operations":[{"op_id":"d893f7347a16","kind":"restore","environment":"staging","status":"succeeded","created_at":"2026-06-01T09:46:50.609806+00:00"},{"op_id":"f281d0863049","kind":"update_modules","environment":"staging","status":"succeeded","created_at":"2026-06-01T09:46:38.894016+00:00"},{"op_id":"b3509d526436","kind":"clone","environment":"staging","status":"succeeded","created_at":"2026-06-01T09:46:10.767137+00:00"},{"op_id":"a8ba1949e3ee","kind":"backup","environment":"production","status":"succeeded","created_at":"2026-06-01T09:46:09.891965+00:00"}]}
```

### Odoo 19.0: API backups
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18990/projects/odooctl-report3-odoo190/backups
```

```text
{"backups":[{"schema_version":1,"backup_id":"production_2026-06-01_094609","project":"odooctl-report3-odoo190","environment":"production","timestamp":"2026-06-01T09:46:10Z","db_name":"odoo190_prod","filestore_path":"/var/lib/odoo/filestore/odoo190_prod","artifact_paths":["db.dump","filestore.tar"],"db_dump":"db.dump","filestore":"filestore.tar","git_commit":"97a487a","docker_image":"odoo:19.0","odoo_version":"19.0","backup_mode":"full","checksums":{"db_dump":"1d9e7ab5beabd48ac1b1257dc8c0c3bdb7c837ccb610598b049d20196f5bee38","filestore":"9ca64a3c4c5bb11267f3fe8e8583b8c181e74d6ec3ac2938aa335e145b2f9529"},"encryption":null,"status":"complete"}]}
```

### Odoo 19.0: API enqueue backup operation
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -X POST -H "Authorization: Bearer $(cat .api-token)" -H "Content-Type: application/json" --data '{"kind":"backup","environment":"staging","params":{"verify":false}}' http://127.0.0.1:18990/projects/odooctl-report3-odoo190/operations
```

```text
{"op_id":"d86d2de6e77e","kind":"backup","project":"odooctl-report3-odoo190","environment":"staging","status":"queued","created_at":"2026-06-01T09:47:01.901612+00:00"}
```

### Odoo 19.0: runner once processes queued op
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.9` seconds

```bash
uv run odooctl runner --once
```

```text
warning: `VIRTUAL_ENV=/home/dev/.hermes/hermes-agent/venv` does not match the project environment path `/home/dev/odooctl/.venv` and will be ignored; use `--active` to target the active environment instead
```

### Odoo 19.0: API audit
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `0.02` seconds

```bash
curl -fsS -H "Authorization: Bearer $(cat .api-token)" http://127.0.0.1:18990/projects/odooctl-report3-odoo190/audit
```

```text
{"entries":[{"actor":"cli","action":"backup","target":"production","outcome":"succeeded","op_id":"a8ba1949e3ee","timestamp":"2026-06-01T09:46:10.382232+00:00"},{"actor":"cli","action":"clone","target":"staging","outcome":"succeeded","op_id":"b3509d526436","timestamp":"2026-06-01T09:46:38.360382+00:00"},{"actor":"cli","action":"update_modules","target":"staging","outcome":"succeeded","op_id":"f281d0863049","timestamp":"2026-06-01T09:46:50.215891+00:00"},{"actor":"cli","action":"restore","target":"staging","outcome":"succeeded","op_id":"d893f7347a16","timestamp":"2026-06-01T09:46:57.799190+00:00"},{"actor":"api-client","action":"backup","target":"staging","outcome":"failed","op_id":"d86d2de6e77e","timestamp":"2026-06-01T09:47:02.748166+00:00"}]}
```

### cleanup Odoo 190: compose down -v --remove-orphans
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190`
- exit: `0`
- duration: `1.26` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo190/docker-compose.yml down -v --remove-orphans
```

```text
Container odooctl-r3-190-odoo-1 Stopping 
 Container odooctl-r3-190-odoo-1 Stopped 
 Container odooctl-r3-190-odoo-1 Removing 
 Container odooctl-r3-190-odoo-1 Removed 
 Container odooctl-r3-190-postgres-1 Stopping 
 Container odooctl-r3-190-postgres-1 Stopped 
 Container odooctl-r3-190-postgres-1 Removing 
 Container odooctl-r3-190-postgres-1 Removed 
 Volume odooctl-r3-190_odoo_data Removing 
 Network odooctl-r3-190_default Removing 
 Volume odooctl-r3-190_db_data Removing 
 Volume odooctl-r3-190_db_data Removed 
 Volume odooctl-r3-190_odoo_data Removed 
 Network odooctl-r3-190_default Removed
```

### cleanup Odoo 180: compose down -v --remove-orphans
- cwd: `/home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180`
- exit: `0`
- duration: `0.75` seconds

```bash
docker compose -f /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report3-work/odoo180/docker-compose.yml down -v --remove-orphans
```

```text
Container odooctl-r3-180-odoo-1 Stopping 
 Container odooctl-r3-180-odoo-1 Stopped 
 Container odooctl-r3-180-odoo-1 Removing 
 Container odooctl-r3-180-odoo-1 Removed 
 Container odooctl-r3-180-postgres-1 Stopping 
 Container odooctl-r3-180-postgres-1 Stopped 
 Container odooctl-r3-180-postgres-1 Removing 
 Container odooctl-r3-180-postgres-1 Removed 
 Network odooctl-r3-180_default Removing 
 Volume odooctl-r3-180_odoo_data Removing 
 Volume odooctl-r3-180_db_data Removing 
 Volume odooctl-r3-180_odoo_data Removed 
 Volume odooctl-r3-180_db_data Removed 
 Network odooctl-r3-180_default Removed
```

### cleanup: verify no report3 containers running
- cwd: `/home/dev/odooctl`
- exit: `0`
- duration: `0.02` seconds

```bash
docker ps --filter "name=odooctl-r3" --format "{{.Names}}"
```

```text

```

### cleanup: verify no report3 compose resources
- cwd: `/home/dev/odooctl`
- exit: `0`
- duration: `0.03` seconds

```bash
docker volume ls --filter "name=odooctl-r3" --format "{{.Name}}"; docker network ls --filter "name=odooctl-r3" --format "{{.Name}}"
```

```text

```
