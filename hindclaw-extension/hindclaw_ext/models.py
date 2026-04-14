"""Pydantic models for hindclaw access control."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from hindclaw_ext.template_models import TemplateScope


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


@dataclass
class TemplateRecord:
    """An installed template, stored in the bank_templates table.

    The manifest is an opaque BankTemplateManifest JSON dict — HindClaw
    does not introspect it. Validation happens upstream via
    BankTemplateManifest.model_validate() + validate_bank_template().

    Identity invariant: a TemplateRecord is uniquely keyed by
    (id, scope, owner). Source attribution (source_name, source_scope,
    source_template_id, source_url, source_revision) is informational
    only — re-installing a template with the same id replaces the
    existing row regardless of which source it came from. To install
    two templates with the same id from different sources, rename one
    before installing via the install request's `alias_id`.
    """

    id: str
    scope: TemplateScope
    owner: str | None
    source_name: str | None
    source_scope: TemplateScope | None
    source_template_id: str | None
    source_url: str | None
    source_revision: str | None
    name: str
    description: str | None
    category: str | None
    integrations: list[str]
    tags: list[str]
    manifest: dict
    installed_at: datetime
    updated_at: datetime


class TemplateSourceRecord(BaseModel):
    """A registered marketplace template source."""

    name: str
    url: str
    scope: str = "server"
    owner: str | None = None
    auth_token: str | None = None
    description: str | None = None
    created_at: str | None = None  # Always set from DB; None only in test construction
    updated_at: str | None = None
