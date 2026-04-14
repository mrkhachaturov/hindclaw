"""Pydantic request and response models for HindclawHttp API endpoints."""

from datetime import datetime

from hindsight_api.api.http import BankTemplateImportResponse, BankTemplateManifest  # type: ignore[attr-defined]
from pydantic import BaseModel, ConfigDict, Field

from hindclaw_ext.template_models import TemplateScope

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


class CreateSelfServiceAccountRequest(BaseModel):
    """Self-service SA creation — owner is always the authenticated caller."""

    model_config = {"extra": "forbid"}

    id: str
    display_name: str
    scoping_policy_id: str | None = None


class UpdateSelfServiceAccountRequest(BaseModel):
    """Self-service SA update — only display_name is mutable.

    Scoping policy and activation state are admin-only operations.
    An SA authenticates as its owner, so without this restriction an SA
    could remove its own scoping policy and escalate to the parent user's
    full permissions.
    """

    model_config = {"extra": "forbid"}

    display_name: str


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


class CreateTemplateRequest(BaseModel):
    """Request to create a personal template by inlining an upstream manifest."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    description: str | None = None
    category: str | None = None
    integrations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    manifest: BankTemplateManifest


class PatchTemplateRequest(BaseModel):
    """Partial update for hand-edited templates. Every field is optional."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    category: str | None = None
    integrations: list[str] | None = None
    tags: list[str] | None = None
    manifest: BankTemplateManifest | None = None


class InstallTemplateRequest(BaseModel):
    """Request to install a template from a marketplace source.

    The ``{id}`` in the URL path is the template id WITHIN the source.
    The installed-template id is ``alias_id`` if provided, else the source
    template id. This lets a user install the same source template under a
    different installed name (Section 4.3 identity invariant: at most one
    row per (id, scope, owner)).
    """

    model_config = ConfigDict(extra="forbid")

    source_name: str = Field(min_length=1)
    source_scope: TemplateScope = TemplateScope.SERVER
    alias_id: str | None = None


class UpdateTemplateRequest(BaseModel):
    """Query knobs for /me/templates/{id}/update — body is empty by default."""

    model_config = ConfigDict(extra="forbid")

    force: bool = False


class CheckUpdateResponse(BaseModel):
    has_update: bool
    current_revision: str | None
    latest_revision: str | None
    source_name: str | None = None
    source_scope: TemplateScope | None = None


class TemplateResponse(BaseModel):
    """Installed template, surfaced over the API."""

    id: str
    name: str
    description: str | None
    category: str | None
    integrations: list[str]
    tags: list[str]
    scope: TemplateScope
    owner: str | None
    source_name: str | None
    source_scope: TemplateScope | None
    source_revision: str | None
    installed_at: datetime
    updated_at: datetime
    manifest: dict


class UpdateTemplateResponse(BaseModel):
    updated: bool
    previous_revision: str | None
    new_revision: str | None
    template: TemplateResponse


class ListTemplatesResponse(BaseModel):
    templates: list[TemplateResponse]


# --- Bank Creation from Template ---


class CreateBankFromTemplateRequest(BaseModel):
    """Body for POST /ext/hindclaw/banks."""

    model_config = ConfigDict(extra="forbid")

    bank_id: str = Field(min_length=1, max_length=128)
    template: str = Field(min_length=1, max_length=256)
    name: str | None = None


class BankCreationResponse(BaseModel):
    """Response from POST /ext/hindclaw/banks — bank creation from template.

    Wraps upstream's ``BankTemplateImportResponse`` so clients see the
    same counts/errors upstream reports directly.
    """

    bank_id: str
    template: str
    bank_created: bool
    import_result: BankTemplateImportResponse


# --- Template Source Models ---


class CreateSourceRequest(BaseModel):
    """Request to register a marketplace source."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, description="Marketplace repository URL")
    alias: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Override auto-derived source name",
    )
    auth_token: str | None = Field(
        default=None,
        description="Auth token for private repositories",
    )
    description: str | None = None


class SourceResponse(BaseModel):
    """Response for a registered marketplace source."""

    name: str
    url: str
    scope: TemplateScope
    owner: str | None = None
    has_auth: bool
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MeProfileResponse(BaseModel):
    """Response for GET /me — caller's own profile."""

    id: str
    display_name: str
    email: str | None
    is_active: bool
    channels: list[ChannelResponse]
