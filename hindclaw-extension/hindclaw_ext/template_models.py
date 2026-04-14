"""Pydantic models for HindClaw bank templates.

HindClaw's template layer is a governance wrapper around upstream Hindsight's
BankTemplateManifest. Field-level validation, label groups, directive shapes,
mental model triggers — all live in upstream and are imported via their
Pydantic models. This file only defines HindClaw-specific types (scope) and
the thin CatalogEntry metadata that wraps an upstream manifest with
hub-style presentation fields.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from hindsight_api.api.http import BankTemplateManifest  # type: ignore[attr-defined]
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TemplateScope(StrEnum):
    """Template visibility scope."""

    SERVER = "server"
    PERSONAL = "personal"


class CatalogEntry(BaseModel):
    """One entry in a catalog (templates.json).

    An entry has presentation metadata plus EXACTLY ONE of:
    - inline ``manifest``: a full upstream BankTemplateManifest (matches
      upstream's hindsight-docs/src/data/templates.json shape)
    - external ``manifest_file``: a relative path to a separate file
      containing a pure BankTemplateManifest (HindClaw's preferred shape)

    A model_validator enforces the exclusive-or invariant at parse time.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None = None
    category: str | None = None
    integrations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    manifest: BankTemplateManifest | None = None
    manifest_file: str | None = None

    @model_validator(mode="after")
    def _exactly_one_body(self) -> Self:
        has_inline = self.manifest is not None
        has_ref = self.manifest_file is not None
        if has_inline and has_ref:
            raise ValueError(f"Catalog entry '{self.id}' has both 'manifest' and 'manifest_file'; specify exactly one")
        if not has_inline and not has_ref:
            raise ValueError(
                f"Catalog entry '{self.id}' has neither 'manifest' nor 'manifest_file'; specify exactly one"
            )
        return self


class Catalog(BaseModel):
    """The full catalog file (templates.json).

    All metadata fields except ``templates`` are optional so that upstream
    Hindsight's hindsight-docs/src/data/templates.json — which only carries
    a top-level ``templates`` array — parses with zero adapter code.
    """

    model_config = ConfigDict(extra="forbid")

    catalog_version: str = "1"
    name: str | None = None
    description: str | None = None
    templates: list[CatalogEntry]


__all__ = ["TemplateScope", "CatalogEntry", "Catalog"]
