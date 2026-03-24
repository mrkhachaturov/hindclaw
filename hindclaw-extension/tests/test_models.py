"""Tests for hindclaw_ext.models."""
import pytest
from hindclaw_ext.models import ResolvedPermissions


def test_resolved_permissions_defaults():
    """Default ResolvedPermissions denies everything."""
    perms = ResolvedPermissions(user_id="test", is_anonymous=False)
    assert perms.recall is False
    assert perms.retain is False
    assert perms.retain_roles == ["user", "assistant"]
    assert perms.retain_tags == []
    assert perms.retain_every_n_turns == 1
    assert perms.retain_strategy is None
    assert perms.recall_budget == "mid"
    assert perms.recall_max_tokens == 1024
    assert perms.recall_tag_groups is None
    assert perms.llm_model is None
    assert perms.llm_provider is None
    assert perms.exclude_providers == []


def test_resolved_permissions_with_values():
    """ResolvedPermissions accepts all fields."""
    perms = ResolvedPermissions(
        user_id="alice",
        is_anonymous=False,
        recall=True,
        retain=True,
        retain_tags=["role:team-lead", "user:alice"],
        recall_budget="high",
        recall_tag_groups=[{"not": {"tags": ["restricted"], "match": "any_strict"}}],
    )
    assert perms.recall is True
    assert perms.retain_tags == ["role:team-lead", "user:alice"]
    assert perms.recall_budget == "high"


def test_resolved_permissions_anonymous():
    """Anonymous users have is_anonymous=True."""
    perms = ResolvedPermissions(user_id="_anonymous", is_anonymous=True)
    assert perms.is_anonymous is True
    assert perms.recall is False


def test_policy_record():
    """PolicyRecord from DB row."""
    from hindclaw_ext.models import PolicyRecord

    r = PolicyRecord(id="fleet-access", display_name="Fleet Access", is_builtin=False, document_json={"version": "2026-03-24", "statements": []})
    assert r.id == "fleet-access"
    assert r.is_builtin is False


def test_policy_attachment_record():
    """PolicyAttachmentRecord from DB row."""
    from hindclaw_ext.models import PolicyAttachmentRecord

    r = PolicyAttachmentRecord(policy_id="fleet-access", principal_type="group", principal_id="default", priority=10)
    assert r.priority == 10


def test_service_account_record():
    """ServiceAccountRecord from DB row."""
    from hindclaw_ext.models import ServiceAccountRecord

    r = ServiceAccountRecord(id="ceo-claude", owner_user_id="ceo@astrateam.net", display_name="CEO Claude", is_active=True, scoping_policy_id=None)
    assert r.scoping_policy_id is None


def test_service_account_key_record():
    """ServiceAccountKeyRecord from DB row."""
    from hindclaw_ext.models import ServiceAccountKeyRecord

    r = ServiceAccountKeyRecord(id="key-1", service_account_id="ceo-claude", api_key="hc_sa_xxx", description="Test key")
    assert r.api_key.startswith("hc_sa_")


def test_bank_policy_record():
    """BankPolicyRecord from DB row."""
    from hindclaw_ext.models import BankPolicyRecord

    r = BankPolicyRecord(bank_id="yoda", document_json={"version": "2026-03-24", "default_strategy": "yoda-default"})
    assert r.bank_id == "yoda"


def test_user_record_is_active():
    """UserRecord has is_active field defaulting to True."""
    from hindclaw_ext.models import UserRecord

    r = UserRecord(id="alice", display_name="Alice")
    assert r.is_active is True
