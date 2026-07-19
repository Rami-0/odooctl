OpenAI Codex v0.144.6
--------
workdir: /home/dev/odooctl
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: low
reasoning summaries: none
session id: 019f7be6-1f29-7c43-8911-bf3f0bb715ff
--------
user
You are doing an adversarial security re-scan of the odooctl codebase (a CLI/API control plane for self-hosted Odoo on Docker Compose). A prior audit (2026-05-31) found these issues which have since been remediated: sh -lc command injection, literal "production" guards instead of is_protected(), DB password on argv, unredacted CommandError, verify-before-destroy restore, Traefik Host() injection, capability-token TTL, unbounded nonce store, unkeyed audit chain, path traversal in backup ids / registry / import output, RBAC cancel gated by read action, healthcheck following redirects.

Your job: verify the remediations actually hold AND find NEW issues. Focus on:
1. odooctl/utils/shell.py (run, run_pipe, redact, CommandError) — any remaining shell injection or secret leak on argv/error paths?
2. odooctl/adapters/ (db.py, filestore.py, docker_compose.py) — command construction.
3. odooctl/security/ (tokens.py, rbac.py, audit.py, secrets.py) — token verification, nonce replay, audit chain keying, RBAC bypass.
4. odooctl/api/ (auth.py, routes_operations.py) — authz, project scoping, key strength floor.
5. odooctl/services/ (restore.py, deploy.py, clone.py) — destructive DB lifecycle, rollback safety.
6. odooctl/config.py validators — can any injection value pass the identifier/hostname validators?
7. odooctl/registry.py, commands/import_cmd.py, migration/rehearse.py — path containment.

Read the actual code. For each finding, give: file:line, severity (HIGH/MED/LOW), a concrete exploit/failure scenario, and a suggested fix. Be precise and skeptical. If a claimed remediation is incomplete or bypassable, that is a HIGH-value finding. Output a concise numbered list. Do not modify any files.

codex
I’ll inspect the requested surfaces and trace the remediations through their call sites. I’ll keep this read-only and distinguish exploitable issues from hardening observations.
exec
/bin/bash -lc 'pwd && rg --files odooctl | sort && find .. -name AGENTS.md -print' in /home/dev/odooctl
exec
/bin/bash -lc 'nl -ba odooctl/utils/shell.py; nl -ba odooctl/adapters/db.py; nl -ba odooctl/adapters/filestore.py; nl -ba odooctl/adapters/docker_compose.py' in /home/dev/odooctl
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	import os
     4	import subprocess
     5	from dataclasses import dataclass
     6	from pathlib import Path
     7	from typing import Iterable, Mapping, Sequence
     8	
     9	SENSITIVE_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "KEY", "PASSWD")
    10	DEFAULT_REDACTION_MIN_SECRET_LENGTH = 6
    11	DEFAULT_REDACTION_IGNORE_VALUES = frozenset({"odoo", "admin", "postgres", "password", "secret", "changeme"})
    12	
    13	@dataclass(slots=True)
    14	class CommandResult:
    15	    args: list[str]
    16	    returncode: int
    17	    stdout: str
    18	    stderr: str
    19	
    20	class CommandError(RuntimeError):
    21	    def __init__(self, result: CommandResult):
    22	        message = f"Command failed ({result.returncode}): {' '.join(result.args)}\n{result.stderr}"
    23	        super().__init__(redact(message))
    24	        self.result = result
    25	
    26	def redact(
    27	    text: str,
    28	    env: Mapping[str, str] | None = None,
    29	    *,
    30	    min_secret_length: int = DEFAULT_REDACTION_MIN_SECRET_LENGTH,
    31	    ignore_values: Iterable[str] = DEFAULT_REDACTION_IGNORE_VALUES,
    32	) -> str:
    33	    env = env or os.environ
    34	    ignored = {value for value in ignore_values if value}
    35	    redacted = text
    36	    for key, value in env.items():
    37	        if not value or not any(marker in key.upper() for marker in SENSITIVE_MARKERS):
    38	            continue
    39	        if len(value) < min_secret_length or value in ignored:
    40	            continue
    41	        redacted = redacted.replace(value, "***REDACTED***")
    42	    return redacted
    43	
    44	def run(args: Sequence[str], *, check: bool = True, cwd: str | None = None, env: Mapping[str, str] | None = None, stream: bool = False) -> CommandResult:
    45	    merged_env = os.environ.copy()
    46	    if env:
    47	        merged_env.update(env)
    48	    if stream:
    49	        proc = subprocess.Popen(list(args), cwd=cwd, env=merged_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    50	        output = []
    51	        assert proc.stdout is not None
    52	        for line in proc.stdout:
    53	            clean = redact(line, merged_env)
    54	            print(clean, end="")
    55	            output.append(clean)
    56	        rc = proc.wait()
    57	        result = CommandResult(list(args), rc, "".join(output), "")
    58	    else:
    59	        proc = subprocess.run(list(args), cwd=cwd, env=merged_env, text=True, capture_output=True)
    60	        result = CommandResult(list(args), proc.returncode, redact(proc.stdout, merged_env), redact(proc.stderr, merged_env))
    61	    if check and result.returncode != 0:
    62	        raise CommandError(result)
    63	    return result
    64	
    65	def _merged_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    66	    merged_env = os.environ.copy()
    67	    if env:
    68	        merged_env.update(env)
    69	    return merged_env
    70	
    71	
    72	def run_capture_bytes(
    73	    args: Sequence[str],
    74	    *,
    75	    cwd: str | None = None,
    76	    env: Mapping[str, str] | None = None,
    77	    stdout_path: str | Path,
    78	    check: bool = True,
    79	) -> CommandResult:
    80	    """Run a command and write raw stdout bytes to a file.
    81	
    82	    This is binary-safe for PostgreSQL custom-format dumps: stdout never passes
    83	    through Python text decoding or redaction.
    84	    """
    85	    merged_env = _merged_env(env)
    86	    output_path = Path(stdout_path)
    87	    output_path.parent.mkdir(parents=True, exist_ok=True)
    88	    with output_path.open("wb") as stdout:
    89	        proc = subprocess.run(list(args), cwd=cwd, env=merged_env, stdout=stdout, stderr=subprocess.PIPE)
    90	    stderr = redact(proc.stderr.decode(errors="replace"), merged_env)
    91	    result = CommandResult(list(args), proc.returncode, str(output_path), stderr)
    92	    if check and result.returncode != 0:
    93	        raise CommandError(result)
    94	    return result
    95	
    96	
    97	def run_pipe_stdin(
    98	    args: Sequence[str],
    99	    *,
   100	    cwd: str | None = None,
   101	    env: Mapping[str, str] | None = None,
   102	    stdin_path: str | Path,
   103	    check: bool = True,
   104	) -> CommandResult:
   105	    """Run a command with raw bytes from a file connected to stdin."""
   106	    merged_env = _merged_env(env)
   107	    with Path(stdin_path).open("rb") as stdin:
   108	        proc = subprocess.run(list(args), cwd=cwd, env=merged_env, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   109	    stdout = redact(proc.stdout.decode(errors="replace"), merged_env)
   110	    stderr = redact(proc.stderr.decode(errors="replace"), merged_env)
   111	    result = CommandResult(list(args), proc.returncode, stdout, stderr)
   112	    if check and result.returncode != 0:
   113	        raise CommandError(result)
   114	    return result
   115	
   116	
   117	def run_pipe(
   118	    producer: Sequence[str],
   119	    consumer: Sequence[str],
   120	    *,
   121	    cwd: str | None = None,
   122	    env: Mapping[str, str] | None = None,
   123	    check: bool = True,
   124	) -> CommandResult:
   125	    """Pipe producer stdout into consumer stdin without invoking a shell.
   126	
   127	    Replaces ``sh -c "producer | consumer"`` so that no operand is ever
   128	    shell-interpreted. The byte stream never passes through Python text
   129	    decoding, keeping it safe for PostgreSQL custom-format dumps.
   130	    """
   131	    merged_env = _merged_env(env)
   132	    producer_proc = subprocess.Popen(
   133	        list(producer), cwd=cwd, env=merged_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
   134	    )
   135	    assert producer_proc.stdout is not None
   136	    consumer_proc = subprocess.Popen(
   137	        list(consumer),
   138	        cwd=cwd,
   139	        env=merged_env,
   140	        stdin=producer_proc.stdout,
   141	        stdout=subprocess.PIPE,
   142	        stderr=subprocess.PIPE,
   143	    )
   144	    # Close our handle so the producer receives SIGPIPE if the consumer exits.
   145	    producer_proc.stdout.close()
   146	    consumer_stdout, consumer_stderr = consumer_proc.communicate()
   147	    producer_stderr = producer_proc.stderr.read() if producer_proc.stderr else b""
   148	    producer_rc = producer_proc.wait()
   149	    display_args = [*producer, "|", *consumer]
   150	    stderr = redact(
   151	        (producer_stderr + consumer_stderr).decode(errors="replace"), merged_env
   152	    )
   153	    stdout = redact(consumer_stdout.decode(errors="replace"), merged_env)
   154	    returncode = producer_rc if producer_rc != 0 else consumer_proc.returncode
   155	    result = CommandResult(list(display_args), returncode, stdout, stderr)
   156	    if check and returncode != 0:
   157	        raise CommandError(result)
   158	    return result
   159	
   160	
   161	def join_csv(values: Iterable[str]) -> str:
   162	    return ",".join(v.strip() for v in values if v and v.strip())
     1	from __future__ import annotations
     2	
     3	from pathlib import Path
     4	from typing import Protocol
     5	
     6	from odooctl.adapters.postgres import PostgresAdapter
     7	from odooctl.context import ProjectContext
     8	from odooctl.utils.shell import run
     9	
    10	
    11	class DbAdapter(Protocol):
    12	    def ping(self, db_name: str) -> None: ...
    13	    def dump(self, db_name: str, output: str | Path) -> None: ...
    14	    def restore(self, db_name: str, dump_path: str | Path) -> None: ...
    15	    def drop(self, db_name: str) -> None: ...
    16	    def drop_create(self, db_name: str) -> None: ...
    17	    def psql_file(self, db_name: str, sql_file: str | Path) -> None: ...
    18	    def psql(self, db_name: str, sql: str) -> None: ...
    19	
    20	
    21	class HostPostgresAdapter(PostgresAdapter):
    22	    """Host PostgreSQL adapter kept for backward-compatible host execution."""
    23	
    24	    def drop(self, db_name: str) -> None:
    25	        from odooctl.odoo.db_swap import drop_database, terminate_connections
    26	
    27	        terminate_connections(self, db_name)
    28	        drop_database(self, db_name)
    29	
    30	
    31	class DockerPostgresAdapter:
    32	
    33	    """PostgreSQL adapter that executes client tools inside the compose DB service."""
    34	
    35	    def __init__(self, ctx: ProjectContext):
    36	        self.ctx = ctx
    37	        self.config = ctx.config.postgres
    38	
    39	    @property
    40	    def project_dir(self) -> str:
    41	        return str(self.ctx.root)
    42	
    43	    def _cmd(self, *args: str) -> list[str]:
    44	        return [
    45	            "docker",
    46	            "compose",
    47	            "-f",
    48	            str(self.ctx.compose_file),
    49	            "exec",
    50	            "-T",
    51	            "-e",
    52	            "PGPASSWORD",
    53	            self.config.service,
    54	            *args,
    55	        ]
    56	
    57	    def _password_env(self) -> dict[str, str]:
    58	        return {"PGPASSWORD": self.config.service_password()}
    59	
    60	    def base_args(self) -> list[str]:
    61	        return ["-h", self.config.internal_host, "-U", self.config.service_user]
    62	
    63	    def ping(self, db_name: str) -> None:
    64	        run(self._cmd("pg_isready", "-d", db_name, *self.base_args()), cwd=self.project_dir, env=self._password_env())
    65	
    66	    def dump(self, db_name: str, output: str | Path) -> None:
    67	        from odooctl.utils.shell import run_capture_bytes
    68	
    69	        run_capture_bytes(
    70	            self._cmd("pg_dump", *self.base_args(), "-Fc", "-d", db_name),
    71	            cwd=self.project_dir,
    72	            env=self._password_env(),
    73	            stdout_path=output,
    74	        )
    75	
    76	    def restore(self, db_name: str, dump_path: str | Path) -> None:
    77	        from odooctl.utils.shell import run_pipe_stdin
    78	
    79	        self.drop_create(db_name)
    80	        run_pipe_stdin(
    81	            self._cmd("pg_restore", *self.base_args(), "-d", db_name),
    82	            cwd=self.project_dir,
    83	            env=self._password_env(),
    84	            stdin_path=dump_path,
    85	        )
    86	
    87	    def drop(self, db_name: str) -> None:
    88	        from odooctl.odoo.db_swap import drop_database, terminate_connections
    89	
    90	        terminate_connections(self, db_name)
    91	        drop_database(self, db_name)
    92	
    93	    def drop_create(self, db_name: str) -> None:
    94	        escaped = db_name.replace("'", "''")
    95	        terminate_sql = (
    96	            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
    97	            f"WHERE datname = '{escaped}' AND pid <> pg_backend_pid();"
    98	        )
    99	        run(
   100	            self._cmd("psql", *self.base_args(), "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", terminate_sql),
   101	            cwd=self.project_dir,
   102	            env=self._password_env(),
   103	            stream=True,
   104	        )
   105	        run(self._cmd("dropdb", *self.base_args(), db_name, "--if-exists"), cwd=self.project_dir, env=self._password_env(), stream=True)
   106	        run(self._cmd("createdb", *self.base_args(), db_name), cwd=self.project_dir, env=self._password_env(), stream=True)
   107	
   108	    def psql_file(self, db_name: str, sql_file: str | Path) -> None:
   109	        from odooctl.utils.shell import run_pipe_stdin
   110	
   111	        run_pipe_stdin(
   112	            self._cmd("psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-f", "-"),
   113	            cwd=self.project_dir,
   114	            env=self._password_env(),
   115	            stdin_path=sql_file,
   116	        )
   117	
   118	    def psql(self, db_name: str, sql: str) -> None:
   119	        run(self._cmd("psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", sql), cwd=self.project_dir, env=self._password_env(), stream=True)
   120	
   121	    def clone_db_in_container(self, src: str, dst: str) -> None:
   122	        from odooctl.utils.shell import run_pipe
   123	
   124	        self.drop_create(dst)
   125	        run_pipe(
   126	            self._cmd("pg_dump", *self.base_args(), "-Fc", "-d", src),
   127	            self._cmd("pg_restore", *self.base_args(), "-d", dst),
   128	            cwd=self.project_dir,
   129	            env=self._password_env(),
   130	        )
   131	
   132	
   133	def make_db_adapter(ctx: ProjectContext) -> DbAdapter:
   134	    if ctx.config.runtime.execution_mode == "host":
   135	        return HostPostgresAdapter(ctx.config.postgres)
   136	    return DockerPostgresAdapter(ctx)
     1	from __future__ import annotations
     2	import shutil
     3	import tempfile
     4	from pathlib import Path
     5	from typing import Protocol
     6	
     7	from odooctl.adapters.docker_compose import DockerComposeAdapter
     8	from odooctl.config import EnvironmentConfig, OdooCtlConfig
     9	from odooctl.context import ProjectContext
    10	from odooctl.utils.paths import ensure_dir
    11	from odooctl.utils.shell import run
    12	
    13	
    14	class FilestoreBackend(Protocol):
    15	    def archive(self, filestore_path: str, output: str | Path) -> None: ...
    16	    def restore_archive(self, archive_path: str | Path, target_path: str) -> None: ...
    17	    def copy(self, source: str, target: str) -> None: ...
    18	    def delete(self, filestore_path: str) -> None: ...
    19	
    20	
    21	class FilestoreAdapter:
    22	    def archive(self, filestore_path: str, output: str | Path) -> None:
    23	        source = Path(filestore_path)
    24	        if not source.exists():
    25	            raise FileNotFoundError(f"Filestore path does not exist: {filestore_path}")
    26	        ensure_dir(Path(output).parent)
    27	        run(["tar", "-cf", str(output), "-C", str(source.parent), source.name], stream=True)
    28	
    29	    def restore_archive(self, archive_path: str | Path, target_path: str) -> None:
    30	        archive = Path(archive_path)
    31	        if not archive.exists():
    32	            raise FileNotFoundError(f"Filestore archive does not exist: {archive_path}")
    33	        target = Path(target_path)
    34	        ensure_dir(target.parent)
    35	        with tempfile.TemporaryDirectory(dir=target.parent, prefix=f".{target.name}.restore-") as tmpdir:
    36	            run(["tar", "-xf", str(archive), "-C", tmpdir], stream=True)
    37	            extracted = Path(tmpdir) / target.name
    38	            if not extracted.exists():
    39	                children = list(Path(tmpdir).iterdir())
    40	                if len(children) != 1:
    41	                    raise RuntimeError(f"Archive did not contain expected filestore directory: {target.name}")
    42	                extracted = children[0]
    43	            if target.exists():
    44	                shutil.rmtree(target)
    45	            shutil.move(str(extracted), target)
    46	
    47	    def copy(self, source: str, target: str) -> None:
    48	        src = Path(source)
    49	        if not src.exists():
    50	            raise FileNotFoundError(f"Source filestore path does not exist: {source}")
    51	        dst = Path(target)
    52	        ensure_dir(dst.parent)
    53	        with tempfile.TemporaryDirectory(dir=dst.parent, prefix=f".{dst.name}.copy-") as tmpdir:
    54	            staged = Path(tmpdir) / dst.name
    55	            shutil.copytree(src, staged)
    56	            if dst.exists():
    57	                shutil.rmtree(dst)
    58	            shutil.move(str(staged), dst)
    59	
    60	    def delete(self, filestore_path: str) -> None:
    61	        path = Path(filestore_path)
    62	        if path.exists():
    63	            shutil.rmtree(path)
    64	
    65	
    66	class DockerVolumeFilestore:
    67	    """Filestore backend for Odoo filestores stored in a Docker named volume.
    68	
    69	    Odoo's official image stores filestores below ``/var/lib/odoo/filestore``.
    70	    Archive/restore stream tar bytes through ``docker compose exec -T`` so hosts do
    71	    not need a bind-mounted filestore path.
    72	    """
    73	
    74	    def __init__(self, context: ProjectContext, cfg: OdooCtlConfig):
    75	        self.compose = DockerComposeAdapter(cfg.runtime.compose_file, project_dir=str(context.root))
    76	        self.service = cfg.odoo.service
    77	        self.root = cfg.odoo.filestore_container_path.rstrip("/")
    78	
    79	    def _relative_name(self, filestore_path: str) -> str:
    80	        return Path(filestore_path).name
    81	
    82	    def _container_filestore_dir(self, filestore_path: str) -> str:
    83	        return f"{self.root}/filestore/{self._relative_name(filestore_path)}"
    84	
    85	    def archive(self, filestore_path: str, output: str | Path) -> None:
    86	        ensure_dir(Path(output).parent)
    87	        name = self._relative_name(filestore_path)
    88	        self.compose.exec_capture_bytes(
    89	            self.service,
    90	            ["tar", "-cf", "-", "-C", f"{self.root}/filestore", name],
    91	            stdout_path=output,
    92	        )
    93	
    94	    def restore_archive(self, archive_path: str | Path, target_path: str) -> None:
    95	        name = self._relative_name(target_path)
    96	        parent = f"{self.root}/filestore"
    97	        self.compose.exec(self.service, ["mkdir", "-p", parent], stream=True)
    98	        self.compose.exec(self.service, ["rm", "-rf", f"{parent}/{name}"], stream=True)
    99	        self.compose.exec_pipe_stdin(
   100	            self.service,
   101	            ["tar", "-xf", "-", "-C", parent],
   102	            stdin_path=archive_path,
   103	        )
   104	
   105	    def copy(self, source: str, target: str) -> None:
   106	        src = self._container_filestore_dir(source)
   107	        dst = self._container_filestore_dir(target)
   108	        self.compose.exec(self.service, ["mkdir", "-p", f"{self.root}/filestore"], stream=True)
   109	        self.compose.exec(self.service, ["rm", "-rf", dst], stream=True)
   110	        self.compose.exec(self.service, ["cp", "-a", src, dst], stream=True)
   111	
   112	    def delete(self, filestore_path: str) -> None:
   113	        target = self._container_filestore_dir(filestore_path)
   114	        self.compose.exec(self.service, ["rm", "-rf", target], stream=True)
   115	
   116	
   117	def make_filestore_adapter(context: ProjectContext, env: EnvironmentConfig) -> FilestoreBackend:
   118	    if env.filestore_volume:
   119	        return DockerVolumeFilestore(context, context.config)
   120	    return FilestoreAdapter()
     1	from __future__ import annotations
     2	from pathlib import Path
     3	from odooctl.utils.shell import run, run_capture_bytes, run_pipe_stdin
     4	
     5	class DockerComposeAdapter:
     6	    def __init__(self, compose_file: str = "docker-compose.yml", project_dir: str | None = None):
     7	        self.compose_file = compose_file
     8	        self.project_dir = project_dir
     9	
    10	    def _cmd(self, *args: str) -> list[str]:
    11	        return ["docker", "compose", "-f", self.compose_file, *args]
    12	
    13	    def pull(self, service: str | None = None) -> None:
    14	        run(self._cmd("pull", *([service] if service else [])), cwd=self.project_dir, stream=True)
    15	
    16	    def build(self, service: str | None = None) -> None:
    17	        run(self._cmd("build", *([service] if service else [])), cwd=self.project_dir, stream=True)
    18	
    19	    def up(self, service: str | None = None) -> None:
    20	        run(self._cmd("up", "-d", *([service] if service else [])), cwd=self.project_dir, stream=True)
    21	
    22	    def restart(self, service: str) -> None:
    23	        run(self._cmd("restart", service), cwd=self.project_dir, stream=True)
    24	
    25	    def logs(self, service: str | None = None, *, follow: bool = True, tail: int | None = None) -> None:
    26	        args = ["logs"]
    27	        if follow:
    28	            args.append("-f")
    29	        if tail is not None:
    30	            args.extend(["--tail", str(tail)])
    31	        if service:
    32	            args.append(service)
    33	        run(self._cmd(*args), cwd=self.project_dir, stream=True)
    34	
    35	    def ps(self) -> str:
    36	        return run(self._cmd("ps"), cwd=self.project_dir, check=False).stdout
    37	
    38	    def exec(
    39	        self,
    40	        service: str,
    41	        args: list[str],
    42	        *,
    43	        stream: bool = True,
    44	        extra_env: dict[str, str] | None = None,
    45	    ) -> None:
    46	        """Run a command inside a compose service.
    47	
    48	        ``extra_env`` values are injected into the container via name-only
    49	        ``-e NAME`` flags, with the actual values supplied through the
    50	        subprocess environment — so secrets never appear on argv.
    51	        """
    52	        env_flags: list[str] = []
    53	        for name in extra_env or {}:
    54	            env_flags.extend(["-e", name])
    55	        run(
    56	            self._cmd("exec", "-T", *env_flags, service, *args),
    57	            cwd=self.project_dir,
    58	            env=extra_env,
    59	            stream=stream,
    60	        )
    61	
    62	    def exec_capture_bytes(self, service: str, args: list[str], *, stdout_path: str | Path) -> None:
    63	        run_capture_bytes(self._cmd("exec", "-T", service, *args), cwd=self.project_dir, stdout_path=stdout_path)
    64	
    65	    def exec_pipe_stdin(self, service: str, args: list[str], *, stdin_path: str | Path) -> None:
    66	        run_pipe_stdin(self._cmd("exec", "-T", service, *args), cwd=self.project_dir, stdin_path=stdin_path)

codex
The shell migration does avoid shell parsing, but I’m checking secondary exposure paths now—especially raw arguments retained on exceptions and values that can be reinterpreted as options by downstream CLIs.
exec
/bin/bash -lc 'nl -ba odooctl/security/tokens.py; nl -ba odooctl/security/rbac.py; nl -ba odooctl/security/audit.py; nl -ba odooctl/security/secrets.py; nl -ba odooctl/api/auth.py; nl -ba odooctl/api/routes_operations.py' in /home/dev/odooctl
 succeeded in 0ms:
     1	"""Capability tokens for queued runner actions.
     2	
     3	The web/API layer cannot touch Docker/Postgres directly (see
     4	``runner_contract``). Instead it enqueues an operation and mints a capability
     5	token that authorizes *one* scoped action. The privileged runner verifies the
     6	token before executing, so a leaked queue entry cannot be used against a
     7	different action, environment, or project, and cannot outlive its expiry.
     8	
     9	Replay within the TTL: these tokens are **replayable** while unexpired — a
    10	captured token can be presented again for the *same* action/environment/project
    11	until ``exp`` passes. Single-use enforcement is not provided here; it requires
    12	the runner to record consumed ``nonce`` values (or ``jti``) and reject repeats.
    13	The random ``nonce`` exists to make that future single-use tracking possible and
    14	to keep otherwise-identical tokens distinct; it does not, on its own, prevent
    15	replay. Keep TTLs short to bound the replay window.
    16	
    17	Tokens are stdlib-only: a base64url ``header.payload.signature`` triple where
    18	the signature is ``HMAC-SHA256`` over ``header.payload`` with the shared runner
    19	key. This is a signed (not encrypted) token — payload fields are readable, so
    20	no secret values are ever placed inside one.
    21	"""
    22	from __future__ import annotations
    23	
    24	import base64
    25	import hashlib
    26	import hmac
    27	import json
    28	import secrets as _secrets
    29	import time
    30	
    31	_ALG = "HS256"
    32	
    33	_RESERVED_CLAIMS = frozenset({"act", "env", "proj", "iat", "exp", "nonce", "sub"})
    34	
    35	#: Default capability-token lifetime. Kept short (5 minutes) so a captured
    36	#: token's replay window is small; callers may still override ``ttl_seconds``.
    37	DEFAULT_TTL_SECONDS = 300
    38	
    39	#: Minimum length (in characters/bytes) accepted for the shared HMAC signing
    40	#: key (``ODOOCTL_API_KEY``). Applied at the operator-facing entry points
    41	#: (``odooctl serve`` / ``odooctl runner`` / API app startup) via
    42	#: :func:`enforce_key_strength`.
    43	MIN_API_KEY_LENGTH = 32
    44	
    45	
    46	class TokenError(Exception):
    47	    """Base class for capability-token failures."""
    48	
    49	
    50	class TokenInvalid(TokenError):
    51	    """Malformed token or signature mismatch (tampering)."""
    52	
    53	
    54	class TokenExpired(TokenError):
    55	    """Token is past its expiry."""
    56	
    57	
    58	class TokenScopeError(TokenError):
    59	    """Token does not authorize the requested action/environment/project."""
    60	
    61	
    62	def _b64encode(raw: bytes) -> str:
    63	    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    64	
    65	
    66	def _b64decode(text: str) -> bytes:
    67	    pad = "=" * (-len(text) % 4)
    68	    return base64.urlsafe_b64decode(text + pad)
    69	
    70	
    71	def _sign(key: bytes, signing_input: bytes) -> str:
    72	    return _b64encode(hmac.new(key, signing_input, hashlib.sha256).digest())
    73	
    74	
    75	def _coerce_key(key: str | bytes) -> bytes:
    76	    return key.encode("utf-8") if isinstance(key, str) else key
    77	
    78	
    79	def enforce_key_strength(key: str | bytes, *, source: str = "ODOOCTL_API_KEY") -> None:
    80	    """Reject signing keys shorter than :data:`MIN_API_KEY_LENGTH`.
    81	
    82	    A short HMAC key makes both bearer tokens and capability tokens brute-
    83	    forceable offline. Entry points that accept the operator-supplied key
    84	    (``odooctl serve``, ``odooctl runner``, ``create_app``) call this before
    85	    minting or verifying anything.
    86	    """
    87	    if len(key) < MIN_API_KEY_LENGTH:
    88	        raise ValueError(
    89	            f"{source} is too weak: it must be at least {MIN_API_KEY_LENGTH} "
    90	            f"characters (got {len(key)}). Generate one with e.g. "
    91	            "`python -c 'import secrets; print(secrets.token_hex(32))'`."
    92	        )
    93	
    94	
    95	def mint(
    96	    key: str | bytes,
    97	    *,
    98	    action: str,
    99	    environment: str,
   100	    project: str,
   101	    ttl_seconds: int = DEFAULT_TTL_SECONDS,
   102	    subject: str | None = None,
   103	    nonce: str | None = None,
   104	    now: float | None = None,
   105	    **extra_claims: object,
   106	) -> str:
   107	    """Mint a signed capability token scoped to one action/environment/project.
   108	
   109	    *ttl_seconds* sets the expiry relative to *now* (defaults to current time).
   110	    A random *nonce* is generated when not supplied so two otherwise-identical
   111	    tokens differ. The nonce does not by itself prevent replay: the token stays
   112	    replayable for the same scope until expiry unless the runner records and
   113	    rejects consumed nonces. It exists to make that future single-use tracking
   114	    possible.
   115	
   116	    *extra_claims* are merged into the payload after the required fields, so
   117	    callers can embed ``roles=["operator"]`` for API session tokens without
   118	    changing the verification contract.
   119	    """
   120	    if ttl_seconds <= 0:
   121	        raise ValueError("ttl_seconds must be positive")
   122	    reserved_overlap = _RESERVED_CLAIMS & set(extra_claims)
   123	    if reserved_overlap:
   124	        raise ValueError(f"extra_claims must not override reserved fields: {sorted(reserved_overlap)}")
   125	    issued = int(now if now is not None else time.time())
   126	    payload = {
   127	        "act": action,
   128	        "env": environment,
   129	        "proj": project,
   130	        "iat": issued,
   131	        "exp": issued + int(ttl_seconds),
   132	        "nonce": nonce or _secrets.token_hex(8),
   133	    }
   134	    if subject is not None:
   135	        payload["sub"] = subject
   136	    payload.update(extra_claims)
   137	    header = {"alg": _ALG, "typ": "ocap"}
   138	    h = _b64encode(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
   139	    p = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
   140	    signing_input = f"{h}.{p}".encode()
   141	    sig = _sign(_coerce_key(key), signing_input)
   142	    return f"{h}.{p}.{sig}"
   143	
   144	
   145	def decode_unverified(token: str) -> dict:
   146	    """Return the payload without verifying the signature (for inspection)."""
   147	    try:
   148	        _, p, _ = token.split(".")
   149	        return json.loads(_b64decode(p))
   150	    except Exception as exc:  # noqa: BLE001 - normalise all parse errors
   151	        raise TokenInvalid("malformed token") from exc
   152	
   153	
   154	def verify(
   155	    key: str | bytes,
   156	    token: str,
   157	    *,
   158	    action: str | None = None,
   159	    environment: str | None = None,
   160	    project: str | None = None,
   161	    now: float | None = None,
   162	) -> dict:
   163	    """Verify *token* and return its payload, or raise a :class:`TokenError`.
   164	
   165	    Checks, in order: structure, signature (tampering), expiry, then scope
   166	    (action/environment/project) when those constraints are provided.
   167	    """
   168	    parts = token.split(".")
   169	    if len(parts) != 3:
   170	        raise TokenInvalid("token must have three segments")
   171	    h, p, sig = parts
   172	    expected = _sign(_coerce_key(key), f"{h}.{p}".encode())
   173	    if not hmac.compare_digest(sig, expected):
   174	        raise TokenInvalid("signature mismatch")
   175	
   176	    try:
   177	        payload = json.loads(_b64decode(p))
   178	    except Exception as exc:  # noqa: BLE001
   179	        raise TokenInvalid("payload not decodable") from exc
   180	
   181	    current = int(now if now is not None else time.time())
   182	    exp = payload.get("exp")
   183	    if not isinstance(exp, int) or current >= exp:
   184	        raise TokenExpired("token has expired")
   185	
   186	    if action is not None and payload.get("act") != action:
   187	        raise TokenScopeError(f"token not valid for action '{action}'")
   188	    if environment is not None and payload.get("env") != environment:
   189	        raise TokenScopeError(f"token not valid for environment '{environment}'")
   190	    if project is not None and payload.get("proj") != project:
   191	        raise TokenScopeError(f"token not valid for project '{project}'")
   192	
   193	    return payload
     1	"""Role-based access control matrix and check/require helpers.
     2	
     3	:func:`require` is the primitive a caller uses to gate an action; read actions
     4	are modelled too so the future API can return 403 instead of leaking data.
     5	These helpers define the *policy* — they do not auto-apply to anything. The
     6	existing CLI does not yet call them; wiring them into the API/runner and
     7	service paths is future work (M12+).
     8	
     9	Two dimensions decide an outcome:
    10	
    11	1. The role → action matrix (:data:`ROLE_ACTIONS`).
    12	2. Environment protection: destructive actions targeting a protected /
    13	   production environment require admin-or-higher even when an operator is
    14	   otherwise allowed to run them on non-prod.
    15	"""
    16	from __future__ import annotations
    17	
    18	from enum import Enum
    19	
    20	from odooctl.security.principals import Principal, Role, role_rank
    21	
    22	
    23	class Action(str, Enum):
    24	    """Actions the platform gates.
    25	
    26	    Read-family: observe state without mutation.
    27	    Write-family: mutate environments, data, or configuration.
    28	    """
    29	
    30	    # read-family
    31	    READ = "read"
    32	    STATUS = "status"
    33	    LOGS = "logs"
    34	    BACKUPS = "backups"          # view/list backups
    35	    OPERATIONS = "operations"    # view operation history
    36	    AUDIT = "audit"              # read the audit trail
    37	
    38	    # write-family
    39	    BACKUP = "backup"            # create a backup
    40	    DEPLOY = "deploy"
    41	    CLONE = "clone"
    42	    RESTORE = "restore"
    43	    PROMOTE = "promote"
    44	    ENV = "env"                  # create/destroy environments
    45	    SECRETS = "secrets"          # manage secret store
    46	    CANCEL = "cancel"            # cancel a queued/running operation
    47	
    48	
    49	READ_ACTIONS: frozenset[Action] = frozenset(
    50	    {Action.READ, Action.STATUS, Action.LOGS, Action.BACKUPS, Action.OPERATIONS, Action.AUDIT}
    51	)
    52	
    53	WRITE_ACTIONS: frozenset[Action] = frozenset(
    54	    {
    55	        Action.BACKUP,
    56	        Action.DEPLOY,
    57	        Action.CLONE,
    58	        Action.RESTORE,
    59	        Action.PROMOTE,
    60	        Action.ENV,
    61	        Action.SECRETS,
    62	        Action.CANCEL,
    63	    }
    64	)
    65	
    66	# Destructive actions that, when aimed at a protected/production environment,
    67	# require admin-or-higher regardless of the base matrix.
    68	DESTRUCTIVE_ON_PROTECTED: frozenset[Action] = frozenset(
    69	    {Action.DEPLOY, Action.CLONE, Action.RESTORE, Action.PROMOTE, Action.ENV, Action.SECRETS}
    70	)
    71	
    72	# Minimum role required to act on a protected/production environment for a
    73	# destructive action.
    74	_PROTECTED_FLOOR: Role = Role.ADMIN
    75	
    76	# Base role → allowed actions matrix.
    77	ROLE_ACTIONS: dict[Role, frozenset[Action]] = {
    78	    Role.VIEWER: READ_ACTIONS,
    79	    Role.OPERATOR: READ_ACTIONS
    80	    | frozenset({Action.BACKUP, Action.DEPLOY, Action.CLONE, Action.RESTORE, Action.CANCEL}),
    81	    Role.ADMIN: READ_ACTIONS | WRITE_ACTIONS,
    82	    Role.OWNER: READ_ACTIONS | WRITE_ACTIONS,
    83	}
    84	
    85	
    86	class AccessDenied(PermissionError):
    87	    """Raised when a principal is not permitted to perform an action."""
    88	
    89	    def __init__(self, principal: Principal, action: Action, reason: str = "") -> None:
    90	        self.principal = principal
    91	        self.action = Action(action)
    92	        self.reason = reason or "insufficient role"
    93	        super().__init__(
    94	            f"Access denied: {principal.identity} cannot perform "
    95	            f"'{self.action.value}' ({self.reason})"
    96	        )
    97	
    98	
    99	def _roles_allow(principal: Principal, action: Action) -> bool:
   100	    return any(action in ROLE_ACTIONS.get(role, frozenset()) for role in principal.roles)
   101	
   102	
   103	def is_allowed(principal: Principal, action: Action, *, protected: bool = False) -> bool:
   104	    """Return True if *principal* may perform *action*.
   105	
   106	    When *protected* is True and the action is destructive, the principal must
   107	    hold admin-or-higher in addition to the base matrix allowance.
   108	    """
   109	    action = Action(action)
   110	    if not _roles_allow(principal, action):
   111	        return False
   112	    if protected and action in DESTRUCTIVE_ON_PROTECTED:
   113	        return principal.has_at_least(_PROTECTED_FLOOR)
   114	    return True
   115	
   116	
   117	def require(principal: Principal, action: Action, *, protected: bool = False) -> None:
   118	    """Raise :class:`AccessDenied` if *principal* may not perform *action*."""
   119	    action = Action(action)
   120	    if not _roles_allow(principal, action):
   121	        raise AccessDenied(principal, action, "role lacks this action")
   122	    if protected and action in DESTRUCTIVE_ON_PROTECTED and not principal.has_at_least(_PROTECTED_FLOOR):
   123	        raise AccessDenied(
   124	            principal,
   125	            action,
   126	            f"protected environment requires {_PROTECTED_FLOOR.value} or higher",
   127	        )
   128	
   129	
   130	def allowed_actions(role: Role, *, protected: bool = False) -> frozenset[Action]:
   131	    """Return the set of actions *role* may perform (optionally on protected)."""
   132	    base = ROLE_ACTIONS.get(Role(role), frozenset())
   133	    if not protected:
   134	        return base
   135	    if role_rank(role) >= role_rank(_PROTECTED_FLOOR):
   136	        return base
   137	    return frozenset(a for a in base if a not in DESTRUCTIVE_ON_PROTECTED)
   138	
   139	
   140	def role_matrix() -> dict[str, dict[str, bool]]:
   141	    """Return a serialisable matrix: ``{role: {action: allowed}}``.
   142	
   143	    Used by ``odooctl security rbac`` to render the matrix and by tests to
   144	    assert full coverage of every role/action pair.
   145	    """
   146	    matrix: dict[str, dict[str, bool]] = {}
   147	    for role in Role:
   148	        base = ROLE_ACTIONS.get(role, frozenset())
   149	        matrix[role.value] = {action.value: action in base for action in Action}
   150	    return matrix
nl: odooctl/security/audit.py: No such file or directory
     1	"""Local secret store with env-var references, encryption, and rotation metadata.
     2	
     3	Design constraints:
     4	
     5	- Stdlib only. Confidentiality uses an HMAC-SHA256 keystream (counter mode) and
     6	  integrity uses encrypt-then-MAC with a separate HMAC-SHA256 key, so no
     7	  third-party ``cryptography`` dependency is required for single-host v1.
     8	- Secret *values* never appear in ``repr``, ``str``, logs, events, or audit.
     9	  Values are wrapped in :class:`SecretValue`, which hides itself, and the only
    10	  way to obtain the raw string is the explicit ``.reveal()`` call.
    11	- Two secret sources are supported: an encrypted local store and an env-var
    12	  *reference* (only the variable name is persisted; the value lives in the
    13	  process environment).
    14	- Rotation metadata (version, rotated_at, interval) is tracked per secret.
    15	
    16	Note: this module is named ``secrets`` but Python 3 absolute imports mean
    17	``import secrets`` below resolves to the stdlib module, not this one.
    18	"""
    19	from __future__ import annotations
    20	
    21	import base64
    22	import hashlib
    23	import hmac
    24	import json
    25	import os
    26	import secrets as _stdlib_secrets
    27	from dataclasses import dataclass
    28	from datetime import datetime, timedelta, timezone
    29	from pathlib import Path
    30	
    31	STORE_VERSION = 1
    32	KEY_ENV_VAR = "ODOOCTL_SECRET_KEY"
    33	
    34	
    35	# --------------------------------------------------------------------------- #
    36	# Value wrapper — never reveals itself except via .reveal()
    37	# --------------------------------------------------------------------------- #
    38	class SecretValue:
    39	    """A revealed secret value that refuses to expose itself implicitly.
    40	
    41	    ``repr``/``str`` return a constant mask, so logging or interpolating a
    42	    SecretValue cannot leak the underlying string. Call ``.reveal()`` to obtain
    43	    the raw value at the exact point it is needed.
    44	    """
    45	
    46	    __slots__ = ("_value",)
    47	
    48	    def __init__(self, value: str) -> None:
    49	        self._value = value
    50	
    51	    def reveal(self) -> str:
    52	        return self._value
    53	
    54	    def __repr__(self) -> str:
    55	        return "SecretValue(***)"
    56	
    57	    def __str__(self) -> str:
    58	        return "***"
    59	
    60	    def __eq__(self, other: object) -> bool:
    61	        if isinstance(other, SecretValue):
    62	            return hmac.compare_digest(self._value, other._value)
    63	        return NotImplemented
    64	
    65	    def __hash__(self) -> int:  # pragma: no cover - rarely used
    66	        return hash(("SecretValue",))
    67	
    68	
    69	class SecretNotFound(KeyError):
    70	    """Raised when a secret name is not present in the store."""
    71	
    72	
    73	class SecretDecryptionError(Exception):
    74	    """Raised when stored ciphertext fails authentication (wrong key/tamper)."""
    75	
    76	
    77	# --------------------------------------------------------------------------- #
    78	# Stdlib authenticated encryption (encrypt-then-MAC, HMAC-SHA256 keystream)
    79	# --------------------------------------------------------------------------- #
    80	def _derive_subkeys(key: bytes) -> tuple[bytes, bytes]:
    81	    enc = hashlib.sha256(b"odooctl-enc\x00" + key).digest()
    82	    mac = hashlib.sha256(b"odooctl-mac\x00" + key).digest()
    83	    return enc, mac
    84	
    85	
    86	def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    87	    out = bytearray()
    88	    counter = 0
    89	    while len(out) < length:
    90	        out += hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
    91	        counter += 1
    92	    return bytes(out[:length])
    93	
    94	
    95	def encrypt(key: bytes, plaintext: str) -> dict[str, str]:
    96	    """Return a JSON-serialisable ciphertext envelope for *plaintext*."""
    97	    raw = plaintext.encode("utf-8")
    98	    nonce = _stdlib_secrets.token_bytes(16)
    99	    enc_key, mac_key = _derive_subkeys(key)
   100	    ks = _keystream(enc_key, nonce, len(raw))
   101	    ct = bytes(a ^ b for a, b in zip(raw, ks))
   102	    mac = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
   103	    return {
   104	        "nonce": base64.b64encode(nonce).decode("ascii"),
   105	        "ct": base64.b64encode(ct).decode("ascii"),
   106	        "mac": base64.b64encode(mac).decode("ascii"),
   107	    }
   108	
   109	
   110	def decrypt(key: bytes, envelope: dict[str, str]) -> str:
   111	    """Authenticate and decrypt a ciphertext envelope produced by :func:`encrypt`."""
   112	    try:
   113	        nonce = base64.b64decode(envelope["nonce"])
   114	        ct = base64.b64decode(envelope["ct"])
   115	        mac = base64.b64decode(envelope["mac"])
   116	    except (KeyError, ValueError, TypeError) as exc:
   117	        raise SecretDecryptionError("malformed ciphertext envelope") from exc
   118	    enc_key, mac_key = _derive_subkeys(key)
   119	    expected = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
   120	    if not hmac.compare_digest(mac, expected):
   121	        raise SecretDecryptionError("authentication failed (wrong key or tampered data)")
   122	    ks = _keystream(enc_key, nonce, len(ct))
   123	    return bytes(a ^ b for a, b in zip(ct, ks)).decode("utf-8")
   124	
   125	
   126	def derive_key(passphrase: str, salt: bytes) -> bytes:
   127	    """Derive a 32-byte master key from a passphrase via PBKDF2-HMAC-SHA256."""
   128	    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)
   129	
   130	
   131	# --------------------------------------------------------------------------- #
   132	# Metadata record — carries NO secret value
   133	# --------------------------------------------------------------------------- #
   134	@dataclass(frozen=True)
   135	class SecretRecord:
   136	    """Non-sensitive metadata describing a stored or referenced secret."""
   137	
   138	    name: str
   139	    source: str  # "stored" | "env"
   140	    version: int = 1
   141	    created_at: str = ""
   142	    rotated_at: str = ""
   143	    rotation_interval_days: int | None = None
   144	    env_var: str | None = None  # set when source == "env"
   145	
   146	    def is_due_for_rotation(self, *, now: datetime | None = None) -> bool:
   147	        if not self.rotation_interval_days or not self.rotated_at:
   148	            return False
   149	        now = now or datetime.now(timezone.utc)
   150	        try:
   151	            rotated = datetime.fromisoformat(self.rotated_at)
   152	        except ValueError:
   153	            return False
   154	        return now >= rotated + timedelta(days=self.rotation_interval_days)
   155	
   156	    def to_public_dict(self) -> dict:
   157	        """Public, value-free view safe for CLI/JSON/audit output."""
   158	        return {
   159	            "name": self.name,
   160	            "source": self.source,
   161	            "version": self.version,
   162	            "created_at": self.created_at,
   163	            "rotated_at": self.rotated_at,
   164	            "rotation_interval_days": self.rotation_interval_days,
   165	            "env_var": self.env_var,
   166	            "rotation_due": self.is_due_for_rotation(),
   167	        }
   168	
   169	
   170	def _utcnow() -> str:
   171	    return datetime.now(timezone.utc).isoformat()
   172	
   173	
   174	def _write_private_bytes(path: Path, data: bytes) -> None:
   175	    """Atomically create/overwrite *path* readable only by its owner (0600).
   176	
   177	    The file is created with mode ``0o600`` in the ``os.open`` call itself, so
   178	    there is no window in which it exists at looser permissions before a
   179	    separate ``chmod`` — the flaw of write-then-chmod. ``fchmod`` on the open
   180	    descriptor additionally tightens a file left over from a prior crash without
   181	    introducing a path-based race.
   182	    """
   183	    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
   184	    with os.fdopen(fd, "wb") as fh:
   185	        os.fchmod(fh.fileno(), 0o600)
   186	        fh.write(data)
   187	
   188	
   189	# --------------------------------------------------------------------------- #
   190	# The store
   191	# --------------------------------------------------------------------------- #
   192	class SecretStore:
   193	    """Encrypted local secret store keyed by secret name.
   194	
   195	    The on-disk JSON holds only ciphertext envelopes and value-free metadata.
   196	    Stored values are encrypted with *key*; env-referenced secrets persist only
   197	    the env-var name and are resolved from the process environment on read.
   198	    """
   199	
   200	    def __init__(self, path: Path, key: bytes) -> None:
   201	        self.path = Path(path)
   202	        self._key = key
   203	        self.path.parent.mkdir(parents=True, exist_ok=True)
   204	        self._data = self._load()
   205	
   206	    # ----- persistence ---------------------------------------------------- #
   207	    def _load(self) -> dict:
   208	        if not self.path.exists():
   209	            return {"version": STORE_VERSION, "secrets": {}}
   210	        data = json.loads(self.path.read_text())
   211	        data.setdefault("secrets", {})
   212	        return data
   213	
   214	    def _save(self) -> None:
   215	        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
   216	        payload = json.dumps(self._data, indent=2, sort_keys=True).encode("utf-8")
   217	        _write_private_bytes(tmp, payload)
   218	        tmp.replace(self.path)
   219	
   220	    # ----- mutation ------------------------------------------------------- #
   221	    def put(self, name: str, value: str, *, rotation_interval_days: int | None = None) -> SecretRecord:
   222	        """Store (or replace) an encrypted secret value under *name*."""
   223	        now = _utcnow()
   224	        entry = self._data["secrets"].get(name, {})
   225	        record_meta = {
   226	            "source": "stored",
   227	            "cipher": encrypt(self._key, value),
   228	            "version": 1,
   229	            "created_at": entry.get("created_at", now),
   230	            "rotated_at": now,
   231	            "rotation_interval_days": rotation_interval_days
   232	            if rotation_interval_days is not None
   233	            else entry.get("rotation_interval_days"),
   234	        }
   235	        self._data["secrets"][name] = record_meta
   236	        self._save()
   237	        return self.metadata(name)
   238	
   239	    def put_reference(self, name: str, env_var: str, *, rotation_interval_days: int | None = None) -> SecretRecord:
   240	        """Register an env-var *reference*; only the variable name is persisted."""
   241	        now = _utcnow()
   242	        entry = self._data["secrets"].get(name, {})
   243	        self._data["secrets"][name] = {
   244	            "source": "env",
   245	            "env_var": env_var,
   246	            "version": entry.get("version", 1),
   247	            "created_at": entry.get("created_at", now),
   248	            "rotated_at": entry.get("rotated_at", now),
   249	            "rotation_interval_days": rotation_interval_days
   250	            if rotation_interval_days is not None
   251	            else entry.get("rotation_interval_days"),
   252	        }
   253	        self._save()
   254	        return self.metadata(name)
   255	
   256	    def rotate(self, name: str, new_value: str | None = None) -> SecretRecord:
   257	        """Rotate *name*: bump version and stamp ``rotated_at``.
   258	
   259	        Stored secrets require *new_value*. Env references record the rotation
   260	        event only (the value itself rotates in the environment/secret manager).
   261	        """
   262	        if name not in self._data["secrets"]:
   263	            raise SecretNotFound(name)
   264	        entry = self._data["secrets"][name]
   265	        now = _utcnow()
   266	        if entry["source"] == "stored":
   267	            if new_value is None:
   268	                raise ValueError("rotating a stored secret requires a new value")
   269	            entry["cipher"] = encrypt(self._key, new_value)
   270	        entry["version"] = int(entry.get("version", 1)) + 1
   271	        entry["rotated_at"] = now
   272	        self._save()
   273	        return self.metadata(name)
   274	
   275	    def delete(self, name: str) -> None:
   276	        if name not in self._data["secrets"]:
   277	            raise SecretNotFound(name)
   278	        del self._data["secrets"][name]
   279	        self._save()
   280	
   281	    # ----- read ----------------------------------------------------------- #
   282	    def names(self) -> list[str]:
   283	        return sorted(self._data["secrets"].keys())
   284	
   285	    def metadata(self, name: str) -> SecretRecord:
   286	        if name not in self._data["secrets"]:
   287	            raise SecretNotFound(name)
   288	        entry = self._data["secrets"][name]
   289	        return SecretRecord(
   290	            name=name,
   291	            source=entry["source"],
   292	            version=int(entry.get("version", 1)),
   293	            created_at=entry.get("created_at", ""),
   294	            rotated_at=entry.get("rotated_at", ""),
   295	            rotation_interval_days=entry.get("rotation_interval_days"),
   296	            env_var=entry.get("env_var"),
   297	        )
   298	
   299	    def list_metadata(self) -> list[SecretRecord]:
   300	        return [self.metadata(name) for name in self.names()]
   301	
   302	    def get(self, name: str) -> SecretValue:
   303	        """Return the resolved secret value wrapped in :class:`SecretValue`.
   304	
   305	        For ``stored`` secrets this decrypts the envelope; for ``env`` secrets
   306	        it reads the referenced variable from the process environment. Callers
   307	        must explicitly ``.reveal()`` to obtain the raw string.
   308	        """
   309	        if name not in self._data["secrets"]:
   310	            raise SecretNotFound(name)
   311	        entry = self._data["secrets"][name]
   312	        if entry["source"] == "stored":
   313	            return SecretValue(decrypt(self._key, entry["cipher"]))
   314	        env_var = entry["env_var"]
   315	        if env_var not in os.environ:
   316	            raise SecretNotFound(f"environment variable {env_var} for secret '{name}' is not set")
   317	        return SecretValue(os.environ[env_var])
   318	
   319	    def secret_values(self) -> set[str]:
   320	        """Return all resolvable raw secret values, for feeding the redactor.
   321	
   322	        Used only to build a redaction set; the returned strings must never be
   323	        logged. Unset env references are silently skipped.
   324	        """
   325	        values: set[str] = set()
   326	        for name in self.names():
   327	            try:
   328	                values.add(self.get(name).reveal())
   329	            except SecretNotFound:
   330	                continue
   331	        return values
   332	
   333	    def __repr__(self) -> str:  # never reveal contents
   334	        return f"SecretStore(path={self.path!s}, count={len(self._data['secrets'])})"
   335	
   336	
   337	# --------------------------------------------------------------------------- #
   338	# Key resolution + command-facing helpers
   339	# --------------------------------------------------------------------------- #
   340	def default_store_path(state_dir: Path) -> Path:
   341	    return Path(state_dir) / "secrets" / "secrets.json"
   342	
   343	
   344	def resolve_key(state_dir: Path, *, passphrase: str | None = None) -> bytes:
   345	    """Resolve the master key for a state dir.
   346	
   347	    Preference order:
   348	    1. *passphrase* argument, derived against a persisted per-store salt.
   349	    2. ``ODOOCTL_SECRET_KEY`` env var, derived against the persisted salt.
   350	    3. A random 32-byte key persisted at ``secrets/master.key`` (0600).
   351	
   352	    The salt/key file lives beside the store so a single host can reopen it
   353	    without re-entering a passphrase; rotating the passphrase re-derives.
   354	    """
   355	    secrets_dir = Path(state_dir) / "secrets"
   356	    secrets_dir.mkdir(parents=True, exist_ok=True)
   357	    passphrase = passphrase if passphrase is not None else os.environ.get(KEY_ENV_VAR)
   358	
   359	    if passphrase:
   360	        salt_path = secrets_dir / "salt"
   361	        if salt_path.exists():
   362	            salt = salt_path.read_bytes()
   363	        else:
   364	            salt = _stdlib_secrets.token_bytes(16)
   365	            _write_private_bytes(salt_path, salt)
   366	        return derive_key(passphrase, salt)
   367	
   368	    key_path = secrets_dir / "master.key"
   369	    if key_path.exists():
   370	        return base64.b64decode(key_path.read_text().strip())
   371	    key = _stdlib_secrets.token_bytes(32)
   372	    _write_private_bytes(key_path, base64.b64encode(key))
   373	    return key
   374	
   375	
   376	def open_store(state_dir: Path, *, passphrase: str | None = None) -> SecretStore:
   377	    """Open (or create) the secret store for a project state directory."""
   378	    key = resolve_key(state_dir, passphrase=passphrase)
   379	    return SecretStore(default_store_path(state_dir), key)
     1	"""Authentication and RBAC dependencies for the FastAPI service.
     2	
     3	Tokens are verified via ``odooctl.security.tokens``; roles embedded in the
     4	token payload drive RBAC checks via ``odooctl.security.rbac``.
     5	
     6	Token format (from ``tokens.mint``):
     7	  ``action="api"``, ``environment="*"``, ``project="*"``, plus
     8	  ``roles=["viewer"]`` / ``roles=["operator"]`` in extra_claims.
     9	
    10	No privileged imports — satisfies the runner contract.
    11	"""
    12	from __future__ import annotations
    13	
    14	from fastapi import Depends, Header, HTTPException, Request
    15	
    16	from odooctl.security import rbac, tokens
    17	from odooctl.security.principals import Principal, PrincipalKind, Role
    18	
    19	
    20	def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    21	    if not authorization or not authorization.lower().startswith("bearer "):
    22	        raise HTTPException(status_code=401, detail="Missing bearer token")
    23	    return authorization.split(" ", 1)[1]
    24	
    25	
    26	def get_principal(
    27	    request: Request,
    28	    token_str: str = Depends(_bearer_token),
    29	) -> Principal:
    30	    api_key: str = request.app.state.api_key
    31	    # Key-strength floor (F24): refuse to authenticate against any weak server
    32	    # key. ``create_app`` already rejects a weak key at startup; this is a
    33	    # backstop for apps constructed another way, and applies regardless of how
    34	    # the key was supplied.
    35	    if len(api_key) < tokens.MIN_API_KEY_LENGTH:
    36	        raise HTTPException(status_code=500, detail="Server API key is too weak")
    37	    try:
    38	        payload = tokens.verify(api_key, token_str, action="api")
    39	    except tokens.TokenExpired:
    40	        raise HTTPException(status_code=401, detail="Token expired")
    41	    except tokens.TokenError:
    42	        raise HTTPException(status_code=401, detail="Invalid token")
    43	
    44	    # Expose the token's project scope claim so routes that are not
    45	    # project-scoped in the path (/operations/{id}...) can enforce that the
    46	    # operation belongs to the project the token was minted for. "*" (the
    47	    # session-token default) means all projects.
    48	    request.state.token_project = str(payload.get("proj") or "*")
    49	
    50	    roles_raw = payload.get("roles", ["viewer"])
    51	    role_set: list[Role] = []
    52	    for r in roles_raw:
    53	        try:
    54	            role_set.append(Role(r))
    55	        except ValueError:
    56	            pass
    57	    if not role_set:
    58	        role_set = [Role.VIEWER]
    59	
    60	    sub = payload.get("sub", "api-client")
    61	    org_id = payload.get("org", "default")
    62	    return Principal(
    63	        id=sub,
    64	        org_id=org_id,
    65	        kind=PrincipalKind.TOKEN,
    66	        roles=frozenset(role_set),
    67	        display=sub,
    68	    )
    69	
    70	
    71	def enforce_project_scope(request: Request, project: str) -> None:
    72	    """Reject access when the token's project claim does not cover *project*.
    73	
    74	    A token minted with a concrete ``proj`` claim (not ``"*"``) is confined to
    75	    that one project: it must not read from or enqueue against any other
    76	    project. Session tokens use ``proj="*"`` and are unaffected. Responds 404
    77	    (not 403) so a scoped token cannot enumerate which other projects exist.
    78	    """
    79	    claim = str(getattr(request.state, "token_project", None) or "")
    80	    if claim != "*" and claim != project:
    81	        raise HTTPException(status_code=404, detail=f"Project {project!r} not found")
    82	
    83	
    84	def require_action(action: rbac.Action):
    85	    """Dependency factory: verify bearer token and require *action* via RBAC."""
    86	
    87	    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
    88	        try:
    89	            rbac.require(principal, action)
    90	        except rbac.AccessDenied as exc:
    91	            raise HTTPException(status_code=403, detail=str(exc))
    92	        return principal
    93	
    94	    return _dep
     1	"""Operation queue and event streaming routes.
     2	
     3	POST /projects/{project}/operations  — enqueue a mutating operation.
     4	GET  /operations/{id}                — fetch operation record.
     5	GET  /operations/{id}/events         — SSE stream of operation events.
     6	POST /operations/{id}/cancel         — cancel a queued/running operation.
     7	
     8	Params are redacted via ``odooctl.security.redaction.redact`` before storing.
     9	A capability token scoped to the exact action/environment/project is minted
    10	and embedded in the queue entry; the runner verifies it before executing.
    11	
    12	No privileged imports — satisfies the runner contract.
    13	"""
    14	from __future__ import annotations
    15	
    16	import asyncio
    17	from typing import Any
    18	
    19	from fastapi import APIRouter, Depends, HTTPException, Request
    20	from fastapi.responses import StreamingResponse
    21	from pydantic import BaseModel
    22	
    23	from odooctl.api.auth import get_principal, require_action
    24	from odooctl.security.rbac import Action
    25	
    26	router = APIRouter()
    27	
    28	# Map operation kind strings to the RBAC action that gates them.
    29	_KIND_ACTION: dict[str, Action] = {
    30	    "backup": Action.BACKUP,
    31	    "restore": Action.RESTORE,
    32	    "clone": Action.CLONE,
    33	    "deploy": Action.DEPLOY,
    34	    "promote": Action.PROMOTE,
    35	    "env_create": Action.ENV,
    36	    "env_destroy": Action.ENV,
    37	    "update_modules": Action.DEPLOY,
    38	    "rollback": Action.RESTORE,
    39	    "dr_drill": Action.RESTORE,
    40	    "migrate_rehearsal": Action.RESTORE,
    41	}
    42	
    43	
    44	class OperationRequest(BaseModel):
    45	    kind: str
    46	    environment: str
    47	    params: dict[str, Any] = {}
    48	
    49	
    50	# Server-side ceiling for the events endpoint's ``max_polls`` query parameter
    51	# (600 × 0.5 s = 5 minutes). Prevents a client from pinning a worker on an
    52	# effectively unbounded poll loop.
    53	MAX_POLLS_CEILING = 600
    54	
    55	
    56	def _clamp_max_polls(value: int) -> int:
    57	    """Clamp a client-supplied poll count into [1, MAX_POLLS_CEILING]."""
    58	    return max(1, min(int(value), MAX_POLLS_CEILING))
    59	
    60	
    61	def _require_op_in_token_scope(request: Request, op) -> None:
    62	    """Enforce the token's project claim on non-project-scoped op routes.
    63	
    64	    ``/operations/{op_id}`` routes carry no ``{project}`` path segment, so the
    65	    op is located by searching all projects. A token minted with a concrete
    66	    ``proj`` claim (not ``"*"``) must not read or cancel operations belonging
    67	    to another project. Responds 404 (not 403) so op IDs in other projects are
    68	    not disclosed as existing.
    69	    """
    70	    claim = str(getattr(request.state, "token_project", "*") or "*")
    71	    if claim != "*" and op.project != claim:
    72	        raise HTTPException(status_code=404, detail=f"Operation {op.id!r} not found")
    73	
    74	
    75	def _load_ctx(request: Request, project: str):
    76	    from odooctl.context import ProjectContext
    77	
    78	    reg = request.app.state.registry_loader()
    79	    proj = reg.projects.get(project)
    80	    if proj is None:
    81	        raise HTTPException(status_code=404, detail=f"Project {project!r} not found")
    82	    try:
    83	        return ProjectContext.from_config_path(proj.config, root=proj.path)
    84	    except Exception as exc:
    85	        raise HTTPException(status_code=404, detail=str(exc)) from exc
    86	
    87	
    88	def _find_op_ctx(request: Request, op_id: str):
    89	    """Search all registered projects for an operation by ID."""
    90	    from odooctl.context import ProjectContext
    91	    from odooctl.operations.store import OperationStore
    92	
    93	    reg = request.app.state.registry_loader()
    94	    for proj in reg.projects.values():
    95	        try:
    96	            ctx = ProjectContext.from_config_path(proj.config, root=proj.path)
    97	        except Exception:
    98	            continue
    99	        store = OperationStore(ctx.state_dir)
   100	        try:
   101	            op = store.load(op_id)
   102	            return op, store
   103	        except KeyError:
   104	            continue
   105	    raise HTTPException(status_code=404, detail=f"Operation {op_id!r} not found")
   106	
   107	
   108	@router.post("/projects/{project}/operations", status_code=202)
   109	def enqueue_operation(
   110	    project: str,
   111	    body: OperationRequest,
   112	    request: Request,
   113	    principal=Depends(get_principal),
   114	):
   115	    from odooctl.api.auth import enforce_project_scope
   116	    from odooctl.api.queue import OperationQueue, QueueEntry
   117	    from odooctl.operations.models import Operation, OperationKind
   118	    from odooctl.operations.store import OperationStore
   119	    from odooctl.security import rbac, tokens
   120	    from odooctl.security.redaction import redact
   121	
   122	    enforce_project_scope(request, project)
   123	    ctx = _load_ctx(request, project)
   124	
   125	    # Resolve the target environment before authorization so protected-env
   126	    # policy is applied to the actual enqueue target.
   127	    try:
   128	        protected = ctx.config.is_protected(body.environment)
   129	    except KeyError as exc:
   130	        raise HTTPException(status_code=400, detail=str(exc)) from exc
   131	
   132	    # RBAC check for the specific operation kind
   133	    action = _KIND_ACTION.get(body.kind)
   134	    if action is None:
   135	        raise HTTPException(status_code=400, detail=f"Unknown operation kind: {body.kind!r}")
   136	    try:
   137	        rbac.require(principal, action, protected=protected)
   138	    except rbac.AccessDenied as exc:
   139	        raise HTTPException(status_code=403, detail=str(exc))
   140	
   141	    api_key: str = request.app.state.api_key
   142	
   143	    # Redact user-supplied params before recording
   144	    params_clean = redact(body.params)
   145	
   146	    # Create durable operation record (status=QUEUED)
   147	    try:
   148	        kind_enum = OperationKind(body.kind)
   149	    except ValueError:
   150	        raise HTTPException(status_code=400, detail=f"Invalid operation kind: {body.kind!r}")
   151	
   152	    op = Operation.create(
   153	        kind=kind_enum,
   154	        project=project,
   155	        environment=body.environment,
   156	        actor=principal.id,
   157	        params_redacted=params_clean if isinstance(params_clean, dict) else {},
   158	    )
   159	    store = OperationStore(ctx.state_dir)
   160	    store.save(op)
   161	
   162	    # Mint a short-lived capability token scoped to this exact operation.
   163	    # The default TTL (300 s) bounds the replay window; see F12.
   164	    cap_token = tokens.mint(
   165	        api_key,
   166	        action=body.kind,
   167	        environment=body.environment,
   168	        project=project,
   169	        ttl_seconds=tokens.DEFAULT_TTL_SECONDS,
   170	        subject=principal.id,
   171	        roles=[role.value for role in principal.roles],
   172	    )
   173	
   174	    # Write queue entry
   175	    entry = QueueEntry.create(
   176	        op_id=op.id,
   177	        kind=body.kind,
   178	        project=project,
   179	        environment=body.environment,
   180	        actor=principal.id,
   181	        params_redacted=op.params_redacted,
   182	        token=cap_token,
   183	    )
   184	    OperationQueue(ctx.state_dir).enqueue(entry)
   185	
   186	    return {
   187	        "op_id": op.id,
   188	        "kind": op.kind.value,
   189	        "project": project,
   190	        "environment": body.environment,
   191	        "status": op.status.value,
   192	        "created_at": op.created_at,
   193	    }
   194	
   195	
   196	@router.get("/operations/{op_id}")
   197	def get_operation(
   198	    op_id: str,
   199	    request: Request,
   200	    principal=Depends(require_action(Action.OPERATIONS)),
   201	):
   202	    op, _ = _find_op_ctx(request, op_id)
   203	    _require_op_in_token_scope(request, op)
   204	    return {
   205	        "op_id": op.id,
   206	        "kind": op.kind.value,
   207	        "project": op.project,
   208	        "environment": op.environment,
   209	        "status": op.status.value,
   210	        "actor": op.actor,
   211	        "params_redacted": op.params_redacted,
   212	        "created_at": op.created_at,
   213	        "updated_at": op.updated_at,
   214	        "error": op.error,
   215	        "result_ref": op.result_ref,
   216	    }
   217	
   218	
   219	@router.get("/operations/{op_id}/events")
   220	def stream_events(
   221	    op_id: str,
   222	    request: Request,
   223	    principal=Depends(require_action(Action.OPERATIONS)),
   224	    max_polls: int = 120,
   225	):
   226	    """Stream operation events as Server-Sent Events.
   227	
   228	    Polls until the operation reaches a terminal state or *max_polls* is
   229	    exhausted (default 120 × 0.5 s = 60 s). Pass ``?max_polls=1`` in tests
   230	    to avoid blocking indefinitely on a queued operation. ``max_polls`` is
   231	    clamped server-side to :data:`MAX_POLLS_CEILING`.
   232	    """
   233	    from odooctl.operations.models import OperationStatus
   234	
   235	    op, store = _find_op_ctx(request, op_id)
   236	    _require_op_in_token_scope(request, op)
   237	    max_polls = _clamp_max_polls(max_polls)
   238	
   239	    async def _generate():
   240	        seen = 0
   241	        polls = 0
   242	        while True:
   243	            events = store.load_events(op_id)
   244	            for event in events[seen:]:
   245	                yield f"data: {event.to_json()}\n\n"
   246	                seen += 1
   247	            current_op = store.load(op_id)
   248	            if current_op.status in (
   249	                OperationStatus.SUCCEEDED,
   250	                OperationStatus.FAILED,
   251	                OperationStatus.CANCELLED,
   252	            ):
   253	                break
   254	            polls += 1
   255	            if polls >= max_polls:
   256	                break
   257	            await asyncio.sleep(0.5)
   258	
   259	    return StreamingResponse(_generate(), media_type="text/event-stream")
   260	
   261	
   262	@router.post("/operations/{op_id}/cancel", status_code=200)
   263	def cancel_operation(
   264	    op_id: str,
   265	    request: Request,
   266	    principal=Depends(require_action(Action.CANCEL)),
   267	):
   268	    from odooctl.api.queue import OperationQueue
   269	    from odooctl.context import ProjectContext
   270	    from odooctl.operations.models import OperationStatus
   271	
   272	    op, store = _find_op_ctx(request, op_id)
   273	    _require_op_in_token_scope(request, op)
   274	    if op.status not in (OperationStatus.QUEUED,):
   275	        raise HTTPException(
   276	            status_code=409,
   277	            detail=f"Cannot cancel operation in status {op.status.value!r}",
   278	        )
   279	
   280	    # Remove the pending queue file so the runner cannot claim and execute it.
   281	    # Best-effort: if the queue file is already claimed (.running), the runner
   282	    # will re-check the operation status and skip execution.
   283	    reg = request.app.state.registry_loader()
   284	    proj = reg.projects.get(op.project)
   285	    if proj is not None:
   286	        try:
   287	            ctx = ProjectContext.from_config_path(proj.config, root=proj.path)
   288	            OperationQueue(ctx.state_dir).cancel(op_id)
   289	        except Exception:
   290	            pass
   291	
   292	    updated = store.update_status(op_id, OperationStatus.CANCELLED)
   293	    return {"op_id": updated.id, "status": updated.status.value}

exec
/bin/bash -lc "rg -n \"nonce|tokens\\.verify|Audit|hmac|audit|enforce_key_strength|api_key\" odooctl/security odooctl/operations odooctl/runner odooctl/api odooctl/commands/serve.py odooctl/commands/runner.py; nl -ba odooctl/runner/worker.py; nl -ba odooctl/operations/audit.py; nl -ba odooctl/api/app.py" in /home/dev/odooctl
 succeeded in 0ms:
odooctl/operations/models.py:1:"""Durable operation, event, and audit models."""
odooctl/operations/models.py:153:class AuditEntry:
odooctl/operations/models.py:182:    def from_dict(cls, d: dict) -> "AuditEntry":
odooctl/operations/audit.py:1:"""Append-only audit trail with SHA-256 hash chain.
odooctl/operations/audit.py:14:import hmac
odooctl/operations/audit.py:19:from odooctl.operations.models import AuditEntry
odooctl/operations/audit.py:21:#: Env var holding the optional audit-chain HMAC key.
odooctl/operations/audit.py:26:    """Return the audit HMAC key as bytes, falling back to the environment."""
odooctl/operations/audit.py:38:        return hmac.new(key, canon, hashlib.sha256).hexdigest()
odooctl/operations/audit.py:42:class AuditStore:
odooctl/operations/audit.py:44:        self.path = state_dir / "audit.jsonl"
odooctl/operations/audit.py:52:        # removed. MAC'd with the audit key when keyed.
odooctl/operations/audit.py:53:        self._hwm_path = state_dir / "audit.hwm"
odooctl/operations/audit.py:55:    def append(self, entry: AuditEntry) -> AuditEntry:
odooctl/operations/audit.py:57:        # atomic unit across threads and processes, preventing audit-chain forks.
odooctl/operations/audit.py:79:            return hmac.new(self._key, canon, hashlib.sha256).hexdigest()
odooctl/operations/audit.py:112:        if not hmac.compare_digest(str(hwm.get("mac", "")), self._hwm_mac(count, last_hash)):
odooctl/operations/audit.py:131:    def load_chain(self) -> list[AuditEntry]:
odooctl/operations/audit.py:134:        entries: list[AuditEntry] = []
odooctl/operations/audit.py:139:                    entries.append(AuditEntry.from_dict(json.loads(stripped)))
odooctl/operations/audit.py:145:def verify_chain(entries: list[AuditEntry], *, key: str | bytes | None = None) -> bool:
odooctl/runner/worker.py:7:4. Checks the nonce has not been replayed (single-use enforcement).
odooctl/runner/worker.py:11:8. Appends an audit trail entry.
odooctl/runner/worker.py:28:from odooctl.operations.audit import AUDIT_KEY_ENV_VAR, AuditEntry, AuditStore
odooctl/runner/worker.py:68:# Consumed nonces are retained for twice the maximum capability-token TTL, so
odooctl/runner/worker.py:69:# a nonce always outlives every token that could carry it (replay within the
odooctl/runner/worker.py:75:    """Tracks consumed capability token nonces to prevent replay attacks.
odooctl/runner/worker.py:77:    Nonces are stored in ``{state_dir}/consumed_nonces.json`` as a mapping of
odooctl/runner/worker.py:78:    ``{nonce: consumed_at_iso}``. Entries older than
odooctl/runner/worker.py:80:    The legacy format (``{"nonces": [nonce, ...]}``) is still accepted on
odooctl/runner/worker.py:86:        self._path = state_dir / "consumed_nonces.json"
odooctl/runner/worker.py:87:        self._lock_path = state_dir / "consumed_nonces.lock"
odooctl/runner/worker.py:91:        """Return ``{nonce: expiry_iso}``, migrating the legacy list form.
odooctl/runner/worker.py:100:            raw = json.loads(self._path.read_text()).get("nonces", {})
odooctl/runner/worker.py:114:    def _write_atomic(self, nonces: dict[str, str]) -> None:
odooctl/runner/worker.py:116:        tmp.write_text(json.dumps({"nonces": nonces}))
odooctl/runner/worker.py:120:    def _purge(nonces: dict[str, str], now: datetime) -> dict[str, str]:
odooctl/runner/worker.py:122:        for name, ts in nonces.items():
odooctl/runner/worker.py:134:    def is_consumed(self, nonce: str) -> bool:
odooctl/runner/worker.py:135:        return nonce in self._load()
odooctl/runner/worker.py:137:    def consume(self, nonce: str, *, expires_at: datetime | None = None) -> bool:
odooctl/runner/worker.py:138:        """Atomically claim *nonce*. Returns False if it was already consumed.
odooctl/runner/worker.py:142:        and across concurrent runner processes. The nonce is retained until at
odooctl/runner/worker.py:148:            nonces = self._purge(self._load(), now)
odooctl/runner/worker.py:149:            if nonce in nonces:
odooctl/runner/worker.py:150:                self._write_atomic(nonces)
odooctl/runner/worker.py:154:            nonces[nonce] = expiry.isoformat()
odooctl/runner/worker.py:155:            self._write_atomic(nonces)
odooctl/runner/worker.py:158:    def mark_consumed(self, nonce: str, *, expires_at: datetime | None = None) -> None:
odooctl/runner/worker.py:160:        self.consume(nonce, expires_at=expires_at)
odooctl/runner/worker.py:166:    def __init__(self, registry: "Registry", api_key: str) -> None:
odooctl/runner/worker.py:168:        self._api_key = api_key
odooctl/runner/worker.py:170:        # One-time notice when the audit chain is unkeyed: without
odooctl/runner/worker.py:177:                "Audit chain is unkeyed (ODOOCTL_AUDIT_KEY not set); entries are "
odooctl/runner/worker.py:179:                "HMAC-protected audit logging.",
odooctl/runner/worker.py:209:        audit = AuditStore(ctx.state_dir)
odooctl/runner/worker.py:210:        nonce_store = NonceStore(ctx.state_dir)
odooctl/runner/worker.py:224:            payload = tokens.verify(
odooctl/runner/worker.py:225:                self._api_key,
odooctl/runner/worker.py:248:        # Single-use nonce check: atomic claim under a file lock closes the
odooctl/runner/worker.py:249:        # check-then-mark race and retains the nonce until the token's own
odooctl/runner/worker.py:251:        nonce = payload.get("nonce", "")
odooctl/runner/worker.py:256:        if not nonce_store.consume(nonce, expires_at=expires_at):
odooctl/runner/worker.py:260:                error=f"token nonce already consumed: {nonce}",
odooctl/runner/worker.py:303:        audit.append(
odooctl/runner/worker.py:304:            AuditEntry(
odooctl/operations/__init__.py:1:"""Operation engine — durable operation records, events, audit, and locks."""
odooctl/operations/__init__.py:2:from odooctl.operations.audit import AuditStore, verify_chain
odooctl/operations/__init__.py:6:    AuditEntry,
odooctl/operations/__init__.py:15:    "AuditEntry",
odooctl/operations/__init__.py:16:    "AuditStore",
odooctl/operations/engine.py:8:from odooctl.operations.audit import AuditStore, AuditEntry
odooctl/operations/engine.py:53:    audit: AuditStore,
odooctl/operations/engine.py:66:    an audit entry regardless of outcome.
odooctl/operations/engine.py:91:        audit.append(
odooctl/operations/engine.py:92:            AuditEntry(
odooctl/operations/engine.py:131:        audit.append(
odooctl/operations/engine.py:132:            AuditEntry(
odooctl/commands/runner.py:13:def run(*, once: bool = False, fail_fast: bool = False, api_key: str | None = None) -> None:
odooctl/commands/runner.py:14:    if api_key is None:
odooctl/commands/runner.py:15:        api_key = os.environ.get("ODOOCTL_API_KEY", "")
odooctl/commands/runner.py:16:    if not api_key:
odooctl/commands/runner.py:26:        tokens.enforce_key_strength(api_key)
odooctl/commands/runner.py:35:    worker = RunnerWorker(registry=registry, api_key=api_key)
odooctl/commands/serve.py:25:    api_key: str | None = None,
odooctl/commands/serve.py:38:    if api_key is None:
odooctl/commands/serve.py:39:        api_key = os.environ.get("ODOOCTL_API_KEY", "")
odooctl/commands/serve.py:40:    if not api_key:
odooctl/commands/serve.py:53:    app = create_app(api_key=api_key, static_dir=static_dir)
odooctl/api/routes_operations.py:141:    api_key: str = request.app.state.api_key
odooctl/api/routes_operations.py:165:        api_key,
odooctl/api/routes_projects.py:186:@router.get("/projects/{project}/audit")
odooctl/api/routes_projects.py:187:def get_audit(
odooctl/api/routes_projects.py:192:    from odooctl.operations.audit import AuditStore
odooctl/api/routes_projects.py:195:    audit = AuditStore(ctx.state_dir)
odooctl/api/routes_projects.py:196:    entries = audit.load_chain()
odooctl/api/app.py:3:Create the app with ``create_app(api_key=..., registry_loader=...)`` and
odooctl/api/app.py:30:    api_key: str,
odooctl/api/app.py:39:    :param api_key: Shared HMAC key used to verify bearer tokens.
odooctl/api/app.py:54:    tokens.enforce_key_strength(api_key)
odooctl/api/app.py:67:    app.state.api_key = api_key
odooctl/api/__init__.py:5:operations, streams events, and reads the audit trail, but never touches
odooctl/api/auth.py:30:    api_key: str = request.app.state.api_key
odooctl/api/auth.py:35:    if len(api_key) < tokens.MIN_API_KEY_LENGTH:
odooctl/api/auth.py:38:        payload = tokens.verify(api_key, token_str, action="api")
odooctl/security/principals.py:9:audit records reason about. It carries the org it belongs to, the kind of
odooctl/security/principals.py:25:    - ``viewer``: read-only (status/logs/backups/operations/audit).
odooctl/security/principals.py:80:    """An authenticated identity that RBAC and audit reason about.
odooctl/security/principals.py:99:        """Stable identity string for audit records, e.g. ``user:alice@acme``."""
odooctl/security/redaction.py:4:before they reach logs, operation events, audit records, or CLI output. Two
odooctl/security/rbac.py:36:    AUDIT = "audit"              # read the audit trail
odooctl/security/__init__.py:17:- Secret *values* are never represented in ``repr``/log/audit surfaces.
odooctl/security/secrets.py:8:- Secret *values* never appear in ``repr``, ``str``, logs, events, or audit.
odooctl/security/secrets.py:23:import hmac
odooctl/security/secrets.py:62:            return hmac.compare_digest(self._value, other._value)
odooctl/security/secrets.py:86:def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
odooctl/security/secrets.py:90:        out += hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
odooctl/security/secrets.py:98:    nonce = _stdlib_secrets.token_bytes(16)
odooctl/security/secrets.py:100:    ks = _keystream(enc_key, nonce, len(raw))
odooctl/security/secrets.py:102:    mac = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
odooctl/security/secrets.py:104:        "nonce": base64.b64encode(nonce).decode("ascii"),
odooctl/security/secrets.py:113:        nonce = base64.b64decode(envelope["nonce"])
odooctl/security/secrets.py:119:    expected = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
odooctl/security/secrets.py:120:    if not hmac.compare_digest(mac, expected):
odooctl/security/secrets.py:122:    ks = _keystream(enc_key, nonce, len(ct))
odooctl/security/secrets.py:128:    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)
odooctl/security/secrets.py:157:        """Public, value-free view safe for CLI/JSON/audit output."""
odooctl/security/tokens.py:12:the runner to record consumed ``nonce`` values (or ``jti``) and reject repeats.
odooctl/security/tokens.py:13:The random ``nonce`` exists to make that future single-use tracking possible and
odooctl/security/tokens.py:26:import hmac
odooctl/security/tokens.py:33:_RESERVED_CLAIMS = frozenset({"act", "env", "proj", "iat", "exp", "nonce", "sub"})
odooctl/security/tokens.py:42:#: :func:`enforce_key_strength`.
odooctl/security/tokens.py:72:    return _b64encode(hmac.new(key, signing_input, hashlib.sha256).digest())
odooctl/security/tokens.py:79:def enforce_key_strength(key: str | bytes, *, source: str = "ODOOCTL_API_KEY") -> None:
odooctl/security/tokens.py:103:    nonce: str | None = None,
odooctl/security/tokens.py:110:    A random *nonce* is generated when not supplied so two otherwise-identical
odooctl/security/tokens.py:111:    tokens differ. The nonce does not by itself prevent replay: the token stays
odooctl/security/tokens.py:113:    rejects consumed nonces. It exists to make that future single-use tracking
odooctl/security/tokens.py:132:        "nonce": nonce or _secrets.token_hex(8),
odooctl/security/tokens.py:173:    if not hmac.compare_digest(sig, expected):
odooctl/security/runner_contract.py:6:and read the audit trail. All privileged work happens in the runner.
odooctl/security/runner_contract.py:49:    "read audit (per RBAC)",
     1	"""Privileged runner worker — claims and executes queued operations.
     2	
     3	The runner:
     4	1. Loads the registry and iterates registered projects.
     5	2. Claims the oldest pending queue entry (atomic POSIX rename).
     6	3. Verifies the capability token (signature, expiry, scope).
     7	4. Checks the nonce has not been replayed (single-use enforcement).
     8	5. Acquires the per-environment lock.
     9	6. Executes the appropriate service call.
    10	7. Emits operation events and transitions status QUEUED→RUNNING→SUCCEEDED/FAILED.
    11	8. Appends an audit trail entry.
    12	
    13	This module is privileged — it imports ``odooctl.adapters`` / ``odooctl.odoo``
    14	transitively via the service layer. It must never be imported by odooctl.api.
    15	"""
    16	from __future__ import annotations
    17	
    18	import fcntl
    19	import json
    20	import os
    21	import time
    22	import warnings
    23	from datetime import datetime, timedelta, timezone
    24	from pathlib import Path
    25	from typing import TYPE_CHECKING
    26	
    27	from odooctl.api.queue import OperationQueue, QueueEntry
    28	from odooctl.operations.audit import AUDIT_KEY_ENV_VAR, AuditEntry, AuditStore
    29	from odooctl.operations.engine import OperationContext
    30	from odooctl.operations.locks import EnvironmentLock, LockAcquisitionError
    31	from odooctl.operations.models import (
    32	    OperationKind,
    33	    OperationStatus,
    34	    _utcnow,
    35	)
    36	from odooctl.operations.store import OperationStore
    37	from odooctl.security import rbac, tokens
    38	from odooctl.security.principals import Principal, PrincipalKind, Role
    39	from odooctl.security.tokens import TokenError
    40	from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
    41	from odooctl.adapters.filestore import FilestoreAdapter
    42	from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult
    43	from odooctl.services.backup import run_backup
    44	from odooctl.services.clone import run_clone
    45	from odooctl.services.context import ServiceContext
    46	from odooctl.services.dr import run_dr_drill
    47	from odooctl.utils.shell import redact
    48	
    49	if TYPE_CHECKING:
    50	    from odooctl.registry import Registry
    51	
    52	
    53	_KIND_ACTION: dict[str, rbac.Action] = {
    54	    "backup": rbac.Action.BACKUP,
    55	    "restore": rbac.Action.RESTORE,
    56	    "clone": rbac.Action.CLONE,
    57	    "deploy": rbac.Action.DEPLOY,
    58	    "promote": rbac.Action.PROMOTE,
    59	    "env_create": rbac.Action.ENV,
    60	    "env_destroy": rbac.Action.ENV,
    61	    "update_modules": rbac.Action.DEPLOY,
    62	    "rollback": rbac.Action.RESTORE,
    63	    "dr_drill": rbac.Action.RESTORE,
    64	    "migrate_rehearsal": rbac.Action.RESTORE,
    65	}
    66	
    67	
    68	# Consumed nonces are retained for twice the maximum capability-token TTL, so
    69	# a nonce always outlives every token that could carry it (replay within the
    70	# token validity window stays blocked) while the store cannot grow unbounded.
    71	NONCE_RETENTION_SECONDS = 7200  # 2 h = 2 × max token TTL
    72	
    73	
    74	class NonceStore:
    75	    """Tracks consumed capability token nonces to prevent replay attacks.
    76	
    77	    Nonces are stored in ``{state_dir}/consumed_nonces.json`` as a mapping of
    78	    ``{nonce: consumed_at_iso}``. Entries older than
    79	    :data:`NONCE_RETENTION_SECONDS` are purged on each :meth:`mark_consumed`.
    80	    The legacy format (``{"nonces": [nonce, ...]}``) is still accepted on
    81	    read; legacy entries are migrated to a now-timestamp on first write (they
    82	    remain consumed until they age out).
    83	    """
    84	
    85	    def __init__(self, state_dir: Path) -> None:
    86	        self._path = state_dir / "consumed_nonces.json"
    87	        self._lock_path = state_dir / "consumed_nonces.lock"
    88	        state_dir.mkdir(parents=True, exist_ok=True)
    89	
    90	    def _load(self) -> dict[str, str]:
    91	        """Return ``{nonce: expiry_iso}``, migrating the legacy list form.
    92	
    93	        A truncated/corrupt file (e.g. a crash during a non-atomic write in an
    94	        older version) yields ``{}`` — with atomic writes below this is no
    95	        longer produced, but reads stay defensive.
    96	        """
    97	        if not self._path.exists():
    98	            return {}
    99	        try:
   100	            raw = json.loads(self._path.read_text()).get("nonces", {})
   101	        except Exception:
   102	            return {}
   103	        default_expiry = (
   104	            datetime.now(timezone.utc) + timedelta(seconds=NONCE_RETENTION_SECONDS)
   105	        ).isoformat()
   106	        if isinstance(raw, dict):
   107	            return {str(n): str(ts) for n, ts in raw.items()}
   108	        if isinstance(raw, list):
   109	            # Legacy format: no timestamp — keep blocked for a full retention
   110	            # window so replay stays blocked; ages out on the normal purge.
   111	            return {str(n): default_expiry for n in raw}
   112	        return {}
   113	
   114	    def _write_atomic(self, nonces: dict[str, str]) -> None:
   115	        tmp = self._path.with_suffix(".json.tmp")
   116	        tmp.write_text(json.dumps({"nonces": nonces}))
   117	        os.replace(tmp, self._path)
   118	
   119	    @staticmethod
   120	    def _purge(nonces: dict[str, str], now: datetime) -> dict[str, str]:
   121	        kept: dict[str, str] = {}
   122	        for name, ts in nonces.items():
   123	            try:
   124	                expiry = datetime.fromisoformat(ts)
   125	            except (TypeError, ValueError):
   126	                kept[name] = (now + timedelta(seconds=NONCE_RETENTION_SECONDS)).isoformat()
   127	                continue
   128	            if expiry.tzinfo is None:
   129	                expiry = expiry.replace(tzinfo=timezone.utc)
   130	            if expiry >= now:
   131	                kept[name] = ts
   132	        return kept
   133	
   134	    def is_consumed(self, nonce: str) -> bool:
   135	        return nonce in self._load()
   136	
   137	    def consume(self, nonce: str, *, expires_at: datetime | None = None) -> bool:
   138	        """Atomically claim *nonce*. Returns False if it was already consumed.
   139	
   140	        The whole check-and-mark runs under an exclusive file lock, closing the
   141	        TOCTOU window between a separate ``is_consumed``/``mark_consumed`` pair
   142	        and across concurrent runner processes. The nonce is retained until at
   143	        least its token's expiry (``expires_at``), never purged early.
   144	        """
   145	        with self._lock_path.open("w") as lock_file:
   146	            fcntl.flock(lock_file, fcntl.LOCK_EX)
   147	            now = datetime.now(timezone.utc)
   148	            nonces = self._purge(self._load(), now)
   149	            if nonce in nonces:
   150	                self._write_atomic(nonces)
   151	                return False
   152	            floor = now + timedelta(seconds=NONCE_RETENTION_SECONDS)
   153	            expiry = max(floor, expires_at) if expires_at else floor
   154	            nonces[nonce] = expiry.isoformat()
   155	            self._write_atomic(nonces)
   156	            return True
   157	
   158	    def mark_consumed(self, nonce: str, *, expires_at: datetime | None = None) -> None:
   159	        # Backward-compatible unconditional mark, now atomic + locked.
   160	        self.consume(nonce, expires_at=expires_at)
   161	
   162	
   163	class RunnerWorker:
   164	    """Claims and executes one queued operation per ``claim_and_run()`` call."""
   165	
   166	    def __init__(self, registry: "Registry", api_key: str) -> None:
   167	        self._registry = registry
   168	        self._api_key = api_key
   169	        self.last_run_ok: bool = True
   170	        # One-time notice when the audit chain is unkeyed: without
   171	        # ODOOCTL_AUDIT_KEY the hash chain is plain SHA-256, so an attacker with
   172	        # filesystem write access could forge or rehash entries. The chain still
   173	        # detects truncation via the high-water mark, but tamper-evidence needs
   174	        # the key.
   175	        if not os.environ.get(AUDIT_KEY_ENV_VAR):
   176	            warnings.warn(
   177	                "Audit chain is unkeyed (ODOOCTL_AUDIT_KEY not set); entries are "
   178	                "not cryptographically tamper-evident. Set ODOOCTL_AUDIT_KEY for "
   179	                "HMAC-protected audit logging.",
   180	                stacklevel=2,
   181	            )
   182	
   183	    def claim_and_run(self) -> bool:
   184	        """Claim and execute one operation. Returns True if work was done.
   185	
   186	        The outcome of the most recent executed operation is recorded on
   187	        ``self.last_run_ok`` so callers (``run_loop``) can report failures.
   188	        """
   189	        for proj_name, proj in self._registry.projects.items():
   190	            from odooctl.context import ProjectContext
   191	
   192	            try:
   193	                ctx = ProjectContext.from_config_path(proj.config, root=proj.path)
   194	            except Exception:
   195	                continue
   196	
   197	            queue = OperationQueue(ctx.state_dir)
   198	            entry = queue.claim_next()
   199	            if entry is None:
   200	                continue
   201	
   202	            self.last_run_ok = self._execute_entry(entry, queue, ctx)
   203	            return True
   204	        self.last_run_ok = True
   205	        return False
   206	
   207	    def _execute_entry(self, entry: QueueEntry, queue: OperationQueue, ctx) -> bool:
   208	        store = OperationStore(ctx.state_dir)
   209	        audit = AuditStore(ctx.state_dir)
   210	        nonce_store = NonceStore(ctx.state_dir)
   211	        svc_ctx = ServiceContext(project=ctx)
   212	
   213	        # Re-check status: the operation may have been cancelled after we claimed
   214	        # the queue entry (post-claim race). Skip execution and clean up.
   215	        try:
   216	            if store.load(entry.op_id).status == OperationStatus.CANCELLED:
   217	                queue.complete(entry.op_id)
   218	                return True
   219	        except KeyError:
   220	            pass
   221	
   222	        # Verify the capability token
   223	        try:
   224	            payload = tokens.verify(
   225	                self._api_key,
   226	                entry.token,
   227	                action=entry.kind,
   228	                environment=entry.environment,
   229	                project=entry.project,
   230	            )
   231	        except TokenError as exc:
   232	            store.update_status(entry.op_id, OperationStatus.FAILED, error=redact(f"token error: {exc}"))
   233	            queue.fail(entry.op_id)
   234	            return False
   235	
   236	        # Defensive RBAC floor: do not trust queue shape alone. Reconstruct the
   237	        # token-derived principal and enforce the same protected-env floor that
   238	        # the API applied before enqueueing.
   239	        try:
   240	            action = _KIND_ACTION[entry.kind]
   241	            protected = ctx.config.is_protected(entry.environment)
   242	            rbac.require(_principal_from_payload(payload), action, protected=protected)
   243	        except (KeyError, ValueError, rbac.AccessDenied) as exc:
   244	            store.update_status(entry.op_id, OperationStatus.FAILED, error=redact(f"rbac error: {exc}"))
   245	            queue.fail(entry.op_id)
   246	            return False
   247	
   248	        # Single-use nonce check: atomic claim under a file lock closes the
   249	        # check-then-mark race and retains the nonce until the token's own
   250	        # expiry so a long-TTL token can never be replayed after purge.
   251	        nonce = payload.get("nonce", "")
   252	        token_exp = payload.get("exp")
   253	        expires_at = None
   254	        if isinstance(token_exp, (int, float)):
   255	            expires_at = datetime.fromtimestamp(token_exp, tz=timezone.utc)
   256	        if not nonce_store.consume(nonce, expires_at=expires_at):
   257	            store.update_status(
   258	                entry.op_id,
   259	                OperationStatus.FAILED,
   260	                error=f"token nonce already consumed: {nonce}",
   261	            )
   262	            queue.fail(entry.op_id)
   263	            return False
   264	
   265	        # Transition to RUNNING and emit start event
   266	        store.update_status(entry.op_id, OperationStatus.RUNNING)
   267	        op = store.load(entry.op_id)
   268	        op_ctx = OperationContext(op, store)
   269	        op_ctx.emit(
   270	            f"operation started: {entry.kind} on {entry.environment}",
   271	            phase="start",
   272	        )
   273	
   274	        # Acquire per-environment lock and execute
   275	        lock = EnvironmentLock(entry.environment, ctx.state_dir, entry.op_id)
   276	        outcome = "failed"
   277	        error_msg: str | None = None
   278	
   279	        try:
   280	            lock.__enter__()
   281	            try:
   282	                _dispatch(entry, svc_ctx, op_ctx)
   283	                outcome = "succeeded"
   284	            except Exception as exc:
   285	                # Second redaction layer: this string is persisted into the
   286	                # operation store and streamed to API clients.
   287	                error_msg = redact(str(exc))
   288	            finally:
   289	                lock.__exit__(None, None, None)
   290	        except LockAcquisitionError as exc:
   291	            error_msg = f"lock acquisition failed: {exc}"
   292	
   293	        # Finalise operation status
   294	        if outcome == "succeeded":
   295	            op_ctx.emit("operation completed", phase="end", level="info")
   296	            store.update_status(entry.op_id, OperationStatus.SUCCEEDED)
   297	            queue.complete(entry.op_id)
   298	        else:
   299	            op_ctx.emit(f"operation failed: {error_msg}", phase="end", level="error")
   300	            store.update_status(entry.op_id, OperationStatus.FAILED, error=error_msg)
   301	            queue.fail(entry.op_id)
   302	
   303	        audit.append(
   304	            AuditEntry(
   305	                actor=entry.actor,
   306	                action=entry.kind,
   307	                target=entry.environment,
   308	                params_redacted=entry.params_redacted,
   309	                outcome=outcome,
   310	                op_id=entry.op_id,
   311	                timestamp=_utcnow(),
   312	            )
   313	        )
   314	        return outcome == "succeeded"
   315	
   316	    def run_loop(self, *, once: bool = False, fail_fast: bool = False) -> bool:
   317	        """Process the queue in a loop.
   318	
   319	        :param once: If True, process at most one item and return (used by
   320	            ``odooctl runner --once``).
   321	        :param fail_fast: If True, stop looping as soon as an operation fails.
   322	        :returns: True if every executed operation succeeded, False if the
   323	            last executed operation failed (``once``) or a failure stopped the
   324	            loop (``fail_fast``). ``odooctl runner`` exits non-zero on False.
   325	        """
   326	        while True:
   327	            did_work = self.claim_and_run()
   328	            if once:
   329	                return self.last_run_ok
   330	            if did_work and fail_fast and not self.last_run_ok:
   331	                return False
   332	            if not did_work:
   333	                time.sleep(1)
   334	
   335	
   336	def _dispatch(entry: QueueEntry, svc_ctx: ServiceContext, op_ctx: OperationContext) -> None:
   337	    """Dispatch a queued entry to the appropriate service call."""
   338	    kind = entry.kind
   339	    env = entry.environment
   340	    params = entry.params_redacted
   341	
   342	    if kind == OperationKind.BACKUP.value:
   343	        result = run_backup(svc_ctx, env)
   344	        op_ctx.emit(f"backup complete: {result.backup_id}", phase="backup")
   345	
   346	    elif kind == OperationKind.CLONE.value:
   347	        source = params.get("source", "production")
   348	        result = run_clone(svc_ctx, source, env)
   349	        op_ctx.emit(f"clone complete: {result.url}", phase="clone")
   350	
   351	    elif kind == OperationKind.DR_DRILL.value:
   352	        cfg = svc_ctx.project.config
   353	        db_adapter = make_context_db_adapter(svc_ctx.project)
   354	        fs_adapter = FilestoreAdapter()
   355	
   356	        def healthcheck_fn(url: str) -> bool:
   357	            try:
   358	                from odooctl.odoo.healthcheck import check_url
   359	
   360	                check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=1, interval=1)
   361	                return True
   362	            except Exception:
   363	                return False
   364	
   365	        result = run_dr_drill(
   366	            environment=env,
   367	            backups_root=svc_ctx.project.backups_dir,
   368	            db_adapter=db_adapter,
   369	            fs_adapter=fs_adapter,
   370	            healthcheck_fn=healthcheck_fn,
   371	            is_protected_fn=cfg.is_protected,
   372	        )
   373	        if result.status != "success":
   374	            raise RuntimeError(result.message or "DR drill failed")
   375	        op_ctx.emit(f"DR drill complete: {result.backup_id}", phase="dr_drill")
   376	
   377	    elif kind == OperationKind.MIGRATE_REHEARSAL.value:
   378	        from odooctl.migration.matrix import supported_paths
   379	
   380	        cfg = svc_ctx.project.config
   381	        env_cfg = cfg.env(env)
   382	        db_adapter = make_context_db_adapter(svc_ctx.project)
   383	        target_version = params.get("to", "")
   384	        if not target_version:
   385	            raise ValueError("migrate_rehearsal requires 'to' version in params")
   386	        use_openupgrade = bool(params.get("openupgrade", False))
   387	        keep_throwaway = bool(params.get("keep", False))
   388	        from_version = cfg.project.odoo_version
   389	
   390	        matrix_paths = supported_paths(from_version=from_version, to_version=target_version)
   391	        if not matrix_paths:
   392	            raise ValueError(
   393	                f"No supported migration path from {from_version!r} to {target_version!r}; "
   394	                "check the migration matrix for supported paths."
   395	            )
   396	        path_requires_ou = any(p.requires_openupgrade for p in matrix_paths)
   397	
   398	        def _upgrade_fn(throwaway_db: str, tgt_ver: str) -> UpgradeResult:
   399	            from odooctl.adapters.docker_compose import DockerComposeAdapter
   400	
   401	            compose = DockerComposeAdapter(
   402	                cfg.runtime.compose_file, project_dir=str(svc_ctx.project.root)
   403	            )
   404	            if use_openupgrade:
   405	                from odooctl.migration.openupgrade import openupgrade_db_command
   406	
   407	                cmd = openupgrade_db_command(throwaway_db, tgt_ver)
   408	                if cmd is None:
   409	                    raise ValueError(
   410	                        f"OpenUpgrade does not support target version {tgt_ver!r}; "
   411	                        "check PINNED_BRANCHES or remove --openupgrade"
   412	                    )
   413	            else:
   414	                cmd = [
   415	                    "odoo",
   416	                    "--database", throwaway_db,
   417	                    "--update", "all",
   418	                    "--stop-after-init",
   419	                ]
   420	            try:
   421	                compose.exec(cfg.odoo.service, cmd, stream=True)
   422	                return UpgradeResult(ok=True)
   423	            except Exception as exc:
   424	                return UpgradeResult(ok=False, warnings=[str(exc)])
   425	
   426	        def _healthcheck_fn(db_name: str) -> bool:
   427	            # Ping the throwaway DB — after --stop-after-init Odoo is not running,
   428	            # so an HTTP check against the source env URL would test the wrong target.
   429	            try:
   430	                db_adapter.ping(db_name)
   431	                return True
   432	            except Exception:
   433	                return False
   434	
   435	        report_dir = svc_ctx.project.state_dir / "migration_reports"
   436	
   437	        result = rehearse_upgrade(
   438	            source_env=env,
   439	            source_version=from_version,
   440	            target_version=target_version,
   441	            source_db=env_cfg.db_name,
   442	            db_adapter=db_adapter,
   443	            healthcheck_fn=_healthcheck_fn,
   444	            upgrade_fn=_upgrade_fn,
   445	            report_dir=report_dir,
   446	            keep=keep_throwaway,
   447	            requires_openupgrade=path_requires_ou,
   448	            use_openupgrade=use_openupgrade,
   449	        )
   450	        if result.status != "success":
   451	            raise RuntimeError(result.message or "Migration rehearsal failed")
   452	        op_ctx.emit(
   453	            f"migrate rehearsal complete: {env} {result.source_version} → {target_version}",
   454	            phase="migrate_rehearsal",
   455	        )
   456	
   457	    else:
   458	        raise ValueError(f"Unsupported operation kind in runner: {kind!r}")
   459	
   460	
   461	def _principal_from_payload(payload: dict) -> Principal:
   462	    roles_raw = payload.get("roles", [])
   463	    roles: list[Role] = []
   464	    if isinstance(roles_raw, list):
   465	        for role in roles_raw:
   466	            try:
   467	                roles.append(Role(role))
   468	            except ValueError:
   469	                continue
   470	
   471	    subject = str(payload.get("sub", "api-client"))
   472	    return Principal(
   473	        id=subject,
   474	        org_id=str(payload.get("org", "default")),
   475	        kind=PrincipalKind.TOKEN,
   476	        roles=frozenset(roles),
   477	        display=subject,
   478	    )
     1	"""Append-only audit trail with SHA-256 hash chain.
     2	
     3	Optional HMAC keying (F13): when the ``ODOOCTL_AUDIT_KEY`` env var is set (or
     4	an explicit ``key`` is passed), each link is computed as
     5	``HMAC-SHA256(key, canonical_json({**entry, "prev_hash": prev_hash}))``
     6	instead of an unkeyed SHA-256. An attacker with file write access can
     7	truncate-and-rehash an unkeyed chain; without the key they cannot forge valid
     8	HMAC links. Unkeyed hashing remains the default for backward compatibility.
     9	"""
    10	from __future__ import annotations
    11	
    12	import fcntl
    13	import hashlib
    14	import hmac
    15	import json
    16	import os
    17	from pathlib import Path
    18	
    19	from odooctl.operations.models import AuditEntry
    20	
    21	#: Env var holding the optional audit-chain HMAC key.
    22	AUDIT_KEY_ENV_VAR = "ODOOCTL_AUDIT_KEY"
    23	
    24	
    25	def _resolve_key(key: str | bytes | None) -> bytes | None:
    26	    """Return the audit HMAC key as bytes, falling back to the environment."""
    27	    if key is None:
    28	        key = os.environ.get(AUDIT_KEY_ENV_VAR) or None
    29	    if key is None:
    30	        return None
    31	    return key.encode("utf-8") if isinstance(key, str) else key
    32	
    33	
    34	def _hash_entry(entry_dict: dict, prev_hash: str, key: bytes | None = None) -> str:
    35	    payload = {**entry_dict, "prev_hash": prev_hash}
    36	    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    37	    if key:
    38	        return hmac.new(key, canon, hashlib.sha256).hexdigest()
    39	    return hashlib.sha256(canon).hexdigest()
    40	
    41	
    42	class AuditStore:
    43	    def __init__(self, state_dir: Path, *, key: str | bytes | None = None) -> None:
    44	        self.path = state_dir / "audit.jsonl"
    45	        self.path.parent.mkdir(parents=True, exist_ok=True)
    46	        # Chain-hash HMAC key; defaults to ODOOCTL_AUDIT_KEY when set, else
    47	        # the chain remains unkeyed (plain SHA-256) for compatibility.
    48	        self._key = _resolve_key(key)
    49	        # High-water mark sidecar (F13 / re-scan H2): records the entry count and
    50	        # last hash so tail-truncation or whole-file deletion is detectable — a
    51	        # plain hash chain stays internally valid after its newest entries are
    52	        # removed. MAC'd with the audit key when keyed.
    53	        self._hwm_path = state_dir / "audit.hwm"
    54	
    55	    def append(self, entry: AuditEntry) -> AuditEntry:
    56	        # Exclusive lock on a sidecar file guards the read-last-hash + write as one
    57	        # atomic unit across threads and processes, preventing audit-chain forks.
    58	        lock_path = self.path.with_suffix(".lock")
    59	        with lock_path.open("w") as lock_file:
    60	            fcntl.flock(lock_file, fcntl.LOCK_EX)
    61	            prev_hash = self._last_hash()
    62	            entry.prev_hash = prev_hash
    63	            entry_dict = entry.to_dict()
    64	            entry.current_hash = _hash_entry(entry_dict, prev_hash, self._key)
    65	            count = self._count_lines() + 1
    66	            with self.path.open("a") as f:
    67	                f.write(entry.to_json() + "\n")
    68	            self._write_hwm(count, entry.current_hash)
    69	        return entry
    70	
    71	    def _count_lines(self) -> int:
    72	        if not self.path.exists():
    73	            return 0
    74	        return sum(1 for ln in self.path.read_text().splitlines() if ln.strip())
    75	
    76	    def _hwm_mac(self, count: int, last_hash: str) -> str:
    77	        canon = f"{count}:{last_hash}".encode()
    78	        if self._key:
    79	            return hmac.new(self._key, canon, hashlib.sha256).hexdigest()
    80	        return hashlib.sha256(canon).hexdigest()
    81	
    82	    def _write_hwm(self, count: int, last_hash: str) -> None:
    83	        payload = {"count": count, "last_hash": last_hash, "mac": self._hwm_mac(count, last_hash)}
    84	        tmp = self._hwm_path.with_suffix(".hwm.tmp")
    85	        tmp.write_text(json.dumps(payload))
    86	        os.replace(tmp, self._hwm_path)
    87	
    88	    def _read_hwm(self) -> dict | None:
    89	        if not self._hwm_path.exists():
    90	            return None
    91	        try:
    92	            return json.loads(self._hwm_path.read_text())
    93	        except Exception:
    94	            return None
    95	
    96	    def verify(self) -> bool:
    97	        """Verify chain integrity AND completeness against the high-water mark.
    98	
    99	        Returns False if any link is tampered (as ``verify_chain``) OR if the
   100	        chain is shorter than the recorded high-water mark, its last hash does
   101	        not match, or the HWM's own MAC is invalid (truncation / deletion).
   102	        A chain with no HWM sidecar (legacy) is verified by chain links only.
   103	        """
   104	        entries = self.load_chain()
   105	        if not verify_chain(entries, key=self._key):
   106	            return False
   107	        hwm = self._read_hwm()
   108	        if hwm is None:
   109	            return True
   110	        count = int(hwm.get("count", 0))
   111	        last_hash = str(hwm.get("last_hash", ""))
   112	        if not hmac.compare_digest(str(hwm.get("mac", "")), self._hwm_mac(count, last_hash)):
   113	            return False
   114	        if len(entries) < count:
   115	            return False
   116	        if count > 0 and entries[count - 1].current_hash != last_hash:
   117	            return False
   118	        return True
   119	
   120	    def _last_hash(self) -> str:
   121	        if not self.path.exists():
   122	            return ""
   123	        lines = [ln.strip() for ln in self.path.read_text().splitlines() if ln.strip()]
   124	        if not lines:
   125	            return ""
   126	        try:
   127	            return json.loads(lines[-1]).get("current_hash", "")
   128	        except Exception:
   129	            return ""
   130	
   131	    def load_chain(self) -> list[AuditEntry]:
   132	        if not self.path.exists():
   133	            return []
   134	        entries: list[AuditEntry] = []
   135	        for line in self.path.read_text().splitlines():
   136	            stripped = line.strip()
   137	            if stripped:
   138	                try:
   139	                    entries.append(AuditEntry.from_dict(json.loads(stripped)))
   140	                except Exception:
   141	                    continue
   142	        return entries
   143	
   144	
   145	def verify_chain(entries: list[AuditEntry], *, key: str | bytes | None = None) -> bool:
   146	    """Return True if the hash chain is intact, False if any entry was tampered.
   147	
   148	    When *key* is provided (or ``ODOOCTL_AUDIT_KEY`` is set), links are
   149	    verified as HMAC-SHA256 with that key; a chain rehashed without the key
   150	    fails verification.
   151	    """
   152	    resolved = _resolve_key(key)
   153	    prev_hash = ""
   154	    for entry in entries:
   155	        if entry.prev_hash != prev_hash:
   156	            return False
   157	        expected = _hash_entry(entry.to_dict(), prev_hash, resolved)
   158	        if entry.current_hash != expected:
   159	            return False
   160	        prev_hash = entry.current_hash
   161	    return True
     1	"""FastAPI application factory for the odooctl local API.
     2	
     3	Create the app with ``create_app(api_key=..., registry_loader=...)`` and
     4	hand it to uvicorn. By default the app binds to localhost-only via
     5	``TrustedHostMiddleware``.
     6	
     7	Optional static SPA: pass ``static_dir`` pointing to a pre-built SPA dist
     8	directory and it will be mounted at ``/`` (served as a fallback after API
     9	routes). The SPA fallback ``index.html`` is read once at app creation and
    10	served from memory for the lifetime of the process; ``odooctl serve`` is a
    11	long-running process, so after rebuilding the SPA dist, restart the server
    12	to pick up a new ``index.html``.
    13	
    14	No privileged imports — satisfies the runner contract.
    15	"""
    16	from __future__ import annotations
    17	
    18	from pathlib import Path
    19	from typing import Callable
    20	
    21	from fastapi import FastAPI
    22	from fastapi.middleware.trustedhost import TrustedHostMiddleware
    23	
    24	from odooctl.api.routes_operations import router as operations_router
    25	from odooctl.api.routes_projects import router as projects_router
    26	from odooctl.security import tokens
    27	
    28	
    29	def create_app(
    30	    api_key: str,
    31	    *,
    32	    registry_loader: Callable | None = None,
    33	    allowed_hosts: list[str] | None = None,
    34	    extra_allowed_hosts: list[str] | None = None,
    35	    static_dir: Path | None = None,
    36	) -> FastAPI:
    37	    """Create and configure the odooctl FastAPI application.
    38	
    39	    :param api_key: Shared HMAC key used to verify bearer tokens.
    40	    :param registry_loader: Callable returning a ``Registry``; defaults to
    41	        ``odooctl.registry.load_registry`` so tests can inject a fake.
    42	    :param allowed_hosts: Hosts allowed by ``TrustedHostMiddleware``; defaults
    43	        to ``["127.0.0.1", "localhost"]`` for localhost-only operation.
    44	    :param extra_allowed_hosts: Additional hosts appended to the default set
    45	        (e.g. tests pass ``["testclient"]``); ignored when ``allowed_hosts`` is
    46	        given explicitly.
    47	    :param static_dir: Optional path to a pre-built SPA dist directory mounted
    48	        at ``/`` after all API routes.
    49	    """
    50	    # Key-strength floor (F24): a short HMAC key makes bearer/capability tokens
    51	    # brute-forceable, so it is rejected unconditionally regardless of how the
    52	    # key reached us. This is the primary defense; ``get_principal`` re-checks
    53	    # as a backstop.
    54	    tokens.enforce_key_strength(api_key)
    55	
    56	    if registry_loader is None:
    57	        from odooctl.registry import load_registry
    58	
    59	        registry_loader = load_registry
    60	
    61	    app = FastAPI(
    62	        title="odooctl API",
    63	        description="Local management API for self-hosted Odoo deployments.",
    64	        version="1.0.0",
    65	    )
    66	
    67	    app.state.api_key = api_key
    68	    app.state.registry_loader = registry_loader
    69	
    70	    if allowed_hosts is None:
    71	        # Localhost-only by default. "testclient" (the Starlette TestClient
    72	        # default Host) is deliberately NOT in the production default; tests
    73	        # opt in via extra_allowed_hosts.
    74	        allowed_hosts = ["127.0.0.1", "localhost"]
    75	        if extra_allowed_hosts:
    76	            allowed_hosts = [*allowed_hosts, *extra_allowed_hosts]
    77	
    78	    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    79	
    80	    app.include_router(projects_router)
    81	    app.include_router(operations_router)
    82	
    83	    if static_dir is not None and Path(static_dir).exists():
    84	        from fastapi.responses import FileResponse, HTMLResponse
    85	
    86	        _static = Path(static_dir).resolve()
    87	        # Cache the SPA fallback index.html bytes at startup instead of
    88	        # re-reading the file on every request. Rebuilding the SPA dist
    89	        # requires a server restart to pick up a new index.html.
    90	        _index_bytes = (_static / "index.html").read_bytes()
    91	
    92	        @app.get("/{full_path:path}", include_in_schema=False)
    93	        async def _spa(full_path: str):
    94	            candidate = (_static / full_path).resolve()
    95	            try:
    96	                candidate.relative_to(_static)
    97	            except ValueError:
    98	                return HTMLResponse(_index_bytes)
    99	            if candidate.is_file():
   100	                return FileResponse(str(candidate))
   101	            return HTMLResponse(_index_bytes)
   102	
   103	    return app

 succeeded in 36209ms:
../Atabe/turpo-repo/AGENTS.md
../atabe_crm/api/AGENTS.md
../atabe_crm/crm-dashboard/AGENTS.md
../atabe_crm/whatsapp-gateway/AGENTS.md
../atabe_crm/shared-types/AGENTS.md
../atabe_crm/AGENTS.md
../atabe_crm/infra/AGENTS.md
../new_crm/whatsapp-gateway/AGENTS.md
../advokit/advokit_v2/.claude/skills/ui-design/AGENTS.md
../advokit/advokit_v2/.agents/skills/ui-design/AGENTS.md
../advokit/AGENTS.md
../.hermes/hermes-agent/AGENTS.md
../.hermes/profiles/odoo-reviewer/home/.codex/.tmp/plugins-clone-SGXGNs/plugins/build-web-apps/skills/react-best-practices/AGENTS.md
../.hermes/profiles/odoo-reviewer/home/.codex/.tmp/plugins-clone-SGXGNs/plugins/build-web-apps/skills/supabase-best-practices/AGENTS.md
../.hermes/profiles/odoo-reviewer/home/.codex/.tmp/plugins-clone-SGXGNs/plugins/zoom/AGENTS.md
../.vscode-server/extensions/repreng.csv-1.3.0/AGENTS.md
../.codex/.tmp/plugins/plugins/build-web-apps/skills/react-best-practices/AGENTS.md
../.codex/.tmp/plugins/plugins/build-web-apps/skills/supabase-best-practices/AGENTS.md
../.codex/.tmp/plugins/plugins/zoom/AGENTS.md
../atabe_CRM_Sales/apps/web/AGENTS.md
../atabe_CRM_Sales/apps/backend/node_modules/ts-loader/AGENTS.md
../atabe_CRM_Sales/AGENTS.md

exec
/bin/bash -lc 'nl -ba odooctl/services/restore.py; nl -ba odooctl/services/deploy.py; nl -ba odooctl/services/clone.py; nl -ba odooctl/config.py' in /home/dev/odooctl
 succeeded in 0ms:
     1	"""Restore service — validate and apply backup archives."""
     2	from __future__ import annotations
     3	
     4	import hashlib
     5	import json
     6	from pathlib import Path
     7	from typing import TYPE_CHECKING
     8	
     9	from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
    10	from odooctl.adapters.filestore import FilestoreAdapter, make_filestore_adapter
    11	from odooctl.adapters.postgres import PostgresAdapter
    12	from odooctl.adapters.reverse_proxy import public_url
    13	from odooctl.odoo.healthcheck import check_url, with_db_selector
    14	from odooctl.odoo.sanitize import sanitize_database
    15	from odooctl.services.models import RestoreResult
    16	
    17	if TYPE_CHECKING:
    18	    from odooctl.services.context import ServiceContext
    19	
    20	REQUIRED_BACKUP_FILES = ("db.dump", "filestore.tar", "manifest.json")
    21	
    22	
    23	def sha256_file(path: Path) -> str:
    24	    digest = hashlib.sha256()
    25	    with path.open("rb") as handle:
    26	        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
    27	            digest.update(chunk)
    28	    return digest.hexdigest()
    29	
    30	
    31	def resolve_backup_dir(environment: str, backup: str, backups_root: Path) -> Path:
    32	    """Resolve a backup id to a directory strictly inside *backups_root*.
    33	
    34	    Path containment (audit finding F10): *backup* is client-suppliable (CLI
    35	    argument, API/runner params), so a hostile id like ``../../etc`` must never
    36	    escape the backups root. Backup ids are plain directory names (e.g.
    37	    ``staging_2026-01-02_000000``); anything containing a path separator or
    38	    ``..`` is rejected outright, and the joined path is resolved and required
    39	    to remain inside ``backups_root.resolve()`` (defense-in-depth against
    40	    symlink tricks).
    41	    """
    42	    if backup != "latest":
    43	        if (
    44	            not backup
    45	            or "/" in backup
    46	            or "\\" in backup
    47	            or ".." in backup
    48	            or backup == "."
    49	        ):
    50	            raise ValueError(
    51	                f"Invalid backup id {backup!r}: backup ids are plain directory names "
    52	                "and must not contain path separators or '..'"
    53	            )
    54	        root = backups_root.resolve()
    55	        candidate = (root / backup).resolve()
    56	        if candidate == root or not candidate.is_relative_to(root):
    57	            raise ValueError(
    58	                f"Invalid backup id {backup!r}: resolved path {candidate} "
    59	                f"escapes the backups root {root}"
    60	            )
    61	        return candidate
    62	    candidates = sorted(backups_root.glob(f"{environment}_*"))
    63	    if not candidates:
    64	        raise RuntimeError(f"No backups found for environment: {environment}")
    65	    return candidates[-1]
    66	
    67	
    68	def validate_backup_dir(
    69	    backup_dir: Path,
    70	    *,
    71	    expected_project: str | None = None,
    72	    expected_environment: str | None = None,
    73	    restore_mode: str = "full",
    74	) -> dict:
    75	    if not backup_dir.exists() or not backup_dir.is_dir():
    76	        raise FileNotFoundError(f"Backup directory does not exist: {backup_dir}")
    77	    missing = [name for name in REQUIRED_BACKUP_FILES if not (backup_dir / name).exists()]
    78	    if missing:
    79	        raise FileNotFoundError(f"Backup is missing required file(s): {', '.join(missing)}")
    80	    manifest = json.loads((backup_dir / "manifest.json").read_text())
    81	    if expected_project and manifest.get("project") != expected_project:
    82	        raise RuntimeError(
    83	            f"Backup project mismatch: expected {expected_project}, got {manifest.get('project')}"
    84	        )
    85	    if expected_environment and manifest.get("environment") != expected_environment:
    86	        raise RuntimeError(
    87	            f"Backup environment mismatch: expected {expected_environment}, got {manifest.get('environment')}"
    88	        )
    89	    if restore_mode == "full" and manifest.get("backup_mode", "full") != "full":
    90	        raise RuntimeError(f"Unsupported backup mode for full restore: {manifest.get('backup_mode')}")
    91	    checksums = manifest.get("checksums") or {}
    92	    for key, file_name in (("db_dump", "db.dump"), ("filestore", "filestore.tar")):
    93	        expected = checksums.get(key)
    94	        if not expected:
    95	            raise RuntimeError(f"Backup manifest is missing checksum for {file_name}")
    96	        if sha256_file(backup_dir / file_name) != expected:
    97	            raise RuntimeError(f"Backup checksum mismatch for {file_name}")
    98	    return manifest
    99	
   100	
   101	def restore_to_env(
   102	    *,
   103	    source_environment: str,
   104	    target_environment: str,
   105	    backup: str = "latest",
   106	    ctx: "ServiceContext",
   107	) -> RestoreResult:
   108	    """Restore a backup from *source_environment* into *target_environment*.
   109	
   110	    Uses a safe staging flow: restore into a temp DB first, then atomically
   111	    swap/rename it into the target DB name. The target environment must not be
   112	    protected. The source backup is validated (checksums) but environment-mismatch
   113	    check is intentionally skipped so a production backup can be restored into staging.
   114	    """
   115	    from odooctl.odoo.db_swap import swap_temp_database
   116	
   117	    cfg = ctx.project.config
   118	
   119	    if cfg.is_protected(target_environment):
   120	        raise RuntimeError(
   121	            f"Cannot restore into protected environment {target_environment!r}. "
   122	            "Use a non-production target (e.g. staging)."
   123	        )
   124	
   125	    env = cfg.env(target_environment)
   126	    source_is_protected = cfg.is_protected(source_environment)
   127	    if source_is_protected and not env.sanitize:
   128	        raise RuntimeError(
   129	            f"Refusing to restore protected-environment backup ({source_environment!r}) "
   130	            f"into {target_environment!r} without sanitization. "
   131	            "Set sanitize: true on the target environment."
   132	        )
   133	
   134	    backup_dir = resolve_backup_dir(source_environment, backup, ctx.project.backups_dir)
   135	    # Validate checksums but skip environment-mismatch check (cross-env restore)
   136	    validate_backup_dir(backup_dir, expected_project=cfg.project.name)
   137	
   138	    temp_db = env.db_name + cfg.sanitization.temp_db_suffix
   139	
   140	    pg = make_context_db_adapter(ctx.project) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
   141	    # Restore into temp DB, not the live target DB
   142	    pg.restore(temp_db, backup_dir / "db.dump")
   143	
   144	    target_filestore = env.filestore_path if env.filestore_volume else str(ctx.project.resolve_path(env.filestore_path))
   145	    fs = make_filestore_adapter(ctx.project, env) if env.filestore_volume else FilestoreAdapter()
   146	    fs.restore_archive(backup_dir / "filestore.tar", target_filestore)
   147	
   148	    # Mirror clone safety contract: sanitize temp DB before swap when source is protected
   149	    if source_is_protected:
   150	        sanitize_database(pg, temp_db, env, cfg, sql_files=ctx.project.sanitization_sql_files())
   151	
   152	    # Atomically promote temp DB into the target DB name
   153	    swap_temp_database(pg, temp_db=temp_db, target_db=env.db_name, target_env_name=target_environment)
   154	
   155	    scheme = cfg.healthcheck.scheme or env.scheme
   156	    url = with_db_selector(
   157	        public_url(env.domain, scheme=scheme, port=env.port) + cfg.healthcheck.path,
   158	        env.db_name if env.db_selector else None,
   159	    )
   160	    check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
   161	    return RestoreResult(backup_id=backup_dir.name)
   162	
   163	
   164	def run_restore(ctx: ServiceContext, environment: str, backup: str = "latest") -> RestoreResult:
   165	    """Restore *environment* from one of its own backups.
   166	
   167	    Verify-before-destroy: the dump is restored into a temp database first,
   168	    so a corrupt or failing restore never destroys the live database. Only
   169	    after pg_restore succeeds is the temp DB swapped into place.
   170	    """
   171	    from odooctl.odoo.db_swap import swap_temp_database
   172	
   173	    cfg = ctx.project.config
   174	    env = cfg.env(environment)
   175	    backup_dir = resolve_backup_dir(environment, backup, ctx.project.backups_dir)
   176	    validate_backup_dir(backup_dir, expected_project=cfg.project.name, expected_environment=environment, restore_mode="full")
   177	    pg = make_context_db_adapter(ctx.project) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
   178	    temp_db = env.db_name + cfg.sanitization.temp_db_suffix
   179	    pg.restore(temp_db, backup_dir / "db.dump")
   180	    target_filestore = env.filestore_path if env.filestore_volume else str(ctx.project.resolve_path(env.filestore_path))
   181	    fs = make_filestore_adapter(ctx.project, env) if env.filestore_volume else FilestoreAdapter()
   182	    fs.restore_archive(backup_dir / "filestore.tar", target_filestore)
   183	    # Same-environment recovery may target a protected env by design; the CLI
   184	    # confirmation gate (--yes) is the policy layer for this path.
   185	    swap_temp_database(pg, temp_db=temp_db, target_db=env.db_name, target_env_name=environment)
   186	    scheme = cfg.healthcheck.scheme or env.scheme
   187	    url = with_db_selector(
   188	        public_url(env.domain, scheme=scheme, port=env.port) + cfg.healthcheck.path,
   189	        env.db_name if env.db_selector else None,
   190	    )
   191	    check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
   192	    return RestoreResult(backup_id=backup_dir.name)
     1	"""Deploy service — orchestrate git pull, compose update, module update, and health check."""
     2	from __future__ import annotations
     3	
     4	from pathlib import Path
     5	from typing import TYPE_CHECKING
     6	
     7	from odooctl.adapters.docker_compose import DockerComposeAdapter
     8	from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
     9	from odooctl.adapters.postgres import PostgresAdapter
    10	from odooctl.adapters.reverse_proxy import public_url
    11	from odooctl.metadata.models import DeploymentMetadata
    12	from odooctl.metadata.store import MetadataStore
    13	from odooctl.odoo.healthcheck import check_url, with_db_selector
    14	from odooctl.odoo.module_update import update_modules_compose
    15	from odooctl.services.backup import git_commit, run_backup as backup_execute
    16	from odooctl.services.models import DeployResult
    17	from odooctl.utils.shell import run
    18	
    19	if TYPE_CHECKING:
    20	    from odooctl.services.context import ServiceContext
    21	
    22	
    23	def _assert_clean_worktree(operation: str = "deploy", *, cwd: str | Path | None = None) -> None:
    24	    result = run(["git", "status", "--porcelain"], check=False, cwd=str(cwd) if cwd is not None else None)
    25	    dirty_paths = result.stdout.strip()
    26	    if dirty_paths:
    27	        raise RuntimeError(
    28	            f"Git worktree is dirty; commit or stash changes before {operation}:\n{dirty_paths}"
    29	        )
    30	
    31	
    32	def run_deploy(ctx: ServiceContext, environment: str, branch: str | None = None) -> DeployResult:
    33	    print("[deploy] preflight")
    34	    cfg = ctx.project.config
    35	    missing_env_vars = cfg.missing_env_vars()
    36	    if missing_env_vars:
    37	        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env_vars)}")
    38	    env = cfg.env(environment)
    39	    selected_branch = branch or env.branch
    40	    if branch and branch != env.branch:
    41	        raise RuntimeError(f"Branch '{branch}' is not allowed for environment '{environment}'")
    42	    compose_path = ctx.project.compose_file
    43	    if not compose_path.exists():
    44	        raise FileNotFoundError(f"Compose file not found: {compose_path}")
    45	    filestore_path = ctx.project.resolve_path(env.filestore_path)
    46	    if not filestore_path.exists():
    47	        raise FileNotFoundError(f"Target filestore path not found: {filestore_path}")
    48	    try:
    49	        pg = (
    50	            make_context_db_adapter(ctx.project)
    51	            if cfg.runtime.execution_mode == "docker"
    52	            else PostgresAdapter(cfg.postgres)
    53	        )
    54	        pg.ping(env.db_name)
    55	    except Exception as exc:
    56	        raise RuntimeError(
    57	            f"Postgres connectivity check failed for database '{env.db_name}' "
    58	            f"on {cfg.postgres.host}:{cfg.postgres.port}: {exc}"
    59	        ) from exc
    60	    _assert_clean_worktree(cwd=ctx.project.root)
    61	
    62	    scheme = cfg.healthcheck.scheme or env.scheme
    63	    url = with_db_selector(
    64	        public_url(env.domain, scheme=scheme, port=env.port) + cfg.healthcheck.path,
    65	        env.db_name if env.db_selector else None,
    66	    )
    67	    compose = DockerComposeAdapter(cfg.runtime.compose_file, project_dir=str(ctx.project.root))
    68	    backup_id = None
    69	    status = "failed"
    70	    message = None
    71	    db_mutation_possible = False
    72	    try:
    73	        if cfg.is_protected(environment):
    74	            print("[deploy] backup")
    75	            backup_result = backup_execute(ctx, environment)
    76	            backup_id = backup_result.backup_id
    77	        print("[deploy] rollout")
    78	        run(["git", "fetch", "--all"], stream=True, cwd=str(ctx.project.root))
    79	        run(["git", "checkout", selected_branch], stream=True, cwd=str(ctx.project.root))
    80	        run(["git", "pull", "--ff-only"], stream=True, cwd=str(ctx.project.root))
    81	        compose.pull(cfg.odoo.service)
    82	        compose.up(cfg.odoo.service)
    83	        db_mutation_possible = True
    84	        update_modules_compose(
    85	            compose,
    86	            cfg.odoo.service,
    87	            env.db_name,
    88	            env.update_modules,
    89	            db_host=cfg.odoo.db_host,
    90	            db_user=cfg.odoo.db_user,
    91	            db_password_env=cfg.odoo.db_password_env,
    92	            config_path=cfg.odoo.config_path,
    93	        )
    94	        print("[deploy] verify")
    95	        check_url(
    96	            url,
    97	            timeout=cfg.healthcheck.timeout_seconds,
    98	            retries=cfg.healthcheck.retries,
    99	            interval=cfg.healthcheck.interval_seconds,
   100	        )
   101	        status = "success"
   102	        print("[deploy] done")
   103	    except Exception as exc:
   104	        message = str(exc)
   105	        if cfg.is_protected(environment):
   106	            recovery_notes = []
   107	            if backup_id is not None and db_mutation_possible:
   108	                try:
   109	                    from odooctl.services.restore import run_restore
   110	
   111	                    run_restore(ctx, environment, backup=backup_id)
   112	                    recovery_notes.append(f"database restored from pre-deploy backup {backup_id}")
   113	                except Exception as restore_exc:
   114	                    recovery_notes.append(
   115	                        f"pre-deploy backup restore FAILED ({restore_exc}); "
   116	                        f"restore manually from backup {backup_id}"
   117	                    )
   118	            try:
   119	                compose.restart(cfg.odoo.service)
   120	            except Exception as recovery_exc:
   121	                recovery_notes.append(f"recovery restart failed: {recovery_exc}")
   122	            if recovery_notes:
   123	                message = f"{message}; " + "; ".join(recovery_notes)
   124	        raise
   125	    finally:
   126	        MetadataStore(ctx.project.state_dir).save_deployment(
   127	            DeploymentMetadata(
   128	                project=cfg.project.name,
   129	                environment=environment,
   130	                branch=selected_branch,
   131	                commit=git_commit(ctx.project.root),
   132	                docker_image=cfg.odoo.image,
   133	                backup=backup_id,
   134	                modules_updated=env.update_modules,
   135	                status=status,
   136	                health_check_url=url,
   137	                message=message,
   138	            )
   139	        )
   140	    return DeployResult(environment=environment, backup_id=backup_id, status=status)
     1	"""Clone service — copy production data to a target environment with sanitization."""
     2	from __future__ import annotations
     3	
     4	import tempfile
     5	from pathlib import Path
     6	from typing import TYPE_CHECKING
     7	
     8	from odooctl.adapters.docker_compose import DockerComposeAdapter
     9	from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
    10	from odooctl.adapters.filestore import FilestoreAdapter, make_filestore_adapter
    11	from odooctl.adapters.postgres import PostgresAdapter
    12	from odooctl.adapters.reverse_proxy import public_url
    13	from odooctl.odoo.db_swap import swap_temp_database
    14	from odooctl.odoo.healthcheck import check_url, with_db_selector
    15	from odooctl.odoo.module_update import update_modules_compose
    16	from odooctl.odoo.sanitize import sanitize_database
    17	from odooctl.services.models import CloneResult
    18	
    19	if TYPE_CHECKING:
    20	    from odooctl.services.context import ServiceContext
    21	
    22	
    23	def run_clone(
    24	    ctx: ServiceContext,
    25	    source: str,
    26	    target: str,
    27	    sanitize: bool | None = True,
    28	    sanitization_profile: str = "normal",
    29	    preview: bool = False,
    30	) -> CloneResult:
    31	    cfg = ctx.project.config
    32	    src = cfg.env(source)
    33	    dst = cfg.env(target)
    34	    if not dst.clone_from:
    35	        raise RuntimeError(
    36	            f"Environment '{target}' is not configured as a clone target; set clone_from before cloning into it"
    37	        )
    38	    if dst.clone_from != source:
    39	        raise RuntimeError(f"Environment '{target}' must be cloned from '{dst.clone_from}', not '{source}'")
    40	    should_sanitize = dst.sanitize if sanitize is None else sanitize
    41	    if cfg.is_protected(source) and not should_sanitize:
    42	        raise RuntimeError("Refusing to clone protected environment data without sanitization enabled")
    43	
    44	    compose_path = ctx.project.compose_file
    45	    if not compose_path.exists():
    46	        raise FileNotFoundError(f"Compose file not found: {compose_path}")
    47	
    48	    scheme = cfg.healthcheck.scheme or dst.scheme
    49	    base_url = public_url(dst.domain, scheme=scheme, port=dst.port)
    50	
    51	    if preview:
    52	        print("[clone] preview")
    53	        print(
    54	            f"source={source} target={target} profile={sanitization_profile} "
    55	            f"base_url={base_url} sanitize={'yes' if should_sanitize else 'no'}"
    56	        )
    57	        print(f"source_branch={src.branch} target_branch={dst.branch} clone_from={dst.clone_from}")
    58	        print(f"affected_integrations={','.join(dst.update_modules) or 'none'}")
    59	        print(f"production_source={'yes' if cfg.is_protected(source) else 'no'}")
    60	        return CloneResult(url=base_url)
    61	
    62	    missing_env_vars = cfg.missing_env_vars()
    63	    if missing_env_vars:
    64	        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env_vars)}")
    65	
    66	    pg = make_context_db_adapter(ctx.project) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
    67	    fs = make_filestore_adapter(ctx.project, dst) if dst.filestore_volume else FilestoreAdapter()
    68	    temp_db = f"{dst.db_name}{cfg.sanitization.temp_db_suffix}"
    69	    if temp_db == dst.db_name:
    70	        raise RuntimeError(
    71	            "Configured sanitization.temp_db_suffix must produce a temporary database distinct from the target"
    72	        )
    73	    if hasattr(pg, "clone_db_in_container"):
    74	        pg.clone_db_in_container(src.db_name, temp_db)  # type: ignore[attr-defined]
    75	    else:
    76	        with tempfile.NamedTemporaryFile(prefix="odooctl-clone-", suffix=".dump", delete=False) as tmp:
    77	            tmp_dump = Path(tmp.name)
    78	        try:
    79	            pg.dump(src.db_name, tmp_dump)
    80	            pg.restore(temp_db, tmp_dump)
    81	        finally:
    82	            tmp_dump.unlink(missing_ok=True)
    83	    src_filestore = src.filestore_path if src.filestore_volume else str(ctx.project.resolve_path(src.filestore_path))
    84	    dst_filestore = dst.filestore_path if dst.filestore_volume else str(ctx.project.resolve_path(dst.filestore_path))
    85	    fs.copy(src_filestore, dst_filestore)
    86	    if should_sanitize:
    87	        sanitize_database(pg, temp_db, dst, cfg, sanitization_profile, sql_files=ctx.project.sanitization_sql_files())
    88	    swap_temp_database(
    89	        pg,
    90	        temp_db=temp_db,
    91	        target_db=dst.db_name,
    92	        target_env_name=target,
    93	        is_protected_fn=cfg.is_protected,
    94	    )
    95	    compose = DockerComposeAdapter(cfg.runtime.compose_file, project_dir=str(ctx.project.root))
    96	    update_modules_compose(
    97	        compose,
    98	        cfg.odoo.service,
    99	        dst.db_name,
   100	        dst.update_modules,
   101	        db_host=cfg.odoo.db_host,
   102	        db_user=cfg.odoo.db_user,
   103	        db_password_env=cfg.odoo.db_password_env,
   104	        config_path=cfg.odoo.config_path,
   105	    )
   106	    compose.restart(cfg.odoo.service)
   107	    running_services = compose.ps()
   108	    if cfg.odoo.service not in running_services:
   109	        raise RuntimeError(f"Target service is not running after clone: {cfg.odoo.service}")
   110	    url = with_db_selector(base_url + cfg.healthcheck.path, dst.db_name if dst.db_selector else None)
   111	    check_url(
   112	        url,
   113	        timeout=cfg.healthcheck.timeout_seconds,
   114	        retries=cfg.healthcheck.retries,
   115	        interval=cfg.healthcheck.interval_seconds,
   116	    )
   117	    return CloneResult(url=base_url)
     1	from __future__ import annotations
     2	
     3	import os
     4	import re
     5	from pathlib import Path
     6	from typing import Literal
     7	
     8	import yaml
     9	import click
    10	from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator
    11	
    12	# Defense-in-depth input validation (audit findings C3/F8). These values flow
    13	# into subprocess argv, container paths, docker volume names, and Traefik YAML,
    14	# so they are constrained at the config boundary even though shell sinks were
    15	# already removed.
    16	IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    17	IDENTIFIER_MAX_LENGTH = 64
    18	_IDENTIFIER_RE = re.compile(IDENTIFIER_PATTERN)
    19	
    20	HOSTNAME_PATTERN = r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?)*$"
    21	HOSTNAME_MAX_LENGTH = 253
    22	_HOSTNAME_RE = re.compile(HOSTNAME_PATTERN)
    23	
    24	
    25	def _redacted(value: object) -> str:
    26	    return str(value)[:32]
    27	
    28	
    29	def validate_identifier(value: str, field_name: str) -> str:
    30	    """Validate a docker/compose/database identifier; return it unchanged.
    31	
    32	    Raises ValueError when *value* is not a safe identifier (alphanumeric
    33	    start, then alphanumerics/dots/underscores/hyphens, no '..', max 64 chars).
    34	    """
    35	    if (
    36	        not isinstance(value, str)
    37	        or len(value) > IDENTIFIER_MAX_LENGTH
    38	        or ".." in value
    39	        or not _IDENTIFIER_RE.fullmatch(value)
    40	    ):
    41	        raise ValueError(
    42	            f"{field_name} {_redacted(value)!r} is invalid: must match {IDENTIFIER_PATTERN} "
    43	            f"with no '..', max {IDENTIFIER_MAX_LENGTH} characters"
    44	        )
    45	    return value
    46	
    47	
    48	def validate_hostname(value: str, field_name: str) -> str:
    49	    """Validate a DNS hostname; return it normalized to lowercase.
    50	
    51	    Raises ValueError when *value* is not a valid DNS hostname (labels of
    52	    alphanumerics and hyphens, dot-separated, max 253 chars; no wildcards).
    53	    """
    54	    normalized = value.lower() if isinstance(value, str) else value
    55	    if (
    56	        not isinstance(normalized, str)
    57	        or len(normalized) > HOSTNAME_MAX_LENGTH
    58	        or not _HOSTNAME_RE.fullmatch(normalized)
    59	    ):
    60	        raise ValueError(
    61	            f"{field_name} {_redacted(value)!r} is invalid: must be a valid DNS hostname "
    62	            f"matching {HOSTNAME_PATTERN}, max {HOSTNAME_MAX_LENGTH} characters"
    63	        )
    64	    return normalized
    65	
    66	
    67	class ProjectConfig(BaseModel):
    68	    name: str = "my-odoo-project"
    69	    odoo_version: str = "19.0"
    70	
    71	
    72	class RuntimeConfig(BaseModel):
    73	    type: Literal["docker_compose"] = "docker_compose"
    74	    compose_file: str = "docker-compose.yml"
    75	    reverse_proxy: str = "traefik"
    76	    execution_mode: Literal["docker", "host"] = "host"
    77	
    78	
    79	class EnvironmentConfig(BaseModel):
    80	    stack: str = "default"
    81	    tier: Literal["production", "staging", "development", "qa"] | None = None
    82	    protected: bool | None = None
    83	    branch: str
    84	    scheme: Literal["http", "https"] = "https"
    85	    domain: str
    86	    port: int | None = None
    87	    db_name: str
    88	    filestore_path: str
    89	    filestore_volume: str | None = None
    90	    db_selector: bool = False
    91	    clone_from: str | None = None
    92	    sanitize: bool = False
    93	    update_modules: list[str] = Field(default_factory=list)
    94	    promotes_to: str | None = None
    95	    auto_deploy: bool = False
    96	    last_deployed_commit: str | None = None
    97	
    98	    @field_validator("db_name", "filestore_volume")
    99	    @classmethod
   100	    def identifier_fields_must_be_safe(cls, value: str | None, info: ValidationInfo) -> str | None:
   101	        if value is None:
   102	            return value
   103	        return validate_identifier(value, info.field_name)
   104	
   105	    @field_validator("domain")
   106	    @classmethod
   107	    def domain_must_be_valid_hostname(cls, value: str, info: ValidationInfo) -> str:
   108	        return validate_hostname(value, info.field_name)
   109	
   110	    @field_validator("filestore_path")
   111	    @classmethod
   112	    def filestore_path_must_be_safe(cls, value: str, info: ValidationInfo) -> str:
   113	        # ``filestore_path`` reaches ``rm -rf``/``shutil.rmtree``/``cp -a`` and,
   114	        # for the Docker backend, is reduced to its basename. A value with an
   115	        # empty basename (``/``, trailing slash only) or ``..`` components can
   116	        # target the filestore root or escape it. Accept both relative
   117	        # (``filestore/odoo_prod``) and absolute (``/var/lib/odoo/...``) paths.
   118	        from pathlib import PurePosixPath
   119	
   120	        display = str(value)[:64]
   121	        if not value or not value.strip():
   122	            raise ValueError(f"{info.field_name} must not be empty")
   123	        parts = PurePosixPath(value).parts
   124	        if ".." in parts:
   125	            raise ValueError(
   126	                f"{info.field_name} {display!r} must not contain '..' path segments"
   127	            )
   128	        if not PurePosixPath(value).name:
   129	            raise ValueError(
   130	                f"{info.field_name} {display!r} must reference a named directory, not a root path"
   131	            )
   132	        return value
   133	
   134	
   135	class PostgresConfig(BaseModel):
   136	    host: str = "localhost"
   137	    port: int = 5432
   138	    user: str = "odoo"
   139	    password_env: str = "ODOO_DB_PASSWORD"
   140	    service: str = "postgres"
   141	    internal_host: str | None = None
   142	    service_user: str | None = None
   143	    service_password_env: str | None = None
   144	
   145	    @field_validator("service")
   146	    @classmethod
   147	    def service_must_be_safe(cls, value: str, info: ValidationInfo) -> str:
   148	        return validate_identifier(value, info.field_name)
   149	
   150	    @model_validator(mode="after")
   151	    def fill_container_defaults(self) -> "PostgresConfig":
   152	        if self.internal_host is None:
   153	            self.internal_host = self.service
   154	        if self.service_user is None:
   155	            self.service_user = self.user
   156	        if self.service_password_env is None:
   157	            self.service_password_env = self.password_env
   158	        return self
   159	
   160	    def password(self) -> str:
   161	        value = os.getenv(self.password_env)
   162	        if not value:
   163	            raise RuntimeError(f"Missing required environment variable: {self.password_env}")
   164	        return value
   165	
   166	    def service_password(self) -> str:
   167	        env_name = self.service_password_env or self.password_env
   168	        value = os.getenv(env_name)
   169	        if not value:
   170	            raise RuntimeError(f"Missing required environment variable: {env_name}")
   171	        return value
   172	
   173	
   174	class OdooConfig(BaseModel):
   175	    image: str
   176	    config_path: str = "/etc/odoo/odoo.conf"
   177	    addons_paths: list[str] = Field(default_factory=list)
   178	    service: str = "odoo"
   179	    db_host: str | None = None
   180	    db_user: str | None = None
   181	    db_password_env: str | None = None
   182	    filestore_container_path: str = "/var/lib/odoo"
   183	    without_demo: str = "True"
   184	
   185	    @field_validator("service")
   186	    @classmethod
   187	    def service_must_be_safe(cls, value: str, info: ValidationInfo) -> str:
   188	        return validate_identifier(value, info.field_name)
   189	
   190	
   191	class RemoteBackupConfig(BaseModel):
   192	    type: str = "s3"
   193	    bucket: str | None = None
   194	    region: str | None = None
   195	    prefix: str = ""
   196	    endpoint_env: str | None = None
   197	    access_key_env: str | None = None
   198	    secret_key_env: str | None = None
   199	    region_env: str | None = None
   200	    encryption_algorithm: str | None = None
   201	    encryption_key_env: str | None = None
   202	
   203	
   204	class RetentionConfig(BaseModel):
   205	    daily: int = 7
   206	    weekly: int = 4
   207	    monthly: int = 6
   208	
   209	
   210	class BackupsConfig(BaseModel):
   211	    local_path: str = "./backups"
   212	    remote: RemoteBackupConfig | None = None
   213	    retention: RetentionConfig = Field(default_factory=RetentionConfig)
   214	
   215	
   216	class SanitizationConfig(BaseModel):
   217	    sql_files: list[str] = Field(default_factory=list)
   218	    disable_mail_servers: bool = True
   219	    disable_fetchmail: bool = True
   220	    disable_crons: bool = True
   221	    rewrite_base_url: bool = True
   222	    disable_payment_providers: bool = True
   223	    disable_queue_jobs: bool = True
   224	    purge_mail_queue: bool = True
   225	    temp_db_suffix: str = "_incoming"
   226	
   227	
   228	class RedactionConfig(BaseModel):
   229	    min_secret_length: int = 6
   230	    ignore_values: list[str] = Field(default_factory=lambda: ["odoo", "admin", "postgres", "password", "secret", "changeme"])
   231	
   232	
   233	class HealthcheckConfig(BaseModel):
   234	    path: str = "/web/health"
   235	    scheme: Literal["http", "https"] | None = None
   236	    timeout_seconds: int = 5
   237	    retries: int = 12
   238	    interval_seconds: int = 5
   239	
   240	
   241	class OdooCtlConfig(BaseModel):
   242	    project: ProjectConfig
   243	    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
   244	    environments: dict[str, EnvironmentConfig]
   245	    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
   246	    odoo: OdooConfig
   247	    backups: BackupsConfig = Field(default_factory=BackupsConfig)
   248	    sanitization: SanitizationConfig = Field(default_factory=SanitizationConfig)
   249	    healthcheck: HealthcheckConfig = Field(default_factory=HealthcheckConfig)
   250	    redaction: RedactionConfig = Field(default_factory=RedactionConfig)
   251	
   252	    @field_validator("environments")
   253	    @classmethod
   254	    def must_have_environments(cls, value: dict[str, EnvironmentConfig]) -> dict[str, EnvironmentConfig]:
   255	        if not value:
   256	            raise ValueError("at least one environment is required")
   257	        for name in value:
   258	            validate_identifier(name, "environment name")
   259	        return value
   260	
   261	    @model_validator(mode="after")
   262	    def validate_environment_graph(self) -> "OdooCtlConfig":
   263	        if self.odoo.db_host is None:
   264	            self.odoo.db_host = self.postgres.internal_host
   265	        if self.odoo.db_user is None:
   266	            self.odoo.db_user = self.postgres.user
   267	        if self.odoo.db_password_env is None:
   268	            self.odoo.db_password_env = self.postgres.password_env
   269	
   270	        seen_db_names: dict[str, str] = {}
   271	        seen_filestores: dict[str, str] = {}
   272	        seen_domains: dict[str, str] = {}
   273	        seen_branches: dict[str, str] = {}
   274	
   275	        for name, env in self.environments.items():
   276	            if name == "production" and env.clone_from:
   277	                raise ValueError(
   278	                    "Environment 'production' cannot be a clone target; "
   279	                    "cloning drops and recreates the target database without a backup"
   280	                )
   281	            if env.clone_from and env.clone_from not in self.environments:
   282	                known = ", ".join(sorted(self.environments))
   283	                raise ValueError(f"Environment '{name}' clone_from '{env.clone_from}' is not defined. Known: {known}")
   284	            if env.clone_from == name:
   285	                raise ValueError(f"Environment '{name}' cannot clone_from itself")
   286	
   287	            if env.db_name in seen_db_names:
   288	                first_env = seen_db_names[env.db_name]
   289	                raise ValueError(
   290	                    f"Environments '{first_env}' and '{name}' cannot share db_name '{env.db_name}'; "
   291	                    "clone and rollback operations drop and recreate target databases"
   292	                )
   293	            seen_db_names[env.db_name] = name
   294	
   295	            filestore_identity = (
   296	                f"volume:{env.filestore_volume}:{env.filestore_path}"
   297	                if env.filestore_volume
   298	                else f"path:{env.filestore_path}"
   299	            )
   300	            if filestore_identity in seen_filestores:
   301	                first_env = seen_filestores[filestore_identity]
   302	                raise ValueError(
   303	                    f"Environments '{first_env}' and '{name}' cannot share filestore '{filestore_identity}'; "
   304	                    "clone and rollback operations replace target filestores"
   305	                )
   306	            seen_filestores[filestore_identity] = name
   307	
   308	            if env.domain in seen_domains:
   309	                first_env = seen_domains[env.domain]
   310	                first = self.environments[first_env]
   311	                shared_multidb_stack = first.stack == env.stack and first.db_selector and env.db_selector
   312	                if not shared_multidb_stack:
   313	                    raise ValueError(
   314	                        f"Environments '{first_env}' and '{name}' cannot share domain '{env.domain}'; "
   315	                        "deploy and rollback healthchecks would target the wrong instance unless both use db_selector in the same stack"
   316	                    )
   317	            seen_domains[env.domain] = name
   318	
   319	            if env.branch in seen_branches:
   320	                first_env = seen_branches[env.branch]
   321	                raise ValueError(
   322	                    f"Environments '{first_env}' and '{name}' cannot share branch '{env.branch}'; "
   323	                    "branch-to-environment mapping must be unique for deploy and rollback to target the right instance"
   324	                )
   325	            seen_branches[env.branch] = name
   326	
   327	            if env.promotes_to and env.promotes_to not in self.environments:
   328	                known = ", ".join(sorted(self.environments))
   329	                raise ValueError(
   330	                    f"Environment '{name}' promotes_to '{env.promotes_to}' is not defined. Known: {known}"
   331	                )
   332	            if env.promotes_to == name:
   333	                raise ValueError(f"Environment '{name}' cannot promotes_to itself")
   334	
   335	        # A clone/restore/rehearsal restores into ``<db_name><temp_db_suffix>``
   336	        # and then drops/renames it. If that temp name equals another env's live
   337	        # db_name, promoting one environment would silently DROP another's
   338	        # database. Reject the collision at load time.
   339	        suffix = self.sanitization.temp_db_suffix
   340	        for name, env in self.environments.items():
   341	            temp_db = env.db_name + suffix
   342	            owner = seen_db_names.get(temp_db)
   343	            if owner is not None and owner != name:
   344	                raise ValueError(
   345	                    f"Environment '{name}' temp database '{temp_db}' "
   346	                    f"(db_name + temp_db_suffix '{suffix}') collides with the live "
   347	                    f"db_name of environment '{owner}'; a clone or restore into "
   348	                    f"'{name}' would drop '{owner}'. Change the db_name or temp_db_suffix."
   349	                )
   350	        return self
   351	
   352	    def is_protected(self, name: str) -> bool:
   353	        env = self.env(name)
   354	        if env.protected is not None:
   355	            return env.protected
   356	        return name == "production" or env.tier == "production"
   357	
   358	    def env(self, name: str) -> EnvironmentConfig:
   359	        try:
   360	            return self.environments[name]
   361	        except KeyError as exc:
   362	            known = ", ".join(sorted(self.environments))
   363	            raise KeyError(f"Unknown environment '{name}'. Known: {known}") from exc
   364	
   365	    def referenced_env_vars(self) -> list[str]:
   366	        refs = {self.postgres.password_env}
   367	        if self.postgres.service_password_env:
   368	            refs.add(self.postgres.service_password_env)
   369	        if self.odoo.db_password_env:
   370	            refs.add(self.odoo.db_password_env)
   371	        if self.backups.remote:
   372	            remote = self.backups.remote
   373	            for value in (
   374	                remote.endpoint_env,
   375	                remote.access_key_env,
   376	                remote.secret_key_env,
   377	                remote.region_env,
   378	                remote.encryption_key_env,
   379	            ):
   380	                if value:
   381	                    refs.add(value)
   382	        return sorted(refs)
   383	
   384	    def missing_env_vars(self) -> list[str]:
   385	        return [name for name in self.referenced_env_vars() if not os.getenv(name)]
   386	
   387	
   388	def load_config(path: str | Path = "odooctl.yml") -> OdooCtlConfig:
   389	    config_path = Path(path)
   390	    if not config_path.exists():
   391	        raise click.ClickException(f"Config file not found: {config_path}")
   392	    data = yaml.safe_load(config_path.read_text())
   393	    return OdooCtlConfig.model_validate(data)
   394	
   395	
   396	def example_config() -> str:
   397	    return """project:
   398	  name: demo-odoo-project
   399	  odoo_version: "19.0"
   400	
   401	runtime:
   402	  type: docker_compose
   403	  compose_file: docker-compose.yml
   404	  reverse_proxy: traefik
   405	
   406	postgres:
   407	  host: localhost
   408	  port: 5432
   409	  user: odoo
   410	  password_env: ODOO_DB_PASSWORD
   411	
   412	backups:
   413	  local_path: backups
   414	  remote:
   415	    type: s3
   416	    bucket: demo-odoo-backups
   417	    endpoint_env: ODOO_S3_ENDPOINT
   418	    access_key_env: ODOO_S3_ACCESS_KEY
   419	    secret_key_env: ODOO_S3_SECRET_KEY
   420	    region: eu-central-1
   421	    prefix: demo-odoo
   422	
   423	redaction:
   424	  min_secret_length: 6
   425	  ignore_values:
   426	    - odoo
   427	    - admin
   428	    - postgres
   429	
   430	odoo:
   431	  image: registry.example.com/odoo:19.0
   432	  config_path: /etc/odoo/odoo.conf
   433	  service: odoo
   434	  addons_paths:
   435	    - /mnt/extra-addons
   436	    - /opt/odoo/custom-addons
   437	
   438	environments:
   439	  production:
   440	    branch: main
   441	    domain: odoo.example.com
   442	    db_name: odoo_prod
   443	    filestore_path: /var/lib/odoo/filestore/odoo_prod
   444	    update_modules:
   445	      - sale
   446	      - stock
   447	  staging:
   448	    branch: staging
   449	    domain: staging.odoo.example.com
   450	    db_name: odoo_staging
   451	    filestore_path: /var/lib/odoo/filestore/odoo_staging
   452	    clone_from: production
   453	    sanitize: true
   454	    update_modules:
   455	      - sale
   456	      - stock
   457	      - custom_module
   458	
   459	sanitization:
   460	  sql_files:
   461	    - .sanitize/staging.sql
   462	    - .sanitize/disable_connectors.sql
   463	  disable_mail_servers: true
   464	  disable_fetchmail: true
   465	  disable_crons: true
   466	  rewrite_base_url: true
   467	  disable_payment_providers: true
   468	  disable_queue_jobs: true
   469	  purge_mail_queue: true
   470	  temp_db_suffix: _incoming
   471	
   472	healthcheck:
   473	  path: /web/health
   474	  timeout_seconds: 5
   475	  retries: 12
   476	  interval_seconds: 5
   477	"""

exec
/bin/bash -lc "nl -ba odooctl/registry.py; nl -ba odooctl/commands/import_cmd.py; nl -ba odooctl/migration/rehearse.py; sed -n '55,180p' odooctl/services/clone.py | nl -ba -v55; sed -n '190,320p' odooctl/runner/worker.py | nl -ba -v190; nl -ba odooctl/odoo/db_swap.py; nl -ba odooctl/adapters/postgres.py" in /home/dev/odooctl
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	from dataclasses import dataclass
     4	from pathlib import Path
     5	import os
     6	import tomllib
     7	
     8	import click
     9	
    10	from odooctl.context import ProjectContext
    11	
    12	
    13	@dataclass(frozen=True)
    14	class RegisteredProject:
    15	    name: str
    16	    path: Path
    17	    config: str = "odooctl.yml"
    18	
    19	
    20	@dataclass(frozen=True)
    21	class Registry:
    22	    path: Path
    23	    active: str | None
    24	    projects: dict[str, RegisteredProject]
    25	
    26	
    27	def default_registry_path() -> Path:
    28	    config_home = os.environ.get("XDG_CONFIG_HOME")
    29	    if config_home:
    30	        return Path(config_home).expanduser() / "odooctl" / "config.toml"
    31	    return Path.home() / ".config" / "odooctl" / "config.toml"
    32	
    33	
    34	def load_registry(path: str | Path | None = None) -> Registry:
    35	    registry_path = Path(path).expanduser() if path is not None else default_registry_path()
    36	    if not registry_path.exists():
    37	        return Registry(path=registry_path, active=None, projects={})
    38	
    39	    data = tomllib.loads(registry_path.read_text())
    40	    raw_projects = data.get("projects", {}) or {}
    41	    projects: dict[str, RegisteredProject] = {}
    42	    for name, raw in raw_projects.items():
    43	        if not isinstance(raw, dict) or "path" not in raw:
    44	            continue
    45	        projects[name] = RegisteredProject(
    46	            name=name,
    47	            path=Path(str(raw["path"])).expanduser(),
    48	            config=str(raw.get("config", "odooctl.yml")),
    49	        )
    50	    active = data.get("active")
    51	    if active is not None:
    52	        active = str(active)
    53	    return Registry(path=registry_path, active=active, projects=projects)
    54	
    55	
    56	def save_registry(registry: Registry) -> None:
    57	    registry.path.parent.mkdir(parents=True, exist_ok=True)
    58	    lines: list[str] = []
    59	    if registry.active:
    60	        lines.append(f'active = "{_toml_escape(registry.active)}"')
    61	        lines.append("")
    62	    if registry.projects:
    63	        lines.append("[projects]")
    64	        for name in sorted(registry.projects):
    65	            project = registry.projects[name]
    66	            lines.append(
    67	                f'"{_toml_escape(name)}" = {{ path = "{_toml_escape(str(project.path))}", '
    68	                f'config = "{_toml_escape(project.config)}" }}'
    69	            )
    70	    registry.path.write_text("\n".join(lines).rstrip() + "\n")
    71	
    72	
    73	def _validate_project_name(name: str) -> str:
    74	    """Reject project names that could inject path components (audit finding F10).
    75	
    76	    Project names flow into registry keys and state paths, so they follow the
    77	    same identifier rule as config environment names.
    78	    """
    79	    from odooctl.config import validate_identifier
    80	
    81	    try:
    82	        return validate_identifier(name, "project name")
    83	    except ValueError as exc:
    84	        raise click.ClickException(str(exc)) from exc
    85	
    86	
    87	def _contained_config_path(name: str, root: Path, config: str | Path) -> Path:
    88	    """Resolve a project's config path and require it to stay inside *root*.
    89	
    90	    Path containment (audit finding F10): a registry entry's ``config`` value
    91	    is attacker-influenceable (hand-edited config.toml), so a value like
    92	    ``../../etc/passwd`` must not read files outside the registered project
    93	    root. The project root itself may be any absolute path; absolute config
    94	    paths keep working as long as they resolve inside the root.
    95	    """
    96	    root_resolved = Path(root).expanduser().resolve()
    97	    config_path = Path(config).expanduser()
    98	    resolved = (config_path if config_path.is_absolute() else root_resolved / config_path).resolve()
    99	    if not resolved.is_relative_to(root_resolved):
   100	        raise click.ClickException(
   101	            f"Config path for project {name!r} escapes the project root: "
   102	            f"{resolved} is not inside {root_resolved}"
   103	        )
   104	    return resolved
   105	
   106	
   107	def add_project(name: str, path: str | Path, config: str = "odooctl.yml", *, make_active: bool = True) -> RegisteredProject:
   108	    _validate_project_name(name)
   109	    registry = load_registry()
   110	    root = Path(path).expanduser().resolve()
   111	    resolved_config = _contained_config_path(name, root, config)
   112	    if not resolved_config.exists():
   113	        raise click.ClickException(f"Config file not found for project {name!r}: {resolved_config}")
   114	    project = RegisteredProject(name=name, path=root, config=str(config))
   115	    projects = dict(registry.projects)
   116	    projects[name] = project
   117	    active = name if make_active or registry.active is None else registry.active
   118	    save_registry(Registry(path=registry.path, active=active, projects=projects))
   119	    return project
   120	
   121	
   122	def remove_project(name: str) -> None:
   123	    registry = load_registry()
   124	    if name not in registry.projects:
   125	        raise click.ClickException(f"Unknown project: {name}")
   126	    projects = dict(registry.projects)
   127	    projects.pop(name)
   128	    active = registry.active
   129	    if active == name:
   130	        active = next(iter(sorted(projects)), None)
   131	    save_registry(Registry(path=registry.path, active=active, projects=projects))
   132	
   133	
   134	def use_project(name: str) -> RegisteredProject:
   135	    registry = load_registry()
   136	    project = registry.projects.get(name)
   137	    if project is None:
   138	        raise click.ClickException(f"Unknown project: {name}")
   139	    save_registry(Registry(path=registry.path, active=name, projects=registry.projects))
   140	    return project
   141	
   142	
   143	def resolve_project_context(
   144	    *,
   145	    project: str | None = None,
   146	    project_dir: str | Path | None = None,
   147	    config: str | Path = "odooctl.yml",
   148	) -> ProjectContext:
   149	    """Resolve project context with precedence: -p > -C > cwd/config."""
   150	
   151	    if project:
   152	        registry = load_registry()
   153	        registered = registry.projects.get(project)
   154	        if registered is None:
   155	            raise click.ClickException(f"Unknown project: {project}")
   156	        # Containment check (audit F10): reject registry entries whose config
   157	        # resolves outside the registered project root.
   158	        resolved_config = _contained_config_path(registered.name, registered.path, registered.config)
   159	        return ProjectContext.from_config_path(resolved_config, root=registered.path)
   160	    if project_dir is not None:
   161	        return ProjectContext.from_config_path(config, root=project_dir)
   162	    return ProjectContext.from_config_path(config)
   163	
   164	
   165	def _toml_escape(value: str) -> str:
   166	    return value.replace("\\", "\\\\").replace('"', '\\"')
     1	"""odooctl import — take over an existing Docker Compose Odoo deployment.
     2	
     3	Safety contract (enforced end-to-end):
     4	  - Detection is strictly read-only: no subprocess calls, no Docker daemon
     5	    access, no container mutations, no DB writes, no volume writes.
     6	  - Secret values are never printed, logged, or written to config.
     7	  - Generated config is written only after explicit --yes confirmation.
     8	  - Existing odooctl.yml is never overwritten without --force.
     9	
    10	After adoption (--yes), the command automatically:
    11	  1. Registers the project in the local registry (add_project).
    12	  2. Validates the generated config (validate).
    13	  3. Runs preflight doctor checks unless --skip-doctor is passed.
    14	  4. Runs a safety backup unless --skip-backup is passed.
    15	
    16	Usage:
    17	    odooctl import                             # preview current directory
    18	    odooctl import PATH                        # preview a specific compose file/dir
    19	    odooctl import --preview                   # explicit preview flag (same as default)
    20	    odooctl import --name myproject --yes      # adopt with project name
    21	    odooctl import --name myproject --yes --skip-backup   # adopt, skip backup
    22	    odooctl import --force                     # overwrite existing odooctl.yml
    23	"""
    24	from __future__ import annotations
    25	
    26	from pathlib import Path
    27	
    28	import typer
    29	
    30	from odooctl.commands import backup as backup_cmd
    31	from odooctl.commands import doctor as doctor_cmd
    32	from odooctl.commands import validate as validate_cmd
    33	from odooctl.importer.adopt import adopt
    34	from odooctl.importer.detect import detect_from_compose
    35	from odooctl.importer.report import build_preview_report, render_preview_text
    36	from odooctl.registry import add_project
    37	from odooctl.utils.logging import info, success, warn
    38	
    39	
    40	def _find_compose(path: Path | None) -> Path:
    41	    if path is not None:
    42	        p = Path(path)
    43	        if p.is_file():
    44	            return p
    45	        if p.is_dir():
    46	            for name in ("docker-compose.yml", "docker-compose.yaml"):
    47	                candidate = p / name
    48	                if candidate.exists():
    49	                    return candidate
    50	        raise typer.BadParameter(
    51	            f"No docker-compose.yml found at {path}. "
    52	            "Pass the path to a compose file or directory containing one."
    53	        )
    54	    for name in ("docker-compose.yml", "docker-compose.yaml"):
    55	        p = Path.cwd() / name
    56	        if p.exists():
    57	            return p
    58	    raise typer.BadParameter(
    59	        "No docker-compose.yml found in the current directory. "
    60	        "Pass a path as the first argument."
    61	    )
    62	
    63	
    64	def _infer_project_name(compose_path: Path) -> str:
    65	    return compose_path.parent.name or "imported-odoo"
    66	
    67	
    68	def _check_output_containment(output: Path, compose_path: Path, *, allow_outside: bool) -> None:
    69	    """Refuse to write the generated config outside the working/project dir.
    70	
    71	    Path containment (audit finding F20): ``--output`` combined with
    72	    ``--force`` could otherwise overwrite arbitrary files. The resolved output
    73	    must live under the current working directory or the imported project's
    74	    directory (the compose file's parent) unless *allow_outside* is explicitly
    75	    set (CLI flag ``--allow-outside``, default off).
    76	    """
    77	    if allow_outside:
    78	        return
    79	    resolved = output.expanduser().resolve()
    80	    allowed_roots = (Path.cwd().resolve(), compose_path.parent.resolve())
    81	    if not any(resolved.is_relative_to(root) for root in allowed_roots):
    82	        raise typer.BadParameter(
    83	            f"Refusing to write {resolved}: it is outside the current working "
    84	            f"directory and the imported project directory. "
    85	            "Pass --allow-outside to permit writing elsewhere."
    86	        )
    87	
    88	
    89	def run(
    90	    path: Path | None = None,
    91	    *,
    92	    preview: bool = False,
    93	    name: str | None = None,
    94	    yes: bool = False,
    95	    force: bool = False,
    96	    output: Path = Path("odooctl.yml"),
    97	    skip_doctor: bool = False,
    98	    skip_backup: bool = False,
    99	    allow_outside: bool = False,
   100	) -> None:
   101	    """Import an existing Odoo Docker Compose deployment.
   102	
   103	    By default this shows a preview only. Pass --yes to write odooctl.yml.
   104	    Secret values are never printed or written to config files.
   105	
   106	    After writing the config, the project is registered in the registry,
   107	    the config is validated, doctor preflight checks run (unless
   108	    --skip-doctor), and a safety backup is created (unless --skip-backup).
   109	
   110	    Path containment (audit finding F20): --output must resolve inside the
   111	    current working directory or the imported project directory; pass
   112	    --allow-outside (allow_outside=True) to write elsewhere. --force is still
   113	    required to overwrite an existing file, regardless of --allow-outside.
   114	    """
   115	    compose_path = _find_compose(path)
   116	    info(f"Detecting deployment from {compose_path} …")
   117	
   118	    detected = detect_from_compose(compose_path)
   119	    project_name = name or _infer_project_name(compose_path)
   120	    report = build_preview_report(detected, project_name=project_name)
   121	
   122	    typer.echo(render_preview_text(report))
   123	
   124	    if not yes or preview:
   125	        typer.echo(
   126	            "\nThis is a preview. Run with --yes to adopt this config, "
   127	            "or --name to change the project name.\n"
   128	            "SAFETY: no files have been written and no containers were touched."
   129	        )
   130	        return
   131	
   132	    _check_output_containment(output, compose_path, allow_outside=allow_outside)
   133	
   134	    try:
   135	        adopt(report, output_path=output, force=force)
   136	    except FileExistsError as exc:
   137	        raise typer.BadParameter(str(exc)) from exc
   138	
   139	    config_path = output.resolve()
   140	    success(f"Adopted config written to {config_path}")
   141	
   142	    # Register the project so it can be referenced by --project/-p globally.
   143	    try:
   144	        add_project(project_name, config_path.parent, config=config_path.name)
   145	        success(f"Registered project '{project_name}' in registry.")
   146	    except Exception as exc:
   147	        warn(f"Could not register project in registry: {exc}")
   148	
   149	    # Validate the generated config (schema + env-var audit).
   150	    try:
   151	        validate_cmd.execute(str(config_path))
   152	    except Exception as exc:
   153	        warn(f"Config validation warning: {exc}")
   154	
   155	    # Run preflight doctor checks (side-effect-free).
   156	    if not skip_doctor:
   157	        try:
   158	            report_doc = doctor_cmd._run_doctor(str(config_path))
   159	            if report_doc.ok:
   160	                success("Doctor: all preflight checks passed.")
   161	            else:
   162	                for check in report_doc.checks:
   163	                    if not check.ok:
   164	                        warn(f"Doctor [{check.name}]: {check.message}")
   165	                warn("Doctor: some checks failed — run 'odooctl doctor' to review and fix.")
   166	        except Exception as exc:
   167	            warn(f"Doctor: check failed with error: {exc}")
   168	
   169	    # Run a safety backup — the first managed snapshot after adoption.
   170	    if not skip_backup:
   171	        try:
   172	            backup_id = backup_cmd.execute("production", str(config_path))
   173	            success(f"Safety backup created: {backup_id}")
   174	        except Exception as exc:
   175	            warn(f"Backup after adoption failed: {exc}")
   176	            warn("Run 'odooctl backup production' manually to create a safety snapshot.")
     1	"""Upgrade rehearsal service.
     2	
     3	Safety contract
     4	---------------
     5	* The throwaway DB name is always distinct from the source DB name (guarded at entry).
     6	* ``db_adapter.dump()`` is read-only on the source — it never modifies the source DB.
     7	* All writes target *throwaway_db* only; the production DB and filestore are untouched.
     8	* The throwaway DB is always dropped in the ``finally`` block unless ``keep=True``.
     9	* A JSON report is always saved to *report_dir* — even on failure — when provided.
    10	* ``healthcheck_fn`` receives the throwaway DB name (not the source env public URL) so
    11	  it validates the upgraded DB, not the live source environment.
    12	* When the matrix marks a path ``requires_openupgrade`` and ``use_openupgrade`` is
    13	  ``False``, the rehearsal fails immediately rather than running a standard
    14	  ``odoo --update all`` that cannot perform a real cross-major upgrade.
    15	"""
    16	from __future__ import annotations
    17	
    18	import json
    19	import re
    20	import tempfile
    21	import time
    22	from dataclasses import dataclass, field
    23	from pathlib import Path
    24	from typing import Callable
    25	
    26	
    27	@dataclass
    28	class UpgradeResult:
    29	    ok: bool
    30	    log_ref: str | None = None
    31	    failed_modules: list[str] = field(default_factory=list)
    32	    warnings: list[str] = field(default_factory=list)
    33	    installed_after: list[str] = field(default_factory=list)
    34	
    35	
    36	@dataclass
    37	class RehearsalReport:
    38	    status: str           # "success" | "failed"
    39	    source_env: str
    40	    source_version: str
    41	    target_version: str
    42	    installed_modules: list[str]
    43	    failed_modules: list[str]
    44	    warnings: list[str]
    45	    duration_seconds: float
    46	    healthcheck_status: str   # "passed" | "failed" | "skipped"
    47	    log_path: str | None
    48	    cleanup_status: str       # "cleaned" | "kept" | "cleanup_failed"
    49	    next_actions: list[str]
    50	    message: str | None = None
    51	
    52	    def to_dict(self) -> dict:
    53	        return {
    54	            "status": self.status,
    55	            "source_env": self.source_env,
    56	            "source_version": self.source_version,
    57	            "target_version": self.target_version,
    58	            "installed_modules": self.installed_modules,
    59	            "failed_modules": self.failed_modules,
    60	            "warnings": self.warnings,
    61	            "duration_seconds": self.duration_seconds,
    62	            "healthcheck_status": self.healthcheck_status,
    63	            "log_path": self.log_path,
    64	            "cleanup_status": self.cleanup_status,
    65	            "next_actions": self.next_actions,
    66	            "message": self.message,
    67	        }
    68	
    69	
    70	def rehearse_upgrade(
    71	    *,
    72	    source_env: str,
    73	    source_version: str,
    74	    target_version: str,
    75	    source_db: str,
    76	    db_adapter,
    77	    healthcheck_fn: Callable[[str], bool],
    78	    upgrade_fn: Callable[[str, str], UpgradeResult],
    79	    report_dir: Path | None = None,
    80	    keep: bool = False,
    81	    throwaway_suffix: str = "_mig_rehearsal",
    82	    requires_openupgrade: bool = False,
    83	    use_openupgrade: bool = False,
    84	) -> RehearsalReport:
    85	    """Run an upgrade rehearsal against a throwaway copy of *source_db*.
    86	
    87	    :param source_env: Name of the source environment (used in the report).
    88	    :param source_version: Current Odoo version (e.g. ``"17.0"``).
    89	    :param target_version: Target Odoo version (e.g. ``"18.0"``).
    90	    :param source_db: Postgres database name of the source environment.
    91	    :param db_adapter: Injectable adapter (must implement dump/restore/drop/drop_create).
    92	    :param healthcheck_fn: Called after the upgrade with the *throwaway DB name*; returns
    93	        ``True`` if the upgraded database is healthy (e.g. a psql ping).  Must target the
    94	        throwaway DB, not the source environment's public URL.
    95	    :param upgrade_fn: Runs the Odoo upgrade on *throwaway_db*; returns :class:`UpgradeResult`.
    96	    :param report_dir: Directory where the JSON report is written (created if absent).
    97	    :param keep: Leave the throwaway DB intact after rehearsal (useful for debugging).
    98	    :param throwaway_suffix: Suffix appended to *source_db* to form the throwaway DB name.
    99	    :param requires_openupgrade: ``True`` when the migration matrix marks this path as
   100	        requiring OpenUpgrade.  If ``True`` and ``use_openupgrade`` is ``False``, the
   101	        rehearsal fails immediately with a clear message rather than running a standard
   102	        ``odoo --update all`` that cannot perform a real cross-major upgrade.
   103	    :param use_openupgrade: ``True`` when the caller's *upgrade_fn* uses OpenUpgrade.
   104	    """
   105	    throwaway_db = f"{source_db}{throwaway_suffix}"
   106	    if throwaway_db == source_db:
   107	        raise RuntimeError(
   108	            f"Throwaway DB name {throwaway_db!r} must differ from source DB "
   109	            f"{source_db!r}; use a non-empty throwaway_suffix."
   110	        )
   111	
   112	    # Early exit: path requires OpenUpgrade but caller did not request it.
   113	    # Running odoo --update all on a throwaway clone cannot perform a real cross-major
   114	    # upgrade, so claiming success would be misleading.
   115	    if requires_openupgrade and not use_openupgrade:
   116	        msg = (
   117	            f"Upgrade path {source_version} → {target_version} requires OpenUpgrade. "
   118	            "Re-run with --openupgrade (and ensure the OpenUpgrade container is set up)."
   119	        )
   120	        report = RehearsalReport(
   121	            status="failed",
   122	            source_env=source_env,
   123	            source_version=source_version,
   124	            target_version=target_version,
   125	            installed_modules=[],
   126	            failed_modules=[],
   127	            warnings=[],
   128	            duration_seconds=0.0,
   129	            healthcheck_status="skipped",
   130	            log_path=None,
   131	            cleanup_status="cleaned",
   132	            next_actions=[
   133	                f"Re-run: odooctl migrate rehearse --env {source_env} "
   134	                f"--to {target_version} --openupgrade",
   135	                "Ensure the OpenUpgrade container is set up per docs/migration.md.",
   136	            ],
   137	            message=msg,
   138	        )
   139	        _save_report_to_dir(report, report_dir)
   140	        return report
   141	
   142	    start = time.monotonic()
   143	    status = "failed"
   144	    message: str | None = None
   145	    failed_modules: list[str] = []
   146	    warnings: list[str] = []
   147	    installed_modules: list[str] = []
   148	    healthcheck_status = "skipped"
   149	    log_path: str | None = None
   150	    cleanup_status = "cleaned"
   151	    tmp_dump: Path | None = None
   152	
   153	    try:
   154	        # Step 1 — clone source DB into throwaway via dump → restore.
   155	        # dump() is a read-only pg_dump on the source; restore() targets throwaway_db only.
   156	        with tempfile.NamedTemporaryFile(
   157	            prefix="odooctl-mig-", suffix=".dump", delete=False
   158	        ) as tmp:
   159	            tmp_dump = Path(tmp.name)
   160	
   161	        db_adapter.dump(source_db, tmp_dump)
   162	        db_adapter.restore(throwaway_db, tmp_dump)
   163	
   164	        # Step 2 — run the upgrade against the throwaway DB.
   165	        upgrade_result = upgrade_fn(throwaway_db, target_version)
   166	        log_path = upgrade_result.log_ref
   167	        failed_modules = upgrade_result.failed_modules
   168	        warnings = upgrade_result.warnings
   169	        installed_modules = upgrade_result.installed_after
   170	
   171	        if not upgrade_result.ok:
   172	            message = "Upgrade command failed; see log_path for details."
   173	        else:
   174	            # Step 3 — healthcheck: ping the throwaway DB (not the source env URL).
   175	            # After --stop-after-init Odoo is not running, so an HTTP check is meaningless;
   176	            # a DB ping confirms the upgraded schema is accessible.
   177	            ok = healthcheck_fn(throwaway_db)
   178	            healthcheck_status = "passed" if ok else "failed"
   179	            if ok:
   180	                status = "success"
   181	            else:
   182	                message = "Healthcheck failed after upgrade."
   183	
   184	    except Exception as exc:
   185	        message = str(exc)
   186	        status = "failed"
   187	    finally:
   188	        if tmp_dump is not None:
   189	            tmp_dump.unlink(missing_ok=True)
   190	        if keep:
   191	            cleanup_status = "kept"
   192	        else:
   193	            try:
   194	                db_adapter.drop(throwaway_db)
   195	            except Exception:
   196	                cleanup_status = "cleanup_failed"
   197	
   198	    duration = round(time.monotonic() - start, 2)
   199	    next_actions = _build_next_actions(status, failed_modules, warnings, target_version)
   200	
   201	    report = RehearsalReport(
   202	        status=status,
   203	        source_env=source_env,
   204	        source_version=source_version,
   205	        target_version=target_version,
   206	        installed_modules=installed_modules,
   207	        failed_modules=failed_modules,
   208	        warnings=warnings,
   209	        duration_seconds=duration,
   210	        healthcheck_status=healthcheck_status,
   211	        log_path=log_path,
   212	        cleanup_status=cleanup_status,
   213	        next_actions=next_actions,
   214	        message=message,
   215	    )
   216	    _save_report_to_dir(report, report_dir)
   217	    return report
   218	
   219	
   220	def _sanitize_component(value: str) -> str:
   221	    """Sanitize a user-influenced report filename component (audit finding F19).
   222	
   223	    Applies the identifier rule from :mod:`odooctl.config`: only
   224	    ``[A-Za-z0-9._-]`` characters, no ``..``, alphanumeric start, max 64 chars.
   225	    Invalid characters are replaced instead of raising so a failure report is
   226	    still written even for hostile inputs.
   227	    """
   228	    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(value))
   229	    while ".." in cleaned:
   230	        cleaned = cleaned.replace("..", ".")
   231	    cleaned = cleaned.lstrip("._-") or "unknown"
   232	    return cleaned[:64]
   233	
   234	
   235	def _save_report_to_dir(report: RehearsalReport, report_dir: Path | None) -> None:
   236	    """Write the JSON report inside *report_dir* only.
   237	
   238	    Path containment (audit finding F19): the filename is derived from
   239	    user-influenced values (env name, version strings), so each component is
   240	    sanitized and the resolved output path is required to stay inside
   241	    ``report_dir`` (the project's ``.odooctl/migration_reports`` directory).
   242	    """
   243	    if report_dir is None:
   244	        return
   245	    report_dir.mkdir(parents=True, exist_ok=True)
   246	    fname = (
   247	        f"migration_rehearsal_{_sanitize_component(report.source_env)}"
   248	        f"_{_sanitize_component(report.source_version)}"
   249	        f"_to_{_sanitize_component(report.target_version)}.json"
   250	    )
   251	    root = report_dir.resolve()
   252	    report_file = (root / fname).resolve()
   253	    if report_file.parent != root:
   254	        raise ValueError(
   255	            f"Report path {report_file} escapes the report directory {root}"
   256	        )
   257	    report_file.write_text(json.dumps(report.to_dict(), indent=2))
   258	    if report.log_path is None:
   259	        report.log_path = str(report_file)
   260	
   261	
   262	def _build_next_actions(
   263	    status: str,
   264	    failed_modules: list[str],
   265	    warnings: list[str],
   266	    target_version: str,
   267	) -> list[str]:
   268	    actions: list[str] = []
   269	    if status == "success":
   270	        actions.append(
   271	            "Review the full migration report for warnings before scheduling the production upgrade."
   272	        )
   273	        actions.append(
   274	            f"Schedule a maintenance window for the production upgrade to {target_version}."
   275	        )
   276	        actions.append(
   277	            "Take a fresh production backup immediately before the production upgrade."
   278	        )
   279	    else:
   280	        if failed_modules:
   281	            failed_str = ", ".join(failed_modules[:5])
   282	            if len(failed_modules) > 5:
   283	                failed_str += f" (and {len(failed_modules) - 5} more)"
   284	            actions.append(f"Investigate failed modules: {failed_str}.")
   285	            actions.append("Check OpenUpgrade migration scripts for each failed module.")
   286	        if warnings:
   287	            actions.append("Address scan warnings and re-run: odooctl migrate rehearse.")
   288	        actions.append("Fix the issues above, then re-run: odooctl migrate rehearse.")
   289	    return actions
    55	            f"base_url={base_url} sanitize={'yes' if should_sanitize else 'no'}"
    56	        )
    57	        print(f"source_branch={src.branch} target_branch={dst.branch} clone_from={dst.clone_from}")
    58	        print(f"affected_integrations={','.join(dst.update_modules) or 'none'}")
    59	        print(f"production_source={'yes' if cfg.is_protected(source) else 'no'}")
    60	        return CloneResult(url=base_url)
    61	
    62	    missing_env_vars = cfg.missing_env_vars()
    63	    if missing_env_vars:
    64	        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env_vars)}")
    65	
    66	    pg = make_context_db_adapter(ctx.project) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
    67	    fs = make_filestore_adapter(ctx.project, dst) if dst.filestore_volume else FilestoreAdapter()
    68	    temp_db = f"{dst.db_name}{cfg.sanitization.temp_db_suffix}"
    69	    if temp_db == dst.db_name:
    70	        raise RuntimeError(
    71	            "Configured sanitization.temp_db_suffix must produce a temporary database distinct from the target"
    72	        )
    73	    if hasattr(pg, "clone_db_in_container"):
    74	        pg.clone_db_in_container(src.db_name, temp_db)  # type: ignore[attr-defined]
    75	    else:
    76	        with tempfile.NamedTemporaryFile(prefix="odooctl-clone-", suffix=".dump", delete=False) as tmp:
    77	            tmp_dump = Path(tmp.name)
    78	        try:
    79	            pg.dump(src.db_name, tmp_dump)
    80	            pg.restore(temp_db, tmp_dump)
    81	        finally:
    82	            tmp_dump.unlink(missing_ok=True)
    83	    src_filestore = src.filestore_path if src.filestore_volume else str(ctx.project.resolve_path(src.filestore_path))
    84	    dst_filestore = dst.filestore_path if dst.filestore_volume else str(ctx.project.resolve_path(dst.filestore_path))
    85	    fs.copy(src_filestore, dst_filestore)
    86	    if should_sanitize:
    87	        sanitize_database(pg, temp_db, dst, cfg, sanitization_profile, sql_files=ctx.project.sanitization_sql_files())
    88	    swap_temp_database(
    89	        pg,
    90	        temp_db=temp_db,
    91	        target_db=dst.db_name,
    92	        target_env_name=target,
    93	        is_protected_fn=cfg.is_protected,
    94	    )
    95	    compose = DockerComposeAdapter(cfg.runtime.compose_file, project_dir=str(ctx.project.root))
    96	    update_modules_compose(
    97	        compose,
    98	        cfg.odoo.service,
    99	        dst.db_name,
   100	        dst.update_modules,
   101	        db_host=cfg.odoo.db_host,
   102	        db_user=cfg.odoo.db_user,
   103	        db_password_env=cfg.odoo.db_password_env,
   104	        config_path=cfg.odoo.config_path,
   105	    )
   106	    compose.restart(cfg.odoo.service)
   107	    running_services = compose.ps()
   108	    if cfg.odoo.service not in running_services:
   109	        raise RuntimeError(f"Target service is not running after clone: {cfg.odoo.service}")
   110	    url = with_db_selector(base_url + cfg.healthcheck.path, dst.db_name if dst.db_selector else None)
   111	    check_url(
   112	        url,
   113	        timeout=cfg.healthcheck.timeout_seconds,
   114	        retries=cfg.healthcheck.retries,
   115	        interval=cfg.healthcheck.interval_seconds,
   116	    )
   117	    return CloneResult(url=base_url)
   190	            from odooctl.context import ProjectContext
   191	
   192	            try:
   193	                ctx = ProjectContext.from_config_path(proj.config, root=proj.path)
   194	            except Exception:
   195	                continue
   196	
   197	            queue = OperationQueue(ctx.state_dir)
   198	            entry = queue.claim_next()
   199	            if entry is None:
   200	                continue
   201	
   202	            self.last_run_ok = self._execute_entry(entry, queue, ctx)
   203	            return True
   204	        self.last_run_ok = True
   205	        return False
   206	
   207	    def _execute_entry(self, entry: QueueEntry, queue: OperationQueue, ctx) -> bool:
   208	        store = OperationStore(ctx.state_dir)
   209	        audit = AuditStore(ctx.state_dir)
   210	        nonce_store = NonceStore(ctx.state_dir)
   211	        svc_ctx = ServiceContext(project=ctx)
   212	
   213	        # Re-check status: the operation may have been cancelled after we claimed
   214	        # the queue entry (post-claim race). Skip execution and clean up.
   215	        try:
   216	            if store.load(entry.op_id).status == OperationStatus.CANCELLED:
   217	                queue.complete(entry.op_id)
   218	                return True
   219	        except KeyError:
   220	            pass
   221	
   222	        # Verify the capability token
   223	        try:
   224	            payload = tokens.verify(
   225	                self._api_key,
   226	                entry.token,
   227	                action=entry.kind,
   228	                environment=entry.environment,
   229	                project=entry.project,
   230	            )
   231	        except TokenError as exc:
   232	            store.update_status(entry.op_id, OperationStatus.FAILED, error=redact(f"token error: {exc}"))
   233	            queue.fail(entry.op_id)
   234	            return False
   235	
   236	        # Defensive RBAC floor: do not trust queue shape alone. Reconstruct the
   237	        # token-derived principal and enforce the same protected-env floor that
   238	        # the API applied before enqueueing.
   239	        try:
   240	            action = _KIND_ACTION[entry.kind]
   241	            protected = ctx.config.is_protected(entry.environment)
   242	            rbac.require(_principal_from_payload(payload), action, protected=protected)
   243	        except (KeyError, ValueError, rbac.AccessDenied) as exc:
   244	            store.update_status(entry.op_id, OperationStatus.FAILED, error=redact(f"rbac error: {exc}"))
   245	            queue.fail(entry.op_id)
   246	            return False
   247	
   248	        # Single-use nonce check: atomic claim under a file lock closes the
   249	        # check-then-mark race and retains the nonce until the token's own
   250	        # expiry so a long-TTL token can never be replayed after purge.
   251	        nonce = payload.get("nonce", "")
   252	        token_exp = payload.get("exp")
   253	        expires_at = None
   254	        if isinstance(token_exp, (int, float)):
   255	            expires_at = datetime.fromtimestamp(token_exp, tz=timezone.utc)
   256	        if not nonce_store.consume(nonce, expires_at=expires_at):
   257	            store.update_status(
   258	                entry.op_id,
   259	                OperationStatus.FAILED,
   260	                error=f"token nonce already consumed: {nonce}",
   261	            )
   262	            queue.fail(entry.op_id)
   263	            return False
   264	
   265	        # Transition to RUNNING and emit start event
   266	        store.update_status(entry.op_id, OperationStatus.RUNNING)
   267	        op = store.load(entry.op_id)
   268	        op_ctx = OperationContext(op, store)
   269	        op_ctx.emit(
   270	            f"operation started: {entry.kind} on {entry.environment}",
   271	            phase="start",
   272	        )
   273	
   274	        # Acquire per-environment lock and execute
   275	        lock = EnvironmentLock(entry.environment, ctx.state_dir, entry.op_id)
   276	        outcome = "failed"
   277	        error_msg: str | None = None
   278	
   279	        try:
   280	            lock.__enter__()
   281	            try:
   282	                _dispatch(entry, svc_ctx, op_ctx)
   283	                outcome = "succeeded"
   284	            except Exception as exc:
   285	                # Second redaction layer: this string is persisted into the
   286	                # operation store and streamed to API clients.
   287	                error_msg = redact(str(exc))
   288	            finally:
   289	                lock.__exit__(None, None, None)
   290	        except LockAcquisitionError as exc:
   291	            error_msg = f"lock acquisition failed: {exc}"
   292	
   293	        # Finalise operation status
   294	        if outcome == "succeeded":
   295	            op_ctx.emit("operation completed", phase="end", level="info")
   296	            store.update_status(entry.op_id, OperationStatus.SUCCEEDED)
   297	            queue.complete(entry.op_id)
   298	        else:
   299	            op_ctx.emit(f"operation failed: {error_msg}", phase="end", level="error")
   300	            store.update_status(entry.op_id, OperationStatus.FAILED, error=error_msg)
   301	            queue.fail(entry.op_id)
   302	
   303	        audit.append(
   304	            AuditEntry(
   305	                actor=entry.actor,
   306	                action=entry.kind,
   307	                target=entry.environment,
   308	                params_redacted=entry.params_redacted,
   309	                outcome=outcome,
   310	                op_id=entry.op_id,
   311	                timestamp=_utcnow(),
   312	            )
   313	        )
   314	        return outcome == "succeeded"
   315	
   316	    def run_loop(self, *, once: bool = False, fail_fast: bool = False) -> bool:
   317	        """Process the queue in a loop.
   318	
   319	        :param once: If True, process at most one item and return (used by
   320	            ``odooctl runner --once``).
     1	from __future__ import annotations
     2	
     3	from typing import Callable, Protocol
     4	
     5	
     6	class SwapPsqlAdapter(Protocol):
     7	    def psql(self, db_name: str, sql: str) -> None: ...
     8	
     9	
    10	def quote_identifier(name: str) -> str:
    11	    """Return a PostgreSQL quoted identifier for a database name."""
    12	    if "\x00" in name:
    13	        raise ValueError("database name cannot contain NUL bytes")
    14	    return '"' + name.replace('"', '""') + '"'
    15	
    16	
    17	def quote_literal(value: str) -> str:
    18	    return "'" + value.replace("'", "''") + "'"
    19	
    20	
    21	def terminate_connections(pg: SwapPsqlAdapter, db_name: str, *, maintenance_db: str = "postgres") -> None:
    22	    pg.psql(
    23	        maintenance_db,
    24	        "SELECT pg_terminate_backend(pid) "
    25	        "FROM pg_stat_activity "
    26	        f"WHERE datname = {quote_literal(db_name)} AND pid <> pg_backend_pid();",
    27	    )
    28	
    29	
    30	def drop_database(pg: SwapPsqlAdapter, db_name: str, *, maintenance_db: str = "postgres") -> None:
    31	    pg.psql(maintenance_db, f"DROP DATABASE IF EXISTS {quote_identifier(db_name)};")
    32	
    33	
    34	def rename_database(pg: SwapPsqlAdapter, old_name: str, new_name: str, *, maintenance_db: str = "postgres") -> None:
    35	    pg.psql(maintenance_db, f"ALTER DATABASE {quote_identifier(old_name)} RENAME TO {quote_identifier(new_name)};")
    36	
    37	
    38	def swap_temp_database(
    39	    pg: SwapPsqlAdapter,
    40	    *,
    41	    temp_db: str,
    42	    target_db: str,
    43	    target_env_name: str,
    44	    is_protected_fn: Callable[[str], bool] | None = None,
    45	    maintenance_db: str = "postgres",
    46	) -> None:
    47	    """Atomically promote a prepared temp DB into the target DB name.
    48	
    49	    ``is_protected_fn`` (typically ``OdooCtlConfig.is_protected``) guards
    50	    against accidental promotion over a protected environment such as
    51	    production; callers that omit it must enforce that policy themselves
    52	    before invoking this function. Callers are expected to restore and
    53	    sanitize ``temp_db`` before invoking this function.
    54	    """
    55	    if is_protected_fn is not None and is_protected_fn(target_env_name):
    56	        raise RuntimeError(
    57	            f"Refusing to swap a temporary database into protected environment '{target_env_name}'"
    58	        )
    59	    if temp_db == target_db:
    60	        raise RuntimeError("Temporary database name must differ from target database name")
    61	    terminate_connections(pg, target_db, maintenance_db=maintenance_db)
    62	    drop_database(pg, target_db, maintenance_db=maintenance_db)
    63	    rename_database(pg, temp_db, target_db, maintenance_db=maintenance_db)
     1	from __future__ import annotations
     2	from pathlib import Path
     3	from odooctl.config import PostgresConfig
     4	from odooctl.utils.shell import run
     5	
     6	class PostgresAdapter:
     7	    def __init__(self, config: PostgresConfig):
     8	        self.config = config
     9	
    10	    def env(self) -> dict[str, str]:
    11	        return {"PGPASSWORD": self.config.password()}
    12	
    13	    def base_args(self) -> list[str]:
    14	        return ["-h", self.config.host, "-p", str(self.config.port), "-U", self.config.user]
    15	
    16	    def ping(self, db_name: str) -> None:
    17	        run(["psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", "SELECT 1"], env=self.env())
    18	
    19	    def dump(self, db_name: str, output: str | Path) -> None:
    20	        run(["pg_dump", *self.base_args(), "-Fc", "-d", db_name, "-f", str(output)], env=self.env(), stream=True)
    21	
    22	    def restore(self, db_name: str, dump_path: str | Path) -> None:
    23	        self.drop_create(db_name)
    24	        run(["pg_restore", *self.base_args(), "-d", db_name, str(dump_path)], env=self.env(), stream=True)
    25	
    26	    def drop_create(self, db_name: str) -> None:
    27	        run(["dropdb", *self.base_args(), db_name, "--if-exists"], env=self.env(), stream=True)
    28	        run(["createdb", *self.base_args(), db_name], env=self.env(), stream=True)
    29	
    30	    def psql_file(self, db_name: str, sql_file: str | Path) -> None:
    31	        run(["psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-f", str(sql_file)], env=self.env(), stream=True)
    32	
    33	    def psql(self, db_name: str, sql: str) -> None:
    34	        run(["psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", sql], env=self.env(), stream=True)

exec
/bin/bash -lc "nl -ba odooctl/context.py; nl -ba odooctl/api/routes_projects.py; nl -ba odooctl/api/queue.py; nl -ba odooctl/security/redaction.py; rg -n \"run\\(|compose\\.exec|subprocess|sh -|shell=True\" odooctl/adapters odooctl/services odooctl/odoo odooctl/migration | head -300" in /home/dev/odooctl
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	from dataclasses import dataclass
     4	from pathlib import Path
     5	
     6	import click
     7	
     8	from odooctl.config import OdooCtlConfig, load_config
     9	
    10	
    11	@dataclass(frozen=True)
    12	class ProjectContext:
    13	    """Resolved filesystem context for an odooctl project.
    14	
    15	    The project root is the directory that owns the selected config file unless
    16	    an explicit root is provided. Relative runtime/state paths should be
    17	    resolved through this object instead of the process current working
    18	    directory.
    19	    """
    20	
    21	    root: Path
    22	    config_path: Path
    23	    config: OdooCtlConfig
    24	
    25	    @classmethod
    26	    def from_config_path(cls, config_path: str | Path = "odooctl.yml", *, root: str | Path | None = None) -> "ProjectContext":
    27	        raw_config = Path(config_path).expanduser()
    28	        if raw_config.is_absolute():
    29	            resolved_config = raw_config.resolve()
    30	        else:
    31	            base = Path(root).expanduser() if root is not None else Path.cwd()
    32	            resolved_config = (base / raw_config).resolve()
    33	
    34	        if not resolved_config.exists():
    35	            raise click.ClickException(f"Config file not found: {resolved_config}")
    36	
    37	        project_root = Path(root).expanduser().resolve() if root is not None else resolved_config.parent
    38	        cfg = load_config(resolved_config)
    39	        return cls(root=project_root, config_path=resolved_config, config=cfg)
    40	
    41	    def resolve_path(self, value: str | Path) -> Path:
    42	        path = Path(value).expanduser()
    43	        if path.is_absolute():
    44	            return path
    45	        return (self.root / path).resolve()
    46	
    47	    @property
    48	    def state_dir(self) -> Path:
    49	        return self.root / ".odooctl"
    50	
    51	    @property
    52	    def compose_file(self) -> Path:
    53	        return self.resolve_path(self.config.runtime.compose_file)
    54	
    55	    @property
    56	    def backups_dir(self) -> Path:
    57	        return self.resolve_path(self.config.backups.local_path)
    58	
    59	    @property
    60	    def odoo_config_path(self) -> Path:
    61	        return self.resolve_path(self.config.odoo.config_path)
    62	
    63	    def sanitization_sql_files(self) -> list[Path]:
    64	        return [self.resolve_path(path) for path in self.config.sanitization.sql_files]
     1	"""Read-only project and environment routes.
     2	
     3	All reads come from the registry, project config, metadata store, and
     4	operation store — no Docker/Postgres/git calls. Satisfies the runner contract.
     5	"""
     6	from __future__ import annotations
     7	
     8	from fastapi import APIRouter, Depends, HTTPException, Request
     9	
    10	from odooctl.api.auth import enforce_project_scope, require_action
    11	from odooctl.security.rbac import Action
    12	
    13	router = APIRouter()
    14	
    15	
    16	def _registry(request: Request):
    17	    return request.app.state.registry_loader()
    18	
    19	
    20	def _load_ctx(request: Request, project: str):
    21	    from odooctl.context import ProjectContext
    22	
    23	    # A per-project token must not reach another project's config/state.
    24	    enforce_project_scope(request, project)
    25	    reg = _registry(request)
    26	    proj = reg.projects.get(project)
    27	    if proj is None:
    28	        raise HTTPException(status_code=404, detail=f"Project {project!r} not found")
    29	    try:
    30	        return ProjectContext.from_config_path(proj.config, root=proj.path)
    31	    except Exception as exc:
    32	        raise HTTPException(status_code=404, detail=str(exc)) from exc
    33	
    34	
    35	@router.get("/projects")
    36	def list_projects(
    37	    request: Request,
    38	    principal=Depends(require_action(Action.READ)),
    39	):
    40	    reg = _registry(request)
    41	    names = sorted(reg.projects.keys())
    42	    # A token scoped to one project only learns of that project.
    43	    claim = str(getattr(request.state, "token_project", None) or "")
    44	    if claim != "*":
    45	        names = [n for n in names if n == claim]
    46	    return {"projects": names}
    47	
    48	
    49	@router.get("/projects/{project}")
    50	def get_project(
    51	    project: str,
    52	    request: Request,
    53	    principal=Depends(require_action(Action.READ)),
    54	):
    55	    enforce_project_scope(request, project)
    56	    reg = _registry(request)
    57	    proj = reg.projects.get(project)
    58	    if proj is None:
    59	        raise HTTPException(status_code=404, detail=f"Project {project!r} not found")
    60	    return {"name": proj.name, "path": str(proj.path)}
    61	
    62	
    63	@router.get("/projects/{project}/environments")
    64	def list_environments(
    65	    project: str,
    66	    request: Request,
    67	    principal=Depends(require_action(Action.READ)),
    68	):
    69	    ctx = _load_ctx(request, project)
    70	    envs = [
    71	        {
    72	            "name": name,
    73	            "branch": env.branch,
    74	            "domain": env.domain,
    75	            "tier": env.tier,
    76	            "protected": env.protected,
    77	        }
    78	        for name, env in ctx.config.environments.items()
    79	    ]
    80	    return {"environments": envs}
    81	
    82	
    83	@router.get("/projects/{project}/status")
    84	def get_project_status(
    85	    project: str,
    86	    request: Request,
    87	    principal=Depends(require_action(Action.STATUS)),
    88	):
    89	    from odooctl.metadata.store import MetadataStore
    90	    from odooctl.operations.store import OperationStore
    91	
    92	    ctx = _load_ctx(request, project)
    93	    meta = MetadataStore(ctx.state_dir)
    94	    op_store = OperationStore(ctx.state_dir)
    95	
    96	    envs = []
    97	    for name in ctx.config.environments:
    98	        dep = meta.latest_deployment(name) or {}
    99	        bak = meta.latest_backup(name) or {}
   100	        envs.append(
   101	            {
   102	                "name": name,
   103	                "last_deployment_status": dep.get("status", "unknown"),
   104	                "last_deployment_commit": dep.get("commit", "unknown"),
   105	                "latest_backup": bak.get("timestamp", "unknown"),
   106	            }
   107	        )
   108	
   109	    recent_ops = [
   110	        {
   111	            "op_id": op.id,
   112	            "kind": op.kind.value,
   113	            "environment": op.environment,
   114	            "status": op.status.value,
   115	            "created_at": op.created_at,
   116	        }
   117	        for op in op_store.list_all(limit=10)
   118	    ]
   119	
   120	    return {
   121	        "project": ctx.config.project.name,
   122	        "environments": envs,
   123	        "recent_operations": recent_ops,
   124	    }
   125	
   126	
   127	@router.get("/projects/{project}/backups")
   128	def list_backups(
   129	    project: str,
   130	    request: Request,
   131	    principal=Depends(require_action(Action.BACKUPS)),
   132	):
   133	    from odooctl.metadata.store import MetadataStore
   134	
   135	    ctx = _load_ctx(request, project)
   136	    meta = MetadataStore(ctx.state_dir)
   137	
   138	    backups = []
   139	    for name in ctx.config.environments:
   140	        bak = meta.latest_backup(name)
   141	        if bak:
   142	            backups.append(bak)
   143	
   144	    # Also scan backup manifests directory
   145	    backup_manifests_dir = ctx.state_dir / "backups"
   146	    if backup_manifests_dir.exists():
   147	        for manifest_file in sorted(backup_manifests_dir.glob("*.json")):
   148	            if manifest_file.stem.endswith("-latest"):
   149	                continue
   150	            try:
   151	                import json
   152	
   153	                data = json.loads(manifest_file.read_text())
   154	                if data not in backups:
   155	                    backups.append(data)
   156	            except Exception:
   157	                continue
   158	
   159	    return {"backups": backups}
   160	
   161	
   162	@router.get("/projects/{project}/restore-points")
   163	def list_restore_points(
   164	    project: str,
   165	    request: Request,
   166	    environment: str | None = None,
   167	    principal=Depends(require_action(Action.BACKUPS)),
   168	):
   169	    from odooctl.services.restore_points import list_restore_points as _list_rp
   170	
   171	    ctx = _load_ctx(request, project)
   172	    points = _list_rp(ctx.backups_dir, environment=environment)
   173	    return {
   174	        "restore_points": [
   175	            {
   176	                "backup_id": p.backup_id,
   177	                "environment": p.environment,
   178	                "timestamp": p.timestamp,
   179	                "integrity": p.integrity,
   180	            }
   181	            for p in points
   182	        ]
   183	    }
   184	
   185	
   186	@router.get("/projects/{project}/audit")
   187	def get_audit(
   188	    project: str,
   189	    request: Request,
   190	    principal=Depends(require_action(Action.AUDIT)),
   191	):
   192	    from odooctl.operations.audit import AuditStore
   193	
   194	    ctx = _load_ctx(request, project)
   195	    audit = AuditStore(ctx.state_dir)
   196	    entries = audit.load_chain()
   197	    return {
   198	        "entries": [
   199	            {
   200	                "actor": e.actor,
   201	                "action": e.action,
   202	                "target": e.target,
   203	                "outcome": e.outcome,
   204	                "op_id": e.op_id,
   205	                "timestamp": e.timestamp,
   206	            }
   207	            for e in entries
   208	        ]
   209	    }
     1	"""Durable operation queue — written by the API, consumed by the runner.
     2	
     3	Queue entries are plain JSON files in ``{state_dir}/queue/``. The API writes
     4	``{op_id}.json``; the runner atomically renames it to ``{op_id}.running``
     5	(POSIX rename is atomic within the same filesystem) before executing, then
     6	removes it on success or renames it to ``{op_id}.failed`` on error.
     7	
     8	This module has NO privileged imports — it must satisfy the runner contract
     9	(see ``odooctl.security.runner_contract``).
    10	"""
    11	from __future__ import annotations
    12	
    13	import json
    14	from dataclasses import dataclass
    15	from datetime import datetime, timezone
    16	from pathlib import Path
    17	
    18	
    19	def _utcnow() -> str:
    20	    return datetime.now(timezone.utc).isoformat()
    21	
    22	
    23	@dataclass
    24	class QueueEntry:
    25	    op_id: str
    26	    kind: str
    27	    project: str
    28	    environment: str
    29	    actor: str
    30	    params_redacted: dict
    31	    token: str
    32	    created_at: str
    33	
    34	    def to_json(self) -> str:
    35	        return json.dumps(
    36	            {
    37	                "op_id": self.op_id,
    38	                "kind": self.kind,
    39	                "project": self.project,
    40	                "environment": self.environment,
    41	                "actor": self.actor,
    42	                "params_redacted": self.params_redacted,
    43	                "token": self.token,
    44	                "created_at": self.created_at,
    45	            },
    46	            indent=2,
    47	        )
    48	
    49	    @classmethod
    50	    def from_json(cls, text: str) -> "QueueEntry":
    51	        d = json.loads(text)
    52	        return cls(
    53	            op_id=d["op_id"],
    54	            kind=d["kind"],
    55	            project=d["project"],
    56	            environment=d["environment"],
    57	            actor=d["actor"],
    58	            params_redacted=d.get("params_redacted", {}),
    59	            token=d["token"],
    60	            created_at=d.get("created_at", ""),
    61	        )
    62	
    63	    @classmethod
    64	    def create(
    65	        cls,
    66	        op_id: str,
    67	        kind: str,
    68	        project: str,
    69	        environment: str,
    70	        actor: str,
    71	        params_redacted: dict,
    72	        token: str,
    73	    ) -> "QueueEntry":
    74	        return cls(
    75	            op_id=op_id,
    76	            kind=kind,
    77	            project=project,
    78	            environment=environment,
    79	            actor=actor,
    80	            params_redacted=params_redacted,
    81	            token=token,
    82	            created_at=_utcnow(),
    83	        )
    84	
    85	
    86	class OperationQueue:
    87	    """File-backed durable operation queue.
    88	
    89	    Each pending entry is ``{state_dir}/queue/{op_id}.json``.
    90	    Claiming renames it to ``{op_id}.running`` atomically (POSIX).
    91	    """
    92	
    93	    def __init__(self, state_dir: Path) -> None:
    94	        self._root = state_dir / "queue"
    95	        self._root.mkdir(parents=True, exist_ok=True)
    96	
    97	    def enqueue(self, entry: QueueEntry) -> None:
    98	        target = self._root / f"{entry.op_id}.json"
    99	        tmp = self._root / f"{entry.op_id}.json.tmp"
   100	        tmp.write_text(entry.to_json())
   101	        tmp.rename(target)
   102	
   103	    def cancel(self, op_id: str) -> None:
   104	        """Remove a pending queue entry so the runner cannot claim it."""
   105	        try:
   106	            (self._root / f"{op_id}.json").unlink()
   107	        except FileNotFoundError:
   108	            pass
   109	
   110	    def claim_next(self) -> QueueEntry | None:
   111	        """Atomically claim the oldest pending entry, or return None."""
   112	        candidates = sorted(
   113	            self._root.glob("*.json"),
   114	            key=lambda p: p.stat().st_mtime,
   115	        )
   116	        for path in candidates:
   117	            claimed = path.with_suffix(".running")
   118	            try:
   119	                path.rename(claimed)
   120	            except (FileNotFoundError, OSError):
   121	                continue
   122	            try:
   123	                return QueueEntry.from_json(claimed.read_text())
   124	            except Exception:
   125	                claimed.rename(path.with_suffix(".corrupt"))
   126	                continue
   127	        return None
   128	
   129	    def complete(self, op_id: str) -> None:
   130	        path = self._root / f"{op_id}.running"
   131	        if path.exists():
   132	            path.unlink()
   133	
   134	    def fail(self, op_id: str) -> None:
   135	        path = self._root / f"{op_id}.running"
   136	        if path.exists():
   137	            path.rename(self._root / f"{op_id}.failed")
     1	"""Central redaction helpers.
     2	
     3	These helpers scrub secret material out of arbitrary strings and mappings
     4	before they reach logs, operation events, audit records, or CLI output. Two
     5	classes of secret are handled:
     6	
     7	1. Known literal secret *values* (e.g. a resolved DB password) — replaced with
     8	   a placeholder wherever they appear as substrings.
     9	2. Env-ref interpolations of the form ``${VAR:-default}`` — the default may be
    10	   a real secret, so it is dropped and only the ``${VAR}`` reference is kept.
    11	
    12	The functions never raise on unexpected shapes; they recurse through dicts,
    13	lists, and tuples and leave non-string scalars untouched.
    14	"""
    15	from __future__ import annotations
    16	
    17	import re
    18	from typing import Any
    19	
    20	PLACEHOLDER = "***"
    21	
    22	# ${VAR:-default} / ${VAR:default} / ${VAR-default} — capture VAR, drop default.
    23	_ENV_DEFAULT_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-|:)[^}]*\}")
    24	
    25	# Keys whose values are treated as secret when redacting mappings.
    26	_SECRET_KEY_TOKENS = ("password", "secret", "token", "key", "passwd", "pass")
    27	
    28	
    29	def strip_env_defaults(text: str) -> str:
    30	    """Collapse ``${VAR:-default}`` to ``${VAR}`` so secret defaults never leak.
    31	
    32	    A bare ``${VAR}`` (no default) is left unchanged.
    33	    """
    34	    return _ENV_DEFAULT_RE.sub(lambda m: "${" + m.group(1) + "}", str(text))
    35	
    36	
    37	def _is_secret_key(key: Any) -> bool:
    38	    if not isinstance(key, str):
    39	        return False
    40	    low = key.lower()
    41	    return any(tok in low for tok in _SECRET_KEY_TOKENS)
    42	
    43	
    44	def redact_text(text: str, secret_values: object = (), *, placeholder: str = PLACEHOLDER) -> str:
    45	    """Redact *text*: drop env-ref defaults, then mask any known secret values.
    46	
    47	    *secret_values* is any iterable of literal secret strings to mask. Longer
    48	    values are masked first so a value that contains another is fully covered.
    49	    """
    50	    out = strip_env_defaults(str(text))
    51	    values = sorted(
    52	        {str(v) for v in secret_values if v is not None and str(v) != ""},
    53	        key=len,
    54	        reverse=True,
    55	    )
    56	    for value in values:
    57	        if value:
    58	            out = out.replace(value, placeholder)
    59	    return out
    60	
    61	
    62	def redact(value: Any, secret_values: object = (), *, placeholder: str = PLACEHOLDER) -> Any:
    63	    """Recursively redact *value* (str / mapping / list / tuple).
    64	
    65	    Mapping entries whose key looks secret are masked **regardless of the value
    66	    type** — a numeric, boolean, or nested-mapping value under a ``*password*``
    67	    key is replaced with the placeholder, not passed through. The one exception
    68	    is a string that, after stripping env-ref defaults, is a bare ``${VAR}``
    69	    reference: that carries no secret material and is preserved. All other
    70	    string values additionally have env-ref defaults stripped and known secret
    71	    literals masked.
    72	    """
    73	    if isinstance(value, str):
    74	        return redact_text(value, secret_values, placeholder=placeholder)
    75	    if isinstance(value, dict):
    76	        result: dict = {}
    77	        for k, v in value.items():
    78	            if _is_secret_key(k):
    79	                # Preserve a bare env reference (default stripped); mask anything
    80	                # else under a secret-looking key, whatever its type.
    81	                if isinstance(v, str):
    82	                    stripped = strip_env_defaults(v)
    83	                    result[k] = stripped if stripped.startswith("${") and stripped.endswith("}") else placeholder
    84	                else:
    85	                    result[k] = placeholder
    86	            else:
    87	                result[k] = redact(v, secret_values, placeholder=placeholder)
    88	        return result
    89	    if isinstance(value, (list, tuple)):
    90	        redacted = [redact(item, secret_values, placeholder=placeholder) for item in value]
    91	        return type(value)(redacted)
    92	    return value
odooctl/odoo/module_update.py:53:    run(
odooctl/odoo/module_update.py:80:    compose.exec(
odooctl/adapters/db.py:64:        run(self._cmd("pg_isready", "-d", db_name, *self.base_args()), cwd=self.project_dir, env=self._password_env())
odooctl/adapters/db.py:99:        run(
odooctl/adapters/db.py:105:        run(self._cmd("dropdb", *self.base_args(), db_name, "--if-exists"), cwd=self.project_dir, env=self._password_env(), stream=True)
odooctl/adapters/db.py:106:        run(self._cmd("createdb", *self.base_args(), db_name), cwd=self.project_dir, env=self._password_env(), stream=True)
odooctl/adapters/db.py:119:        run(self._cmd("psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", sql), cwd=self.project_dir, env=self._password_env(), stream=True)
odooctl/adapters/filestore.py:27:        run(["tar", "-cf", str(output), "-C", str(source.parent), source.name], stream=True)
odooctl/adapters/filestore.py:36:            run(["tar", "-xf", str(archive), "-C", tmpdir], stream=True)
odooctl/adapters/filestore.py:88:        self.compose.exec_capture_bytes(
odooctl/adapters/filestore.py:97:        self.compose.exec(self.service, ["mkdir", "-p", parent], stream=True)
odooctl/adapters/filestore.py:98:        self.compose.exec(self.service, ["rm", "-rf", f"{parent}/{name}"], stream=True)
odooctl/adapters/filestore.py:99:        self.compose.exec_pipe_stdin(
odooctl/adapters/filestore.py:108:        self.compose.exec(self.service, ["mkdir", "-p", f"{self.root}/filestore"], stream=True)
odooctl/adapters/filestore.py:109:        self.compose.exec(self.service, ["rm", "-rf", dst], stream=True)
odooctl/adapters/filestore.py:110:        self.compose.exec(self.service, ["cp", "-a", src, dst], stream=True)
odooctl/adapters/filestore.py:114:        self.compose.exec(self.service, ["rm", "-rf", target], stream=True)
odooctl/adapters/postgres.py:17:        run(["psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", "SELECT 1"], env=self.env())
odooctl/adapters/postgres.py:20:        run(["pg_dump", *self.base_args(), "-Fc", "-d", db_name, "-f", str(output)], env=self.env(), stream=True)
odooctl/adapters/postgres.py:24:        run(["pg_restore", *self.base_args(), "-d", db_name, str(dump_path)], env=self.env(), stream=True)
odooctl/adapters/postgres.py:27:        run(["dropdb", *self.base_args(), db_name, "--if-exists"], env=self.env(), stream=True)
odooctl/adapters/postgres.py:28:        run(["createdb", *self.base_args(), db_name], env=self.env(), stream=True)
odooctl/adapters/postgres.py:31:        run(["psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-f", str(sql_file)], env=self.env(), stream=True)
odooctl/adapters/postgres.py:34:        run(["psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", sql], env=self.env(), stream=True)
odooctl/services/deploy.py:24:    result = run(["git", "status", "--porcelain"], check=False, cwd=str(cwd) if cwd is not None else None)
odooctl/services/deploy.py:78:        run(["git", "fetch", "--all"], stream=True, cwd=str(ctx.project.root))
odooctl/services/deploy.py:79:        run(["git", "checkout", selected_branch], stream=True, cwd=str(ctx.project.root))
odooctl/services/deploy.py:80:        run(["git", "pull", "--ff-only"], stream=True, cwd=str(ctx.project.root))
odooctl/services/branch.py:15:    result = run(["git", "rev-parse", "--short", ref], check=False, cwd=cwd)
odooctl/services/branch.py:21:    result = run(["git", "rev-list", "--count", f"{a}..{b}"], check=False, cwd=cwd)
odooctl/services/backup.py:39:    r = shell_run(["git", "rev-parse", "--short", "HEAD"], check=False, cwd=str(cwd) if cwd is not None else None)
odooctl/services/promote.py:31:    result = run(["git", "status", "--porcelain"], check=False, cwd=cwd)
odooctl/services/promote.py:119:        run(["git", "fetch", "--all"], stream=True, cwd=str(ctx.project.root))
odooctl/services/promote.py:120:        run(["git", "checkout", selected_branch], stream=True, cwd=str(ctx.project.root))
odooctl/services/promote.py:122:        run(["git", "merge", "--ff-only", src_env.branch], stream=True, cwd=str(ctx.project.root))
odooctl/services/promote.py:163:                run(["git", "checkout", selected_branch], stream=True, cwd=str(ctx.project.root))
odooctl/services/promote.py:164:                run(["git", "reset", "--hard", pre_promote_commit], stream=True, cwd=str(ctx.project.root))
odooctl/adapters/docker_compose.py:14:        run(self._cmd("pull", *([service] if service else [])), cwd=self.project_dir, stream=True)
odooctl/adapters/docker_compose.py:17:        run(self._cmd("build", *([service] if service else [])), cwd=self.project_dir, stream=True)
odooctl/adapters/docker_compose.py:20:        run(self._cmd("up", "-d", *([service] if service else [])), cwd=self.project_dir, stream=True)
odooctl/adapters/docker_compose.py:23:        run(self._cmd("restart", service), cwd=self.project_dir, stream=True)
odooctl/adapters/docker_compose.py:33:        run(self._cmd(*args), cwd=self.project_dir, stream=True)
odooctl/adapters/docker_compose.py:36:        return run(self._cmd("ps"), cwd=self.project_dir, check=False).stdout
odooctl/adapters/docker_compose.py:50:        subprocess environment — so secrets never appear on argv.
odooctl/adapters/docker_compose.py:55:        run(

exec
/bin/bash -lc "rg -n \"password\\(\\)|service_password\\(\\)|reveal\\(\\)|PASSWORD|TOKEN|SECRET\" odooctl | head -250; rg -n \"CommandError|\\.result\\.args|result\\.args\" . --glob '*.py'; sed -n '95,170p' odooctl/migration/rehearse.py | nl -ba -v95; sed -n '120,210p' odooctl/security/secrets.py | nl -ba -v120" in /home/dev/odooctl
 succeeded in 0ms:
odooctl/runner/worker.py:475:        kind=PrincipalKind.TOKEN,
odooctl/commands/setup.py:90:                "password_env": "ODOO_DB_PASSWORD",
odooctl/commands/migrate.py:48:            env={"PGPASSWORD": os.getenv(pg.password_env, "")},
odooctl/commands/github_actions.py:58:          ODOO_DB_PASSWORD: ${{{{ secrets.ODOO_DB_PASSWORD }}}}
odooctl/commands/security.py:139:    typer.echo(value.reveal())
odooctl/adapters/db.py:52:            "PGPASSWORD",
odooctl/adapters/db.py:58:        return {"PGPASSWORD": self.config.service_password()}
odooctl/adapters/postgres.py:11:        return {"PGPASSWORD": self.config.password()}
odooctl/config.py:139:    password_env: str = "ODOO_DB_PASSWORD"
odooctl/config.py:410:  password_env: ODOO_DB_PASSWORD
odooctl/config.py:419:    secret_key_env: ODOO_S3_SECRET_KEY
odooctl/catalog/manifests/companions.yaml:10:    PGADMIN_DEFAULT_PASSWORD: "${PGADMIN_PASSWORD}"
odooctl/catalog/manifests/companions.yaml:35:    MINIO_ROOT_PASSWORD: "${MINIO_ROOT_PASSWORD}"
odooctl/catalog/manifests/companions.yaml:47:    N8N_BASIC_AUTH_PASSWORD: "${N8N_PASSWORD}"
odooctl/importer/report.py:23:            "using placeholder 'ODOO_DB_PASSWORD'. Update before deploying."
odooctl/importer/report.py:51:    password_env = detected.db_password_ref or "ODOO_DB_PASSWORD"
odooctl/catalog/render.py:27:            "password_env": "ODOO_DB_PASSWORD",
odooctl/catalog/schema.py:46:                f"auth_env must be an env-var name (e.g. GITHUB_TOKEN), not a literal value or reference: {v!r}"
odooctl/importer/detect.py:21:_SECRET_KEYS = frozenset({"PASSWORD", "SECRET", "KEY", "TOKEN", "PASS"})
odooctl/importer/detect.py:26:    return any(tok in upper for tok in _SECRET_KEYS)
odooctl/importer/detect.py:116:    _PASS_KEYS = {"PASSWORD", "DB_PASSWORD", "PGPASSWORD", "ODOO_PASSWORD"}
odooctl/importer/detect.py:131:                db_password_ref = "ODOO_DB_PASSWORD"
odooctl/api/auth.py:65:        kind=PrincipalKind.TOKEN,
odooctl/utils/shell.py:9:SENSITIVE_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "KEY", "PASSWD")
odooctl/utils/shell.py:10:DEFAULT_REDACTION_MIN_SECRET_LENGTH = 6
odooctl/utils/shell.py:30:    min_secret_length: int = DEFAULT_REDACTION_MIN_SECRET_LENGTH,
odooctl/odoo/module_update.py:27:    """Resolve the configured password env var to a PGPASSWORD mapping.
odooctl/odoo/module_update.py:30:    process through the PGPASSWORD environment variable, which psycopg2
odooctl/odoo/module_update.py:38:    return {"PGPASSWORD": value}
odooctl/security/principals.py:53:    TOKEN = "token"
odooctl/security/rbac.py:45:    SECRETS = "secrets"          # manage secret store
odooctl/security/rbac.py:61:        Action.SECRETS,
odooctl/security/rbac.py:69:    {Action.DEPLOY, Action.CLONE, Action.RESTORE, Action.PROMOTE, Action.ENV, Action.SECRETS}
odooctl/security/secrets.py:10:  way to obtain the raw string is the explicit ``.reveal()`` call.
odooctl/security/secrets.py:32:KEY_ENV_VAR = "ODOOCTL_SECRET_KEY"
odooctl/security/secrets.py:36:# Value wrapper — never reveals itself except via .reveal()
odooctl/security/secrets.py:42:    SecretValue cannot leak the underlying string. Call ``.reveal()`` to obtain
odooctl/security/secrets.py:307:        must explicitly ``.reveal()`` to obtain the raw string.
odooctl/security/secrets.py:328:                values.add(self.get(name).reveal())
odooctl/security/secrets.py:349:    2. ``ODOOCTL_SECRET_KEY`` env var, derived against the persisted salt.
odooctl/security/redaction.py:26:_SECRET_KEY_TOKENS = ("password", "secret", "token", "key", "passwd", "pass")
odooctl/security/redaction.py:41:    return any(tok in low for tok in _SECRET_KEY_TOKENS)
./odooctl/utils/shell.py:20:class CommandError(RuntimeError):
./odooctl/utils/shell.py:22:        message = f"Command failed ({result.returncode}): {' '.join(result.args)}\n{result.stderr}"
./odooctl/utils/shell.py:62:        raise CommandError(result)
./odooctl/utils/shell.py:93:        raise CommandError(result)
./odooctl/utils/shell.py:113:        raise CommandError(result)
./odooctl/utils/shell.py:157:        raise CommandError(result)
./tests/test_shell.py:64:    from odooctl.utils.shell import CommandError, run_pipe
./tests/test_shell.py:66:    with pytest.raises(CommandError):
./tests/test_shell.py:73:    from odooctl.utils.shell import CommandError, run_pipe
./tests/test_shell.py:75:    with pytest.raises(CommandError) as excinfo:
./tests/test_shell.py:103:    """CommandError's composed message (args + stderr) must be redacted."""
./tests/test_shell.py:104:    from odooctl.utils.shell import CommandError, CommandResult
./tests/test_shell.py:107:    err = CommandError(
./tests/test_shell.py:113:    assert err.result.args[-1] == "argv-secret-value-123"
./tests/test_shell.py:120:    from odooctl.utils.shell import CommandError, run
./tests/test_shell.py:124:    with pytest.raises(CommandError) as excinfo:
    95	    :param upgrade_fn: Runs the Odoo upgrade on *throwaway_db*; returns :class:`UpgradeResult`.
    96	    :param report_dir: Directory where the JSON report is written (created if absent).
    97	    :param keep: Leave the throwaway DB intact after rehearsal (useful for debugging).
    98	    :param throwaway_suffix: Suffix appended to *source_db* to form the throwaway DB name.
    99	    :param requires_openupgrade: ``True`` when the migration matrix marks this path as
   100	        requiring OpenUpgrade.  If ``True`` and ``use_openupgrade`` is ``False``, the
   101	        rehearsal fails immediately with a clear message rather than running a standard
   102	        ``odoo --update all`` that cannot perform a real cross-major upgrade.
   103	    :param use_openupgrade: ``True`` when the caller's *upgrade_fn* uses OpenUpgrade.
   104	    """
   105	    throwaway_db = f"{source_db}{throwaway_suffix}"
   106	    if throwaway_db == source_db:
   107	        raise RuntimeError(
   108	            f"Throwaway DB name {throwaway_db!r} must differ from source DB "
   109	            f"{source_db!r}; use a non-empty throwaway_suffix."
   110	        )
   111	
   112	    # Early exit: path requires OpenUpgrade but caller did not request it.
   113	    # Running odoo --update all on a throwaway clone cannot perform a real cross-major
   114	    # upgrade, so claiming success would be misleading.
   115	    if requires_openupgrade and not use_openupgrade:
   116	        msg = (
   117	            f"Upgrade path {source_version} → {target_version} requires OpenUpgrade. "
   118	            "Re-run with --openupgrade (and ensure the OpenUpgrade container is set up)."
   119	        )
   120	        report = RehearsalReport(
   121	            status="failed",
   122	            source_env=source_env,
   123	            source_version=source_version,
   124	            target_version=target_version,
   125	            installed_modules=[],
   126	            failed_modules=[],
   127	            warnings=[],
   128	            duration_seconds=0.0,
   129	            healthcheck_status="skipped",
   130	            log_path=None,
   131	            cleanup_status="cleaned",
   132	            next_actions=[
   133	                f"Re-run: odooctl migrate rehearse --env {source_env} "
   134	                f"--to {target_version} --openupgrade",
   135	                "Ensure the OpenUpgrade container is set up per docs/migration.md.",
   136	            ],
   137	            message=msg,
   138	        )
   139	        _save_report_to_dir(report, report_dir)
   140	        return report
   141	
   142	    start = time.monotonic()
   143	    status = "failed"
   144	    message: str | None = None
   145	    failed_modules: list[str] = []
   146	    warnings: list[str] = []
   147	    installed_modules: list[str] = []
   148	    healthcheck_status = "skipped"
   149	    log_path: str | None = None
   150	    cleanup_status = "cleaned"
   151	    tmp_dump: Path | None = None
   152	
   153	    try:
   154	        # Step 1 — clone source DB into throwaway via dump → restore.
   155	        # dump() is a read-only pg_dump on the source; restore() targets throwaway_db only.
   156	        with tempfile.NamedTemporaryFile(
   157	            prefix="odooctl-mig-", suffix=".dump", delete=False
   158	        ) as tmp:
   159	            tmp_dump = Path(tmp.name)
   160	
   161	        db_adapter.dump(source_db, tmp_dump)
   162	        db_adapter.restore(throwaway_db, tmp_dump)
   163	
   164	        # Step 2 — run the upgrade against the throwaway DB.
   165	        upgrade_result = upgrade_fn(throwaway_db, target_version)
   166	        log_path = upgrade_result.log_ref
   167	        failed_modules = upgrade_result.failed_modules
   168	        warnings = upgrade_result.warnings
   169	        installed_modules = upgrade_result.installed_after
   170	
   120	    if not hmac.compare_digest(mac, expected):
   121	        raise SecretDecryptionError("authentication failed (wrong key or tampered data)")
   122	    ks = _keystream(enc_key, nonce, len(ct))
   123	    return bytes(a ^ b for a, b in zip(ct, ks)).decode("utf-8")
   124	
   125	
   126	def derive_key(passphrase: str, salt: bytes) -> bytes:
   127	    """Derive a 32-byte master key from a passphrase via PBKDF2-HMAC-SHA256."""
   128	    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)
   129	
   130	
   131	# --------------------------------------------------------------------------- #
   132	# Metadata record — carries NO secret value
   133	# --------------------------------------------------------------------------- #
   134	@dataclass(frozen=True)
   135	class SecretRecord:
   136	    """Non-sensitive metadata describing a stored or referenced secret."""
   137	
   138	    name: str
   139	    source: str  # "stored" | "env"
   140	    version: int = 1
   141	    created_at: str = ""
   142	    rotated_at: str = ""
   143	    rotation_interval_days: int | None = None
   144	    env_var: str | None = None  # set when source == "env"
   145	
   146	    def is_due_for_rotation(self, *, now: datetime | None = None) -> bool:
   147	        if not self.rotation_interval_days or not self.rotated_at:
   148	            return False
   149	        now = now or datetime.now(timezone.utc)
   150	        try:
   151	            rotated = datetime.fromisoformat(self.rotated_at)
   152	        except ValueError:
   153	            return False
   154	        return now >= rotated + timedelta(days=self.rotation_interval_days)
   155	
   156	    def to_public_dict(self) -> dict:
   157	        """Public, value-free view safe for CLI/JSON/audit output."""
   158	        return {
   159	            "name": self.name,
   160	            "source": self.source,
   161	            "version": self.version,
   162	            "created_at": self.created_at,
   163	            "rotated_at": self.rotated_at,
   164	            "rotation_interval_days": self.rotation_interval_days,
   165	            "env_var": self.env_var,
   166	            "rotation_due": self.is_due_for_rotation(),
   167	        }
   168	
   169	
   170	def _utcnow() -> str:
   171	    return datetime.now(timezone.utc).isoformat()
   172	
   173	
   174	def _write_private_bytes(path: Path, data: bytes) -> None:
   175	    """Atomically create/overwrite *path* readable only by its owner (0600).
   176	
   177	    The file is created with mode ``0o600`` in the ``os.open`` call itself, so
   178	    there is no window in which it exists at looser permissions before a
   179	    separate ``chmod`` — the flaw of write-then-chmod. ``fchmod`` on the open
   180	    descriptor additionally tightens a file left over from a prior crash without
   181	    introducing a path-based race.
   182	    """
   183	    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
   184	    with os.fdopen(fd, "wb") as fh:
   185	        os.fchmod(fh.fileno(), 0o600)
   186	        fh.write(data)
   187	
   188	
   189	# --------------------------------------------------------------------------- #
   190	# The store
   191	# --------------------------------------------------------------------------- #
   192	class SecretStore:
   193	    """Encrypted local secret store keyed by secret name.
   194	
   195	    The on-disk JSON holds only ciphertext envelopes and value-free metadata.
   196	    Stored values are encrypted with *key*; env-referenced secrets persist only
   197	    the env-var name and are resolved from the process environment on read.
   198	    """
   199	
   200	    def __init__(self, path: Path, key: bytes) -> None:
   201	        self.path = Path(path)
   202	        self._key = key
   203	        self.path.parent.mkdir(parents=True, exist_ok=True)
   204	        self._data = self._load()
   205	
   206	    # ----- persistence ---------------------------------------------------- #
   207	    def _load(self) -> dict:
   208	        if not self.path.exists():
   209	            return {"version": STORE_VERSION, "secrets": {}}
   210	        data = json.loads(self.path.read_text())

exec
/bin/bash -lc "sed -n '200,305p' odooctl/security/secrets.py | nl -ba -v200; nl -ba tests/test_shell.py | sed -n '90,135p'; nl -ba odooctl/commands/migrate.py | sed -n '30,65p'" in /home/dev/odooctl
 succeeded in 0ms:
   200	    def __init__(self, path: Path, key: bytes) -> None:
   201	        self.path = Path(path)
   202	        self._key = key
   203	        self.path.parent.mkdir(parents=True, exist_ok=True)
   204	        self._data = self._load()
   205	
   206	    # ----- persistence ---------------------------------------------------- #
   207	    def _load(self) -> dict:
   208	        if not self.path.exists():
   209	            return {"version": STORE_VERSION, "secrets": {}}
   210	        data = json.loads(self.path.read_text())
   211	        data.setdefault("secrets", {})
   212	        return data
   213	
   214	    def _save(self) -> None:
   215	        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
   216	        payload = json.dumps(self._data, indent=2, sort_keys=True).encode("utf-8")
   217	        _write_private_bytes(tmp, payload)
   218	        tmp.replace(self.path)
   219	
   220	    # ----- mutation ------------------------------------------------------- #
   221	    def put(self, name: str, value: str, *, rotation_interval_days: int | None = None) -> SecretRecord:
   222	        """Store (or replace) an encrypted secret value under *name*."""
   223	        now = _utcnow()
   224	        entry = self._data["secrets"].get(name, {})
   225	        record_meta = {
   226	            "source": "stored",
   227	            "cipher": encrypt(self._key, value),
   228	            "version": 1,
   229	            "created_at": entry.get("created_at", now),
   230	            "rotated_at": now,
   231	            "rotation_interval_days": rotation_interval_days
   232	            if rotation_interval_days is not None
   233	            else entry.get("rotation_interval_days"),
   234	        }
   235	        self._data["secrets"][name] = record_meta
   236	        self._save()
   237	        return self.metadata(name)
   238	
   239	    def put_reference(self, name: str, env_var: str, *, rotation_interval_days: int | None = None) -> SecretRecord:
   240	        """Register an env-var *reference*; only the variable name is persisted."""
   241	        now = _utcnow()
   242	        entry = self._data["secrets"].get(name, {})
   243	        self._data["secrets"][name] = {
   244	            "source": "env",
   245	            "env_var": env_var,
   246	            "version": entry.get("version", 1),
   247	            "created_at": entry.get("created_at", now),
   248	            "rotated_at": entry.get("rotated_at", now),
   249	            "rotation_interval_days": rotation_interval_days
   250	            if rotation_interval_days is not None
   251	            else entry.get("rotation_interval_days"),
   252	        }
   253	        self._save()
   254	        return self.metadata(name)
   255	
   256	    def rotate(self, name: str, new_value: str | None = None) -> SecretRecord:
   257	        """Rotate *name*: bump version and stamp ``rotated_at``.
   258	
   259	        Stored secrets require *new_value*. Env references record the rotation
   260	        event only (the value itself rotates in the environment/secret manager).
   261	        """
   262	        if name not in self._data["secrets"]:
   263	            raise SecretNotFound(name)
   264	        entry = self._data["secrets"][name]
   265	        now = _utcnow()
   266	        if entry["source"] == "stored":
   267	            if new_value is None:
   268	                raise ValueError("rotating a stored secret requires a new value")
   269	            entry["cipher"] = encrypt(self._key, new_value)
   270	        entry["version"] = int(entry.get("version", 1)) + 1
   271	        entry["rotated_at"] = now
   272	        self._save()
   273	        return self.metadata(name)
   274	
   275	    def delete(self, name: str) -> None:
   276	        if name not in self._data["secrets"]:
   277	            raise SecretNotFound(name)
   278	        del self._data["secrets"][name]
   279	        self._save()
   280	
   281	    # ----- read ----------------------------------------------------------- #
   282	    def names(self) -> list[str]:
   283	        return sorted(self._data["secrets"].keys())
   284	
   285	    def metadata(self, name: str) -> SecretRecord:
   286	        if name not in self._data["secrets"]:
   287	            raise SecretNotFound(name)
   288	        entry = self._data["secrets"][name]
   289	        return SecretRecord(
   290	            name=name,
   291	            source=entry["source"],
   292	            version=int(entry.get("version", 1)),
   293	            created_at=entry.get("created_at", ""),
   294	            rotated_at=entry.get("rotated_at", ""),
   295	            rotation_interval_days=entry.get("rotation_interval_days"),
   296	            env_var=entry.get("env_var"),
   297	        )
   298	
   299	    def list_metadata(self) -> list[SecretRecord]:
   300	        return [self.metadata(name) for name in self.names()]
   301	
   302	    def get(self, name: str) -> SecretValue:
   303	        """Return the resolved secret value wrapped in :class:`SecretValue`.
   304	
   305	        For ``stored`` secrets this decrypts the envelope; for ``env`` secrets
    90	    """Guard: adapters/services must never build 'sh -c' / 'sh -lc' command strings."""
    91	    from pathlib import Path
    92	
    93	    root = Path(__file__).resolve().parents[1] / "odooctl"
    94	    offenders = []
    95	    for path in root.rglob("*.py"):
    96	        text = path.read_text()
    97	        if '"sh", "-lc"' in text or '"sh", "-c"' in text or "'sh', '-lc'" in text or "'sh', '-c'" in text:
    98	            offenders.append(str(path))
    99	    assert offenders == [], f"shell -c sinks found: {offenders}"
   100	
   101	
   102	def test_command_error_redacts_secrets_in_argv(monkeypatch):
   103	    """CommandError's composed message (args + stderr) must be redacted."""
   104	    from odooctl.utils.shell import CommandError, CommandResult
   105	
   106	    monkeypatch.setenv("ODOOCTL_TEST_PASSWORD", "argv-secret-value-123")
   107	    err = CommandError(
   108	        CommandResult(["odoo", "--db_password", "argv-secret-value-123"], 1, "", "")
   109	    )
   110	    assert "argv-secret-value-123" not in str(err)
   111	    assert "***REDACTED***" in str(err)
   112	    # The raw result stays untouched for programmatic inspection.
   113	    assert err.result.args[-1] == "argv-secret-value-123"
   114	
   115	
   116	def test_run_command_error_does_not_leak_secret_env_value(monkeypatch):
   117	    """A failing run() whose argv/stderr contain a sensitive env value raises a redacted error."""
   118	    import pytest
   119	
   120	    from odooctl.utils.shell import CommandError, run
   121	
   122	    secret = "shell-secret-value-456"
   123	    monkeypatch.setenv("ODOOCTL_TEST_PASSWORD", secret)
   124	    with pytest.raises(CommandError) as excinfo:
   125	        run(
   126	            [
   127	                sys.executable,
   128	                "-c",
   129	                f"import sys; sys.stderr.write('auth failed: {secret}'); sys.exit(3)",
   130	                secret,
   131	            ]
   132	        )
   133	    message = str(excinfo.value)
   134	    assert secret not in message
   135	    assert "***REDACTED***" in message
    30	    env_cfg = cfg.env(env)
    31	    from_version = cfg.project.odoo_version
    32	
    33	    def _list_modules() -> list[str]:
    34	        from odooctl.utils.shell import run
    35	
    36	        pg = cfg.postgres
    37	        result = run(
    38	            [
    39	                "psql",
    40	                "-h", pg.host,
    41	                "-p", str(pg.port),
    42	                "-U", pg.user,
    43	                "-d", env_cfg.db_name,
    44	                "-t",
    45	                "-c",
    46	                "SELECT name FROM ir_module_module WHERE state='installed' ORDER BY name;",
    47	            ],
    48	            env={"PGPASSWORD": os.getenv(pg.password_env, "")},
    49	            check=True,
    50	            stream=False,
    51	        )
    52	        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    53	
    54	    result = scan_modules(
    55	        from_version=from_version,
    56	        to_version=to,
    57	        module_list_fn=_list_modules,
    58	    )
    59	
    60	    typer.echo(f"Scan: {env!r}  {from_version} → {to}")
    61	    typer.echo(f"Installed modules: {len(result.installed_modules)}")
    62	    if result.blockers:
    63	        typer.secho("Blockers:", fg=typer.colors.RED)
    64	        for b in result.blockers:
    65	            typer.echo(f"  [BLOCK] {b}")

codex
The prior shell-injection, protected-environment, password-on-argv, nonce-bounding, project-scoping, and key-length remediations generally hold. I found these remaining issues:

1. **[HIGH] Docker filestore restore extracts an unvalidated archive directly into the live shared filestore root** — [odooctl/adapters/filestore.py:94](/home/dev/odooctl/odooctl/adapters/filestore.py:94)  
   `restore_archive()` deletes the target, then runs `tar -xf - -C /.../filestore` without validating members or requiring them to live beneath the expected database directory. A backup containing `another_db/...`, absolute paths, traversal components, hard links, or symlinks can overwrite sibling filestores or other container files, depending on tar behavior. Manifest checksums establish consistency, not authenticity—a malicious/imported backup can supply matching checksums.  
   **Fix:** inspect every archive member before extraction; reject absolute paths, `..`, links/devices, and anything outside exactly `<target-name>/`. Extract into a private staging directory/volume path, verify the resulting tree, then rename it into place.

2. **[HIGH] Restore/clone replaces the live filestore before DB preparation and promotion are known to succeed** — [odooctl/services/restore.py:142](/home/dev/odooctl/odooctl/services/restore.py:142), [odooctl/services/restore.py:179](/home/dev/odooctl/odooctl/services/restore.py:179), [odooctl/services/clone.py:83](/home/dev/odooctl/odooctl/services/clone.py:83)  
   Both restore paths replace the target filestore before sanitization and DB swap; clone does likewise. If sanitization or `swap_temp_database()` fails, the old live DB remains—or is dropped midway—while its filestore has already been destroyed and replaced. The advertised verify-before-destroy guarantee therefore covers only the dump restoration, not the complete Odoo state.  
   **Fix:** stage the filestore alongside the temporary DB, complete sanitization, then promote both with rollback bookkeeping. Preserve the previous filestore until DB promotion succeeds and restore it if any later step fails.

3. **[HIGH] Database “swap” destroys the live DB before the replacement rename succeeds** — [odooctl/odoo/db_swap.py:61](/home/dev/odooctl/odooctl/odoo/db_swap.py:61)  
   `swap_temp_database()` terminates connections, drops the target, and only then renames the temporary DB. A rename failure—permissions, conflicting database, connection loss, or malformed/colliding temp name—leaves the live database absent. This is not atomic despite service comments calling it so.  
   **Fix:** rename the live DB to a unique rollback name first, rename the prepared DB into place, and only drop the rollback DB after successful promotion and verification. On failure, rename the old DB back. Serialize the complete sequence with an appropriate lock.

4. **[MED] `CommandError` still retains secrets in its public `result.args` object** — [odooctl/utils/shell.py:20](/home/dev/odooctl/odooctl/utils/shell.py:20)  
   The exception string is redacted, but `self.result` is the original object, including raw argv. The test explicitly preserves this behavior. Exception serializers, debug handlers, telemetry, or code logging `exc.result` can therefore expose a password or token supplied by a future/third-party caller. Additionally, `CommandError` redacts its composed message using `os.environ`, not the merged per-call environment.  
   **Fix:** store a fully redacted public `CommandResult` on the exception; keep raw results private only if indispensable. Pass the merged environment/redaction values into exception construction, and prohibit secrets in argv at adapter boundaries.

5. **[MED] Audit-chain keying remains optional, so the claimed remediation is bypassable by default** — [odooctl/operations/audit.py:25](/home/dev/odooctl/odooctl/operations/audit.py:25), [odooctl/operations/audit.py:42](/home/dev/odooctl/odooctl/operations/audit.py:42)  
   Without `ODOOCTL_AUDIT_KEY`, both chain links and the high-water mark use attacker-recomputable SHA-256. Anyone able to alter state files can edit entries and regenerate both `audit.jsonl` and `audit.hwm`, after which `verify()` succeeds. The runner only warns and continues unkeyed.  
   **Fix:** require a strong, separately managed audit key at runner/API startup, fail closed when absent, and avoid storing it with the audit files. Provide an explicit migration mode for legacy unkeyed chains.

6. **[MED] Registry config-path containment is not enforced by API or runner loaders** — [odooctl/api/routes_operations.py:75](/home/dev/odooctl/odooctl/api/routes_operations.py:75), [odooctl/api/routes_operations.py:88](/home/dev/odooctl/odooctl/api/routes_operations.py:88), [odooctl/api/routes_projects.py:20](/home/dev/odooctl/odooctl/api/routes_projects.py:20), [odooctl/runner/worker.py:190](/home/dev/odooctl/odooctl/runner/worker.py:190)  
   CLI project resolution uses `_contained_config_path()`, but these paths call `ProjectContext.from_config_path(proj.config, root=proj.path)` directly. A hand-edited registry entry with `config="../../attacker/odooctl.yml"` is resolved and loaded outside the registered root. The privileged runner can subsequently execute operations using that external configuration.  
   **Fix:** centralize registry-to-context resolution in one function that always validates both the project root and resolved config path; use it in CLI, API, operation search, and runner.

7. **[MED] Capability tokens do not bind the operation ID or executable parameters** — [odooctl/api/routes_operations.py:162](/home/dev/odooctl/odooctl/api/routes_operations.py:162), [odooctl/runner/worker.py:222](/home/dev/odooctl/odooctl/runner/worker.py:222), [odooctl/runner/worker.py:336](/home/dev/odooctl/odooctl/runner/worker.py:336)  
   The signature covers only action/environment/project plus identity and roles. The runner executes `entry.params_redacted` and trusts `entry.op_id` and `entry.actor`, none of which are token-bound. Before nonce consumption, someone able to alter a queued file can reuse its valid token while changing migration options, clone source parameters, operation association, or audit attribution within the same scope.  
   **Fix:** include `op_id`, actor, and a canonical SHA-256 digest of the executable parameter object in reserved signed claims, then compare all three before consuming the nonce or changing operation status.
tokens used
78,527
The prior shell-injection, protected-environment, password-on-argv, nonce-bounding, project-scoping, and key-length remediations generally hold. I found these remaining issues:

1. **[HIGH] Docker filestore restore extracts an unvalidated archive directly into the live shared filestore root** — [odooctl/adapters/filestore.py:94](/home/dev/odooctl/odooctl/adapters/filestore.py:94)  
   `restore_archive()` deletes the target, then runs `tar -xf - -C /.../filestore` without validating members or requiring them to live beneath the expected database directory. A backup containing `another_db/...`, absolute paths, traversal components, hard links, or symlinks can overwrite sibling filestores or other container files, depending on tar behavior. Manifest checksums establish consistency, not authenticity—a malicious/imported backup can supply matching checksums.  
   **Fix:** inspect every archive member before extraction; reject absolute paths, `..`, links/devices, and anything outside exactly `<target-name>/`. Extract into a private staging directory/volume path, verify the resulting tree, then rename it into place.

2. **[HIGH] Restore/clone replaces the live filestore before DB preparation and promotion are known to succeed** — [odooctl/services/restore.py:142](/home/dev/odooctl/odooctl/services/restore.py:142), [odooctl/services/restore.py:179](/home/dev/odooctl/odooctl/services/restore.py:179), [odooctl/services/clone.py:83](/home/dev/odooctl/odooctl/services/clone.py:83)  
   Both restore paths replace the target filestore before sanitization and DB swap; clone does likewise. If sanitization or `swap_temp_database()` fails, the old live DB remains—or is dropped midway—while its filestore has already been destroyed and replaced. The advertised verify-before-destroy guarantee therefore covers only the dump restoration, not the complete Odoo state.  
   **Fix:** stage the filestore alongside the temporary DB, complete sanitization, then promote both with rollback bookkeeping. Preserve the previous filestore until DB promotion succeeds and restore it if any later step fails.

3. **[HIGH] Database “swap” destroys the live DB before the replacement rename succeeds** — [odooctl/odoo/db_swap.py:61](/home/dev/odooctl/odooctl/odoo/db_swap.py:61)  
   `swap_temp_database()` terminates connections, drops the target, and only then renames the temporary DB. A rename failure—permissions, conflicting database, connection loss, or malformed/colliding temp name—leaves the live database absent. This is not atomic despite service comments calling it so.  
   **Fix:** rename the live DB to a unique rollback name first, rename the prepared DB into place, and only drop the rollback DB after successful promotion and verification. On failure, rename the old DB back. Serialize the complete sequence with an appropriate lock.

4. **[MED] `CommandError` still retains secrets in its public `result.args` object** — [odooctl/utils/shell.py:20](/home/dev/odooctl/odooctl/utils/shell.py:20)  
   The exception string is redacted, but `self.result` is the original object, including raw argv. The test explicitly preserves this behavior. Exception serializers, debug handlers, telemetry, or code logging `exc.result` can therefore expose a password or token supplied by a future/third-party caller. Additionally, `CommandError` redacts its composed message using `os.environ`, not the merged per-call environment.  
   **Fix:** store a fully redacted public `CommandResult` on the exception; keep raw results private only if indispensable. Pass the merged environment/redaction values into exception construction, and prohibit secrets in argv at adapter boundaries.

5. **[MED] Audit-chain keying remains optional, so the claimed remediation is bypassable by default** — [odooctl/operations/audit.py:25](/home/dev/odooctl/odooctl/operations/audit.py:25), [odooctl/operations/audit.py:42](/home/dev/odooctl/odooctl/operations/audit.py:42)  
   Without `ODOOCTL_AUDIT_KEY`, both chain links and the high-water mark use attacker-recomputable SHA-256. Anyone able to alter state files can edit entries and regenerate both `audit.jsonl` and `audit.hwm`, after which `verify()` succeeds. The runner only warns and continues unkeyed.  
   **Fix:** require a strong, separately managed audit key at runner/API startup, fail closed when absent, and avoid storing it with the audit files. Provide an explicit migration mode for legacy unkeyed chains.

6. **[MED] Registry config-path containment is not enforced by API or runner loaders** — [odooctl/api/routes_operations.py:75](/home/dev/odooctl/odooctl/api/routes_operations.py:75), [odooctl/api/routes_operations.py:88](/home/dev/odooctl/odooctl/api/routes_operations.py:88), [odooctl/api/routes_projects.py:20](/home/dev/odooctl/odooctl/api/routes_projects.py:20), [odooctl/runner/worker.py:190](/home/dev/odooctl/odooctl/runner/worker.py:190)  
   CLI project resolution uses `_contained_config_path()`, but these paths call `ProjectContext.from_config_path(proj.config, root=proj.path)` directly. A hand-edited registry entry with `config="../../attacker/odooctl.yml"` is resolved and loaded outside the registered root. The privileged runner can subsequently execute operations using that external configuration.  
   **Fix:** centralize registry-to-context resolution in one function that always validates both the project root and resolved config path; use it in CLI, API, operation search, and runner.

7. **[MED] Capability tokens do not bind the operation ID or executable parameters** — [odooctl/api/routes_operations.py:162](/home/dev/odooctl/odooctl/api/routes_operations.py:162), [odooctl/runner/worker.py:222](/home/dev/odooctl/odooctl/runner/worker.py:222), [odooctl/runner/worker.py:336](/home/dev/odooctl/odooctl/runner/worker.py:336)  
   The signature covers only action/environment/project plus identity and roles. The runner executes `entry.params_redacted` and trusts `entry.op_id` and `entry.actor`, none of which are token-bound. Before nonce consumption, someone able to alter a queued file can reuse its valid token while changing migration options, clone source parameters, operation association, or audit attribution within the same scope.  
   **Fix:** include `op_id`, actor, and a canonical SHA-256 digest of the executable parameter object in reserved signed claims, then compare all three before consuming the nonce or changing operation status.
