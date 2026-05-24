from __future__ import annotations
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.utils.shell import join_csv, run

def update_modules_local(db_name: str, modules: list[str]) -> None:
    if not modules:
        return
    run(["odoo", "-d", db_name, "-u", join_csv(modules), "--stop-after-init"], stream=True)

def update_modules_compose(compose: DockerComposeAdapter, service: str, db_name: str, modules: list[str]) -> None:
    if not modules:
        return
    compose.exec(service, ["odoo", "-d", db_name, "-u", join_csv(modules), "--stop-after-init"], stream=True)
