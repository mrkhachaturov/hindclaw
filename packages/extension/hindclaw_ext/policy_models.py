"""Pydantic models for policy documents (access policies and bank policies).

Access policy documents carry allow/deny statements with actions, banks, and
behavioral parameters. Bank policy documents carry strategy defaults, context
overrides, and public access rules.

See spec Sections 5 and 6.
"""

from pydantic import BaseModel, field_validator

_SUPPORTED_VERSIONS = {"2026-03-24"}
_VALID_EFFECTS = {"allow", "deny"}
_VALID_BUDGETS = {"low", "mid", "high"}
_VALID_SCOPES = {"provider", "channel", "topic"}


class PolicyStatement(BaseModel):
    """Single statement in an access policy document.

    Allow statements may carry behavioral parameters. Deny statements only
    need effect, actions, and banks.
    """

    effect: str
    actions: list[str]
    banks: list[str]

    # Behavioral parameters (optional, only meaningful on allow statements)
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    retain_strategy: str | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None

    @field_validator("effect")
    @classmethod
    def validate_effect(cls, v: str) -> str:
        """Effect must be 'allow' or 'deny'."""
        if v not in _VALID_EFFECTS:
            raise ValueError(f"effect must be one of {_VALID_EFFECTS}, got {v!r}")
        return v

    @field_validator("recall_budget")
    @classmethod
    def validate_budget(cls, v: str | None) -> str | None:
        """Budget must be low/mid/high if set."""
        if v is not None and v not in _VALID_BUDGETS:
            raise ValueError(f"recall_budget must be one of {_VALID_BUDGETS}, got {v!r}")
        return v


class PolicyDocument(BaseModel):
    """Access policy document — a list of allow/deny statements.

    Attached to users or groups via hindclaw_policy_attachments.
    SAs reference a single scoping policy via scoping_policy_id.

    See spec Section 5.
    """

    version: str
    statements: list[PolicyStatement]

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Version must be a known schema version."""
        if v not in _SUPPORTED_VERSIONS:
            raise ValueError(f"unsupported policy version {v!r}, supported: {_SUPPORTED_VERSIONS}")
        return v


class PublicAccessOverride(BaseModel):
    """Single public access override scoped by context (provider/channel/topic)."""

    scope: str
    value: str
    actions: list[str]
    recall_budget: str | None = None
    recall_max_tokens: int | None = None

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        """Scope must be provider, channel, or topic."""
        if v not in _VALID_SCOPES:
            raise ValueError(f"scope must be one of {_VALID_SCOPES}, got {v!r}")
        return v

    @field_validator("recall_budget")
    @classmethod
    def validate_budget(cls, v: str | None) -> str | None:
        """Budget must be low/mid/high if set."""
        if v is not None and v not in _VALID_BUDGETS:
            raise ValueError(f"recall_budget must be one of {_VALID_BUDGETS}, got {v!r}")
        return v


class PublicAccessDefault(BaseModel):
    """Default public access when no override matches."""

    actions: list[str]
    recall_budget: str | None = None
    recall_max_tokens: int | None = None


class PublicAccess(BaseModel):
    """Public access configuration on a bank policy."""

    default: PublicAccessDefault | None = None
    overrides: list[PublicAccessOverride] = []


class StrategyOverride(BaseModel):
    """Context-scoped strategy override on a bank policy."""

    scope: str
    value: str
    strategy: str

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        """Scope must be provider, channel, or topic."""
        if v not in _VALID_SCOPES:
            raise ValueError(f"scope must be one of {_VALID_SCOPES}, got {v!r}")
        return v


class BankPolicyDocument(BaseModel):
    """Bank policy document — strategy defaults, context overrides, public access.

    Attached to banks via hindclaw_bank_policies.

    See spec Section 6.
    """

    version: str
    default_strategy: str | None = None
    strategy_overrides: list[StrategyOverride] = []
    public_access: PublicAccess | None = None

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Version must be a known schema version."""
        if v not in _SUPPORTED_VERSIONS:
            raise ValueError(f"unsupported bank policy version {v!r}, supported: {_SUPPORTED_VERSIONS}")
        return v
