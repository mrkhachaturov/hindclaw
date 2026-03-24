"""Tests for hindclaw_ext.models."""


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
