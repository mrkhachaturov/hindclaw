"""Pydantic request and response models for HindclawHttp API endpoints."""

from pydantic import BaseModel


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
