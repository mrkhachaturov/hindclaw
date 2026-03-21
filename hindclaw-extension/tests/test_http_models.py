"""Tests for response model imports and field shapes."""

from hindclaw_ext.http_models import (
    UserResponse,
    ChannelResponse,
    GroupResponse,
    GroupSummaryResponse,
    GroupMemberResponse,
    GroupMembershipConfirmation,
    BankPermissionResponse,
    StrategyScopeResponse,
    StrategyUpsertConfirmation,
    ApiKeyResponse,
    ApiKeyCreateResponse,
    ResolvedPermissionsResponse,
    UpsertConfirmation,
)


def test_user_response_fields():
    """UserResponse has exactly the public fields."""
    resp = UserResponse(id="alice", display_name="Alice", email="alice@example.com")
    assert resp.model_dump() == {"id": "alice", "display_name": "Alice", "email": "alice@example.com"}


def test_group_response_includes_permission_fields():
    """GroupResponse includes all permission fields."""
    resp = GroupResponse(
        id="engineering", display_name="Engineering",
        recall=True, retain=False,
    )
    data = resp.model_dump()
    assert data["id"] == "engineering"
    assert data["recall"] is True
    assert data["retain_strategy"] is None  # default


def test_bank_permission_response():
    """BankPermissionResponse includes scope identifiers + permission fields."""
    resp = BankPermissionResponse(
        bank_id="agent-alpha", scope_type="group", scope_id="team-lead",
        recall=True,
    )
    assert resp.bank_id == "agent-alpha"
    assert resp.recall is True


def test_api_key_create_response_includes_full_key():
    """ApiKeyCreateResponse shows the full key (only at creation time)."""
    resp = ApiKeyCreateResponse(id="k1", api_key="hc_alice_xxx", description="test")
    assert resp.api_key == "hc_alice_xxx"


def test_api_key_response_masks_key():
    """ApiKeyResponse in list view shows masked key."""
    resp = ApiKeyResponse(id="k1", api_key_prefix="hc_alice_", description="test")
    assert "hc_alice_" in resp.api_key_prefix


def test_group_membership_confirmation():
    """GroupMembershipConfirmation returned by POST /groups/:id/members."""
    resp = GroupMembershipConfirmation(group_id="engineering", user_id="alice")
    assert resp.group_id == "engineering"
    assert resp.user_id == "alice"


def test_strategy_upsert_confirmation():
    """StrategyUpsertConfirmation returned by PUT /banks/:bank/strategies/:type/:value."""
    resp = StrategyUpsertConfirmation(
        bank_id="agent-alpha", scope_type="topic", scope_value="500001", strategy="conversation"
    )
    assert resp.strategy == "conversation"


def test_strategy_scope_response():
    """StrategyScopeResponse returned by GET /banks/:bank/strategies."""
    resp = StrategyScopeResponse(
        bank_id="agent-alpha", scope_type="topic", scope_value="500001", strategy="conversation"
    )
    assert resp.scope_type == "topic"


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


def test_upsert_confirmation():
    """UpsertConfirmation has bank_id, scope_type, scope_id."""
    resp = UpsertConfirmation(bank_id="agent-alpha", scope_type="group", scope_id="engineering")
    assert resp.bank_id == "agent-alpha"
    assert resp.scope_type == "group"


def test_resolved_permissions_response():
    """ResolvedPermissionsResponse has all required fields with correct types."""
    resp = ResolvedPermissionsResponse(
        user_id="alice", is_anonymous=False,
        recall=True, retain=True,
        retain_roles=["assistant"], retain_tags=["department:engineering"],
        retain_every_n_turns=3, retain_strategy="conversation",
        recall_budget="mid", recall_max_tokens=2000,
        recall_tag_groups=None, llm_model=None, llm_provider=None,
        exclude_providers=[],
    )
    assert resp.user_id == "alice"
    assert resp.recall is True
    assert resp.retain_roles == ["assistant"]
    assert resp.recall_budget == "mid"
