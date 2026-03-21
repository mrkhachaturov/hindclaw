"""Pydantic request and response models for HindclawHttp API endpoints."""

from pydantic import BaseModel


# --- Users ---

class CreateUserRequest(BaseModel):
    id: str
    display_name: str
    email: str | None = None


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None


# --- Channels ---

class AddChannelRequest(BaseModel):
    provider: str
    sender_id: str


# --- Groups ---

class CreateGroupRequest(BaseModel):
    id: str
    display_name: str
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


class UpdateGroupRequest(BaseModel):
    display_name: str | None = None
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


# --- Group Members ---

class AddMemberRequest(BaseModel):
    user_id: str


# --- Bank Permissions ---

class BankPermissionRequest(BaseModel):
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


# --- Strategy Scopes ---

class StrategyRequest(BaseModel):
    strategy: str


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


class ChannelResponse(BaseModel):
    """Channel mapping returned by GET/POST endpoints."""

    provider: str
    sender_id: str


class GroupResponse(BaseModel):
    """Group resource with all permission fields.

    Returned by GET /groups/:id and POST /groups.
    Permission fields are nullable — None means "not set (inherit from global)."
    """

    id: str
    display_name: str
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


class GroupSummaryResponse(BaseModel):
    """Group summary returned by GET /groups (list view)."""

    id: str
    display_name: str


class GroupMemberResponse(BaseModel):
    """Group membership entry."""

    user_id: str


class BankPermissionResponse(BaseModel):
    """Bank-level permission entry with scope identifiers.

    Returned by GET /banks/:bank/permissions endpoints.
    """

    bank_id: str
    scope_type: str
    scope_id: str
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


class StrategyScopeResponse(BaseModel):
    """Strategy scope entry returned by GET /banks/:bank/strategies."""

    bank_id: str
    scope_type: str
    scope_value: str
    strategy: str


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


class UpsertConfirmation(BaseModel):
    """Confirmation returned by PUT (upsert) endpoints."""

    bank_id: str
    scope_type: str
    scope_id: str


class GroupMembershipConfirmation(BaseModel):
    """Confirmation returned by POST /groups/:id/members."""

    group_id: str
    user_id: str


class StrategyUpsertConfirmation(BaseModel):
    """Confirmation returned by PUT /banks/:bank/strategies/:type/:value."""

    bank_id: str
    scope_type: str
    scope_value: str
    strategy: str


class ResolvedPermissionsResponse(BaseModel):
    """Full resolved permissions returned by GET /debug/resolve.

    Mirrors hindclaw_ext.models.ResolvedPermissions but as an HTTP response model.
    """

    user_id: str
    is_anonymous: bool
    recall: bool
    retain: bool
    retain_roles: list[str]
    retain_tags: list[str]
    retain_every_n_turns: int
    retain_strategy: str | None
    recall_budget: str
    recall_max_tokens: int
    recall_tag_groups: list[dict] | None
    llm_model: str | None
    llm_provider: str | None
    exclude_providers: list[str]
