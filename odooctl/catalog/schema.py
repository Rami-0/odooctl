"""Catalog entry schemas: StackTemplate, AddonSource, AddonPack, CompanionService."""
from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator


class StackTemplate(BaseModel):
    kind: Literal["StackTemplate"] = "StackTemplate"
    id: str
    description: str = ""
    odoo_version: str
    odoo_image: str
    postgres_image: str
    http_port: int = 8069
    volumes: list[str] = Field(default_factory=list)
    compose_defaults: dict = Field(default_factory=dict)

    @field_validator("odoo_image", "postgres_image")
    @classmethod
    def no_floating_latest(cls, v: str) -> str:
        if v.endswith(":latest"):
            raise ValueError(
                f"Pin to a specific version tag instead of ':latest': {v!r}"
            )
        return v


class AddonSource(BaseModel):
    kind: Literal["AddonSource"] = "AddonSource"
    id: str
    description: str = ""
    repo_url: str
    ref: str
    subpath: str | None = None
    # Env-var name for repo auth token — never a literal credential value.
    auth_env: str | None = None

    @field_validator("auth_env")
    @classmethod
    def valid_env_var_name(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", v):
            raise ValueError(
                f"auth_env must be an env-var name (e.g. GITHUB_TOKEN), not a literal value or reference: {v!r}"
            )
        return v


class AddonPack(BaseModel):
    kind: Literal["AddonPack"] = "AddonPack"
    id: str
    description: str = ""
    sources: list[str] = Field(default_factory=list)


class CompanionService(BaseModel):
    kind: Literal["CompanionService"] = "CompanionService"
    id: str
    description: str = ""
    service_name: str
    image: str
    ports: list[str] = Field(default_factory=list)
    # Values are env-var references only (e.g. "${MY_VAR}"), never literal secrets.
    environment: dict[str, str] = Field(default_factory=dict)
    volumes: list[str] = Field(default_factory=list)

    @field_validator("image")
    @classmethod
    def no_floating_latest(cls, v: str) -> str:
        if v.endswith(":latest"):
            raise ValueError(
                f"Pin to a specific version tag instead of ':latest': {v!r}"
            )
        return v


CatalogEntry = Annotated[
    Union[StackTemplate, AddonSource, AddonPack, CompanionService],
    Field(discriminator="kind"),
]
