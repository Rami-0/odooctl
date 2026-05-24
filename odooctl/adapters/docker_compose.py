from __future__ import annotations
from odooctl.utils.shell import run

class DockerComposeAdapter:
    def __init__(self, compose_file: str = "docker-compose.yml", project_dir: str | None = None):
        self.compose_file = compose_file
        self.project_dir = project_dir

    def _cmd(self, *args: str) -> list[str]:
        return ["docker", "compose", "-f", self.compose_file, *args]

    def pull(self, service: str | None = None) -> None:
        run(self._cmd("pull", *([service] if service else [])), cwd=self.project_dir, stream=True)

    def build(self, service: str | None = None) -> None:
        run(self._cmd("build", *([service] if service else [])), cwd=self.project_dir, stream=True)

    def up(self, service: str | None = None) -> None:
        run(self._cmd("up", "-d", *([service] if service else [])), cwd=self.project_dir, stream=True)

    def restart(self, service: str) -> None:
        run(self._cmd("restart", service), cwd=self.project_dir, stream=True)

    def logs(self, service: str | None = None) -> None:
        run(self._cmd("logs", "-f", *([service] if service else [])), cwd=self.project_dir, stream=True)

    def ps(self) -> str:
        return run(self._cmd("ps"), cwd=self.project_dir, check=False).stdout

    def exec(self, service: str, args: list[str], *, stream: bool = True) -> None:
        run(self._cmd("exec", "-T", service, *args), cwd=self.project_dir, stream=stream)
