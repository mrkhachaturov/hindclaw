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


_VALID_EXTRACTION_MODES = ("concise", "verbose", "custom", "verbatim", "chunks")


class MarketplaceTemplate(BaseModel):
    """A template definition from a marketplace JSON file.

    Represents the full template as published in a marketplace repository.
    Uses strict validation (extra="forbid") to reject unknown fields —
    if a marketplace publishes fields this version doesn't understand,
    install fails closed rather than silently ignoring data.
    """

    model_config = {"extra": "forbid"}

    schema_version: int = Field(ge=1)
    min_hindclaw_version: str
    min_hindsight_version: str | None = None
    name: str
    version: str
    description: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)

    retain_mission: str
    reflect_mission: str
    observations_mission: str | None = None

    retain_extraction_mode: str = "concise"
    retain_custom_instructions: str | None = None
    retain_chunk_size: int | None = Field(default=None, gt=0)
    retain_default_strategy: str | None = None
    retain_strategies: dict = Field(default_factory=dict)

    entity_labels: list[EntityLabel] = Field(default_factory=list)
    entities_allow_free_form: bool = True

    enable_observations: bool = True
    consolidation_llm_batch_size: int | None = Field(default=None, gt=0)
    consolidation_source_facts_max_tokens: int | None = None
    consolidation_source_facts_max_tokens_per_observation: int | None = None

    disposition_skepticism: int = Field(default=3, ge=1, le=5)
    disposition_literalism: int = Field(default=3, ge=1, le=5)
    disposition_empathy: int = Field(default=3, ge=1, le=5)

    directive_seeds: list[DirectiveSeed] = Field(default_factory=list)
    mental_model_seeds: list[MentalModelSeed] = Field(default_factory=list)

    @field_validator("retain_extraction_mode")
    @classmethod
    def _validate_extraction_mode(cls, v: str) -> str:
        if v not in _VALID_EXTRACTION_MODES:
            raise ValueError(f"retain_extraction_mode must be one of {_VALID_EXTRACTION_MODES}")
        return v

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "MarketplaceTemplate":
        if self.retain_extraction_mode == "custom" and not self.retain_custom_instructions:
            raise ValueError(
                "retain_custom_instructions required when retain_extraction_mode is 'custom'"
            )
        if self.retain_extraction_mode != "custom" and self.retain_custom_instructions is not None:
            raise ValueError(
                "retain_custom_instructions only valid when retain_extraction_mode is 'custom'"
            )
        return self
