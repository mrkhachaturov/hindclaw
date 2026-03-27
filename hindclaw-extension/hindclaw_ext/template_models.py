"""Pydantic models for bank templates."""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class TemplateScope(StrEnum):
    """Template visibility scope."""

    SERVER = "server"
    PERSONAL = "personal"


class DirectiveSeed(BaseModel):
    """A directive to create when bootstrapping a bank from a template."""

    name: str
    content: str
    priority: int = 0
    is_active: bool = True


class EntityLabelValue(BaseModel):
    """A valid value for a value or multi-values entity label."""

    value: str
    description: str = ""


class EntityLabel(BaseModel):
    """An entity label definition for structured classification.

    Hindsight supports three label types:
    - "value": single enum value from the values list
    - "multi-values": multiple enum values from the values list
    - "text": free-form text (no values list needed)

    The ``tag`` field controls whether facts with this label also get tagged
    (enabling tag-based filtering in recall/reflect).
    """

    key: str
    description: str = ""
    type: str = "value"
    optional: bool = True
    tag: bool = False
    values: list[EntityLabelValue] = Field(default_factory=list)

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        valid = ("value", "multi-values", "text")
        if v not in valid:
            raise ValueError(f"type must be one of {valid}")
        return v

    @model_validator(mode="after")
    def _validate_values_for_type(self) -> "EntityLabel":
        if self.type in ("value", "multi-values") and not self.values:
            raise ValueError(f"values required when type is '{self.type}'")
        return self


class MentalModelSeed(BaseModel):
    """A mental model to create when bootstrapping a bank from a template."""

    name: str
    source_query: str
