"""Pydantic models for hindclaw access control."""

from pydantic import BaseModel, Field


class MergedPermissions(BaseModel):
    """Internal accumulator for the 4-step permission merge.

    All fields are optional — None means "not yet set by any source."
    Used by resolver.py as a typed alternative to raw dict (per upstream
    convention: never use raw dict for structured data).

    See spec Section 7 for merge rules.
    """

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


class ResolvedPermissions(BaseModel):
    """Output of the 4-step permission resolution algorithm.

    Produced by resolver.resolve() after merging MergedPermissions
    with defaults and adding user-specific fields (user_id, is_anonymous,
    retain_strategy).

    See spec Section 7 for the resolution algorithm and merge rules.
    """

    user_id: str
    is_anonymous: bool

    # Access control
    recall: bool = False
    retain: bool = False

    # Retain configuration
    retain_roles: list[str] = Field(default_factory=lambda: ["user", "assistant"])
    retain_tags: list[str] = Field(default_factory=list)
    retain_every_n_turns: int = 1
    retain_strategy: str | None = None

    # Recall configuration
    recall_budget: str = "mid"
    recall_max_tokens: int = 1024
    recall_tag_groups: list[dict] | None = None

    # LLM overrides (client-enforced)
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] = Field(default_factory=list)


class UserRecord(BaseModel):
    """User from hindclaw_users table."""

    id: str
    display_name: str
    email: str | None = None


class ApiKeyRecord(BaseModel):
    """API key from hindclaw_api_keys table."""

    id: str
    api_key: str
    user_id: str
    description: str | None = None


class GroupRecord(BaseModel):
    """Group from hindclaw_groups table. Nullable fields = not set (inherit)."""

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


class BankPermissionRecord(BaseModel):
    """Bank-level permission override from hindclaw_bank_permissions table."""

    bank_id: str
    scope_type: str  # 'group' or 'user'
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
