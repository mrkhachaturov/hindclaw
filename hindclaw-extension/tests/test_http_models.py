"""Tests for response model imports and field shapes."""

from hindclaw_ext.http_models import (
    UserResponse,
    ChannelResponse,
    GroupSummaryResponse,
    GroupMemberResponse,
    GroupMembershipConfirmation,
    ApiKeyResponse,
    ApiKeyCreateResponse,
)


def test_user_response_fields():
    """UserResponse has exactly the public fields."""
    resp = UserResponse(id="alice", display_name="Alice", email="alice@example.com")
    assert resp.model_dump() == {"id": "alice", "display_name": "Alice", "email": "alice@example.com", "is_active": True}


def test_api_key_create_response_includes_full_key():
    """ApiKeyCreateResponse shows the full key (only at creation time)."""
    resp = ApiKeyCreateResponse(id="k1", api_key="hc_u_alice_xxx", description="test")
    assert resp.api_key == "hc_u_alice_xxx"


def test_api_key_response_masks_key():
    """ApiKeyResponse in list view shows masked key."""
    resp = ApiKeyResponse(id="k1", api_key_prefix="hc_u_alice_", description="test")
    assert "hc_u_alice_" in resp.api_key_prefix


def test_group_membership_confirmation():
    """GroupMembershipConfirmation returned by POST /groups/:id/members."""
    resp = GroupMembershipConfirmation(group_id="engineering", user_id="alice")
    assert resp.group_id == "engineering"
    assert resp.user_id == "alice"


def test_channel_response():
    """ChannelResponse has provider + sender_id."""
    resp = ChannelResponse(provider="telegram", sender_id="100001")
    assert resp.provider == "telegram"
    assert resp.sender_id == "100001"


def test_group_summary_response():
    """GroupSummaryResponse has only id + display_name."""
    resp = GroupSummaryResponse(id="engineering", display_name="Engineering")
    assert resp.model_dump() == {"id": "engineering", "display_name": "Engineering"}


def test_group_member_response():
    """GroupMemberResponse has user_id."""
    resp = GroupMemberResponse(user_id="alice")
    assert resp.user_id == "alice"


def test_create_policy_request():
    from hindclaw_ext.http_models import CreatePolicyRequest
    req = CreatePolicyRequest(id="fleet-access", display_name="Fleet Access", document={"version": "2026-03-24", "statements": []})
    assert req.id == "fleet-access"


def test_policy_response():
    from hindclaw_ext.http_models import PolicyResponse
    r = PolicyResponse(id="fleet-access", display_name="Fleet Access", document={"version": "2026-03-24", "statements": []}, is_builtin=False)
    assert r.is_builtin is False


def test_create_policy_attachment_request():
    from hindclaw_ext.http_models import CreatePolicyAttachmentRequest
    req = CreatePolicyAttachmentRequest(policy_id="fleet-access", principal_type="group", principal_id="default", priority=10)
    assert req.priority == 10


def test_policy_attachment_response():
    from hindclaw_ext.http_models import PolicyAttachmentResponse
    r = PolicyAttachmentResponse(policy_id="fleet-access", principal_type="group", principal_id="default", priority=10)
    assert r.principal_type == "group"


def test_create_service_account_request():
    from hindclaw_ext.http_models import CreateServiceAccountRequest
    req = CreateServiceAccountRequest(id="ceo-claude", owner_user_id="ceo@astrateam.net", display_name="CEO Claude", scoping_policy_id="claude-readonly")
    assert req.scoping_policy_id == "claude-readonly"


def test_service_account_response():
    from hindclaw_ext.http_models import ServiceAccountResponse
    r = ServiceAccountResponse(id="ceo-claude", owner_user_id="ceo@astrateam.net", display_name="CEO Claude", is_active=True, scoping_policy_id=None)
    assert r.is_active is True


def test_sa_key_create_response():
    from hindclaw_ext.http_models import SAKeyCreateResponse
    r = SAKeyCreateResponse(id="k1", api_key="hc_sa_ceo_claude_xxx", description="test")
    assert r.api_key.startswith("hc_sa_")


def test_bank_policy_request():
    from hindclaw_ext.http_models import UpsertBankPolicyRequest
    req = UpsertBankPolicyRequest(document={"version": "2026-03-24", "default_strategy": "yoda-default"})
    assert req.document["default_strategy"] == "yoda-default"


def test_debug_resolve_response():
    from hindclaw_ext.http_models import DebugResolveResponse
    r = DebugResolveResponse(tenant_id="alice", principal_type="user", access={"allowed": True, "recall_budget": "high"}, bank_policy=None)
    assert r.principal_type == "user"
