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


class TemplateRecord(BaseModel):
    """A bank template stored in the database."""

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


class TemplateSourceRecord(BaseModel):
    """A registered marketplace template source."""

    name: str
    url: str
    scope: str = "server"
    owner: str | None = None
    auth_token: str | None = None
    created_at: str | None = None
