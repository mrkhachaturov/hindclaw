"""Pydantic request and response models for HindclawHttp API endpoints."""

from pydantic import BaseModel, Field, field_validator, model_validator

from hindclaw_ext.template_models import DirectiveSeed, EntityLabel, MentalModelSeed


# --- Users ---

class CreateUserRequest(BaseModel):
    id: str
    display_name: str
    email: str | None = None
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None
    is_active: bool | None = None


# --- Channels ---

class AddChannelRequest(BaseModel):
    provider: str
    sender_id: str


# --- Groups (identity-only) ---

class CreateGroupRequest(BaseModel):
    id: str
    display_name: str


class UpdateGroupRequest(BaseModel):
    display_name: str | None = None


# --- Group Members ---

class AddMemberRequest(BaseModel):
    user_id: str


# --- API Keys ---

class CreateApiKeyRequest(BaseModel):
    description: str | None = None


# ============================================================================
# Response models — used as response_model= on route decorators.
# FastAPI uses these to generate typed OpenAPI schemas for client generation.
# ============================================================================


class UserResponse(BaseModel):
    """User resource returned by GET/POST/PUT endpoints."""

    id: str
    display_name: str
    email: str | None = None
    is_active: bool = True


class ChannelResponse(BaseModel):
    """Channel mapping returned by GET/POST endpoints."""

    provider: str
    sender_id: str


class GroupSummaryResponse(BaseModel):
    """Group resource (identity-only)."""

    id: str
    display_name: str


class GroupMemberResponse(BaseModel):
    """Group membership entry."""

    user_id: str


class ApiKeyResponse(BaseModel):
    """API key in list view — key is masked after creation."""

    id: str
    api_key_prefix: str
    description: str | None = None


class ApiKeyCreateResponse(BaseModel):
    """API key at creation time — full key shown once."""

    id: str
    api_key: str
    description: str | None = None


class GroupMembershipConfirmation(BaseModel):
    """Confirmation returned by POST /groups/:id/members."""

    group_id: str
    user_id: str


# --- Policies ---


class CreatePolicyRequest(BaseModel):
    """Request to create an access policy."""

    id: str
    display_name: str
    document: dict


class UpdatePolicyRequest(BaseModel):
    """Request to update an access policy."""

    display_name: str | None = None
    document: dict | None = None


class PolicyResponse(BaseModel):
    """Access policy resource."""

    id: str
    display_name: str
    document: dict
    is_builtin: bool


# --- Policy Attachments ---


class CreatePolicyAttachmentRequest(BaseModel):
    """Request to attach a policy to a principal."""

    policy_id: str
    principal_type: str
    principal_id: str
    priority: int = 0


class PolicyAttachmentResponse(BaseModel):
    """Policy attachment resource."""

    policy_id: str
    principal_type: str
    principal_id: str
    priority: int


# --- Service Accounts ---


class CreateServiceAccountRequest(BaseModel):
    """Request to create a service account."""

    id: str
    owner_user_id: str
    display_name: str
    scoping_policy_id: str | None = None


class UpdateServiceAccountRequest(BaseModel):
    """Request to update a service account."""

    display_name: str | None = None
    scoping_policy_id: str | None = None
    is_active: bool | None = None


class ServiceAccountResponse(BaseModel):
    """Service account resource."""

    id: str
    owner_user_id: str
    display_name: str
    is_active: bool
    scoping_policy_id: str | None


# --- SA Keys ---


class CreateSAKeyRequest(BaseModel):
    """Request to create an SA API key."""

    description: str | None = None


class SAKeyResponse(BaseModel):
    """SA API key in list view — key is masked."""

    id: str
    api_key_prefix: str
    description: str | None


class SAKeyCreateResponse(BaseModel):
    """SA API key at creation time — full key shown once."""

    id: str
    api_key: str
    description: str | None


# --- Bank Policies ---


class UpsertBankPolicyRequest(BaseModel):
    """Request to create/update a bank policy."""

    document: dict


class BankPolicyResponse(BaseModel):
    """Bank policy resource."""

    bank_id: str
    document: dict


# --- Debug ---


class DebugResolveResponse(BaseModel):
    """Debug resolve response — effective access + bank policy."""

    tenant_id: str
    principal_type: str
    access: dict
    bank_policy: dict | None


# --- Templates ---


_VALID_SCOPES = ("server", "personal")
_VALID_EXTRACTION_MODES = ("concise", "verbose", "custom", "verbatim", "chunks")


class CreateTemplateRequest(BaseModel):
    """Request to create a custom template."""

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1, max_length=128)
    scope: str
    description: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    min_hindclaw_version: str
    min_hindsight_version: str | None = None
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

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, v: str) -> str:
        if v not in _VALID_SCOPES:
            raise ValueError(f"scope must be one of {_VALID_SCOPES}")
        return v

    @field_validator("retain_extraction_mode")
    @classmethod
    def _validate_extraction_mode(cls, v: str) -> str:
        if v not in _VALID_EXTRACTION_MODES:
            raise ValueError(f"retain_extraction_mode must be one of {_VALID_EXTRACTION_MODES}")
        return v

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "CreateTemplateRequest":
        if self.retain_extraction_mode == "custom" and not self.retain_custom_instructions:
            raise ValueError("retain_custom_instructions required when retain_extraction_mode is 'custom'")
        if self.retain_extraction_mode != "custom" and self.retain_custom_instructions is not None:
            raise ValueError("retain_custom_instructions only valid when retain_extraction_mode is 'custom'")
        return self


class UpdateTemplateRequest(BaseModel):
    """Request to update an existing template. All fields optional.

    Note: cross-field validation (e.g. custom mode requires custom instructions)
    cannot be fully checked here because this is a partial update. The endpoint
    must merge with the existing record and validate the final state.
    """

    model_config = {"extra": "forbid"}

    description: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    min_hindclaw_version: str | None = None
    min_hindsight_version: str | None = None
    retain_mission: str | None = None
    reflect_mission: str | None = None
    observations_mission: str | None = None
    retain_extraction_mode: str | None = None
    retain_custom_instructions: str | None = None
    retain_chunk_size: int | None = Field(default=None, gt=0)
    retain_default_strategy: str | None = None
    retain_strategies: dict | None = None
    entity_labels: list[EntityLabel] | None = None
    entities_allow_free_form: bool | None = None
    enable_observations: bool | None = None
    consolidation_llm_batch_size: int | None = Field(default=None, gt=0)
    consolidation_source_facts_max_tokens: int | None = None
    consolidation_source_facts_max_tokens_per_observation: int | None = None
    disposition_skepticism: int | None = Field(default=None, ge=1, le=5)
    disposition_literalism: int | None = Field(default=None, ge=1, le=5)
    disposition_empathy: int | None = Field(default=None, ge=1, le=5)
    directive_seeds: list[DirectiveSeed] | None = None
    mental_model_seeds: list[MentalModelSeed] | None = None

    @field_validator("retain_extraction_mode")
    @classmethod
    def _validate_extraction_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_EXTRACTION_MODES:
            raise ValueError(f"retain_extraction_mode must be one of {_VALID_EXTRACTION_MODES}")
        return v


class TemplateSummaryResponse(BaseModel):
    """Summary of a template for list endpoints."""

    id: str
    scope: str
    source_name: str | None
    version: str | None
    description: str
    author: str
    tags: list[str]
    retain_extraction_mode: str
    disposition_skepticism: int
    disposition_literalism: int
    disposition_empathy: int
    created_at: str
    updated_at: str


class TemplateResponse(BaseModel):
    """Full template details."""

    id: str
    scope: str
    owner: str | None
    source_name: str | None
    schema_version: int
    min_hindclaw_version: str
    min_hindsight_version: str | None
    version: str | None
    source_url: str | None
    source_revision: str | None
    description: str
    author: str
    tags: list[str]
    retain_mission: str
    reflect_mission: str
    observations_mission: str | None
    retain_extraction_mode: str
    retain_custom_instructions: str | None
    retain_chunk_size: int | None
    retain_default_strategy: str | None
    retain_strategies: dict
    entity_labels: list[dict]
    entities_allow_free_form: bool
    enable_observations: bool
    consolidation_llm_batch_size: int | None
    consolidation_source_facts_max_tokens: int | None
    consolidation_source_facts_max_tokens_per_observation: int | None
    disposition_skepticism: int
    disposition_literalism: int
    disposition_empathy: int
    directive_seeds: list[dict]
    mental_model_seeds: list[dict]
    created_at: str
    updated_at: str
