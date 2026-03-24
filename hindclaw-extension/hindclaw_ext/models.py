"""Pydantic models for hindclaw access control."""

from pydantic import BaseModel


class UserRecord(BaseModel):
    """User from hindclaw_users table."""

    id: str
    display_name: str
    email: str | None = None
    is_active: bool = True


class ApiKeyRecord(BaseModel):
    """API key from hindclaw_api_keys table."""

    id: str
    api_key: str
    user_id: str
    description: str | None = None


class GroupRecord(BaseModel):
    """Group from hindclaw_groups table (identity-only)."""

    id: str
    display_name: str


class PolicyRecord(BaseModel):
    """Access policy from hindclaw_policies table."""

    id: str
    display_name: str
    document_json: dict
    is_builtin: bool = False


class PolicyAttachmentRecord(BaseModel):
    """Policy attachment from hindclaw_policy_attachments table."""

    policy_id: str
    principal_type: str  # 'user' or 'group'
    principal_id: str
    priority: int = 0


class ServiceAccountRecord(BaseModel):
    """Service account from hindclaw_service_accounts table."""

    id: str
    owner_user_id: str
    scoping_policy_id: str | None = None
    display_name: str
    is_active: bool = True


class ServiceAccountKeyRecord(BaseModel):
    """SA API key from hindclaw_service_account_keys table."""

    id: str
    service_account_id: str
    api_key: str
    description: str | None = None


class BankPolicyRecord(BaseModel):
    """Bank policy from hindclaw_bank_policies table."""

    bank_id: str
    document_json: dict


class AttachedPolicyRecord(BaseModel):
    """Policy with attachment metadata, from joined query."""

    id: str
    display_name: str
    document_json: dict
    is_builtin: bool = False
    principal_type: str
    principal_id: str
    priority: int = 0
