"""Tests for response model imports and field shapes."""

import pytest

from hindclaw_ext.http_models import (
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ChannelResponse,
    GroupMemberResponse,
    GroupMembershipConfirmation,
    GroupSummaryResponse,
    UserResponse,
)


def test_user_response_fields():
    """UserResponse has exactly the public fields."""
    resp = UserResponse(id="alice", display_name="Alice", email="alice@example.com")
    assert resp.model_dump() == {
        "id": "alice",
        "display_name": "Alice",
        "email": "alice@example.com",
        "is_active": True,
    }


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

    req = CreatePolicyRequest(
        id="fleet-access",
        display_name="Fleet Access",
        document={"version": "2026-03-24", "statements": []},
    )
    assert req.id == "fleet-access"


def test_policy_response():
    from hindclaw_ext.http_models import PolicyResponse

    r = PolicyResponse(
        id="fleet-access",
        display_name="Fleet Access",
        document={"version": "2026-03-24", "statements": []},
        is_builtin=False,
    )
    assert r.is_builtin is False


def test_create_policy_attachment_request():
    from hindclaw_ext.http_models import CreatePolicyAttachmentRequest

    req = CreatePolicyAttachmentRequest(
        policy_id="fleet-access",
        principal_type="group",
        principal_id="default",
        priority=10,
    )
    assert req.priority == 10


def test_policy_attachment_response():
    from hindclaw_ext.http_models import PolicyAttachmentResponse

    r = PolicyAttachmentResponse(
        policy_id="fleet-access",
        principal_type="group",
        principal_id="default",
        priority=10,
    )
    assert r.principal_type == "group"


def test_create_service_account_request():
    from hindclaw_ext.http_models import CreateServiceAccountRequest

    req = CreateServiceAccountRequest(
        id="ceo-claude",
        owner_user_id="ceo@astrateam.net",
        display_name="CEO Claude",
        scoping_policy_id="claude-readonly",
    )
    assert req.scoping_policy_id == "claude-readonly"


def test_service_account_response():
    from hindclaw_ext.http_models import ServiceAccountResponse

    r = ServiceAccountResponse(
        id="ceo-claude",
        owner_user_id="ceo@astrateam.net",
        display_name="CEO Claude",
        is_active=True,
        scoping_policy_id=None,
    )
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

    r = DebugResolveResponse(
        tenant_id="alice",
        principal_type="user",
        access={"allowed": True, "recall_budget": "high"},
        bank_policy=None,
    )
    assert r.principal_type == "user"


def test_create_self_service_account_request_no_owner():
    """CreateSelfServiceAccountRequest has no owner_user_id field."""
    from hindclaw_ext.http_models import CreateSelfServiceAccountRequest

    req = CreateSelfServiceAccountRequest(id="my-sa", display_name="My SA")
    assert req.id == "my-sa"
    assert req.display_name == "My SA"
    assert req.scoping_policy_id is None
    assert "owner_user_id" not in CreateSelfServiceAccountRequest.model_fields


def test_create_self_service_account_request_rejects_extra_fields():
    """CreateSelfServiceAccountRequest rejects unknown fields."""
    from pydantic import ValidationError

    from hindclaw_ext.http_models import CreateSelfServiceAccountRequest

    with pytest.raises(ValidationError, match="extra"):
        CreateSelfServiceAccountRequest(id="sa", display_name="SA", owner_user_id="bob")


def test_update_self_service_account_request_display_name_only():
    """UpdateSelfServiceAccountRequest only accepts display_name."""
    from hindclaw_ext.http_models import UpdateSelfServiceAccountRequest

    req = UpdateSelfServiceAccountRequest(display_name="New Name")
    assert req.display_name == "New Name"
    assert "scoping_policy_id" not in UpdateSelfServiceAccountRequest.model_fields
    assert "is_active" not in UpdateSelfServiceAccountRequest.model_fields


def test_update_self_service_account_request_rejects_extra_fields():
    """UpdateSelfServiceAccountRequest rejects unknown fields."""
    from pydantic import ValidationError

    from hindclaw_ext.http_models import UpdateSelfServiceAccountRequest

    with pytest.raises(ValidationError, match="extra"):
        UpdateSelfServiceAccountRequest(display_name="OK", scoping_policy_id="nope")


def test_create_template_request_requires_valid_upstream_manifest():
    from pydantic import ValidationError

    from hindclaw_ext.http_models import CreateTemplateRequest

    with pytest.raises(ValidationError):
        CreateTemplateRequest.model_validate(
            {
                "id": "bad",
                "name": "Bad",
                "manifest": {
                    "version": "1",
                    "mental_models": [{"name": "no id field"}],
                },
            }
        )


def test_create_template_request_accepts_full_upstream_feature_set():
    from hindclaw_ext.http_models import CreateTemplateRequest

    manifest = {
        "version": "1",
        "bank": {
            "reflect_mission": "m",
            "retain_mission": "r",
            "retain_extraction_mode": "verbose",
            "entity_labels": [
                {
                    "key": "k",
                    "description": "d",
                    "type": "multi-values",
                    "optional": False,
                    "tag": True,
                    "values": [{"value": "v1", "description": ""}],
                }
            ],
        },
        "directives": [
            {
                "name": "d1",
                "content": "c",
                "priority": 7,
                "is_active": True,
                "tags": ["ops"],
            }
        ],
        "mental_models": [
            {
                "id": "mm-1",
                "name": "MM1",
                "source_query": "q",
                "tags": ["t"],
                "max_tokens": 1024,
                "trigger": {"refresh_after_consolidation": True},
            }
        ],
    }
    req = CreateTemplateRequest.model_validate(
        {
            "id": "x",
            "name": "X",
            "description": "d",
            "category": "coding",
            "integrations": ["claude-code"],
            "tags": ["t"],
            "manifest": manifest,
        }
    )
    assert req.id == "x"
    assert req.manifest.bank is not None
    assert req.manifest.directives[0].priority == 7


def test_install_template_request_defaults_source_scope_to_server():
    from hindclaw_ext.http_models import InstallTemplateRequest
    from hindclaw_ext.template_models import TemplateScope

    req = InstallTemplateRequest.model_validate({"source_name": "hindclaw-official"})
    assert req.source_scope is TemplateScope.SERVER
    assert req.alias_id is None


def test_install_template_request_rejects_unknown_fields():
    from pydantic import ValidationError

    from hindclaw_ext.http_models import InstallTemplateRequest

    with pytest.raises(ValidationError):
        InstallTemplateRequest.model_validate({"source_name": "x", "foo": "bar"})


def test_check_update_response_roundtrip():
    from hindclaw_ext.http_models import CheckUpdateResponse
    from hindclaw_ext.template_models import TemplateScope

    resp = CheckUpdateResponse.model_validate(
        {
            "has_update": True,
            "current_revision": "etag-old",
            "latest_revision": "etag-new",
            "source_name": "hindclaw-official",
            "source_scope": "server",
        }
    )
    assert resp.has_update is True
    assert resp.source_scope is TemplateScope.SERVER


def test_template_response_carries_manifest_as_dict():
    from datetime import datetime, timezone

    from hindclaw_ext.http_models import TemplateResponse

    resp = TemplateResponse.model_validate(
        {
            "id": "x",
            "name": "X",
            "description": "d",
            "category": "coding",
            "integrations": ["claude-code"],
            "tags": ["python"],
            "scope": "personal",
            "owner": "user-1",
            "source_name": "hindclaw-official",
            "source_scope": "server",
            "source_owner": None,
            "source_revision": "etag",
            "installed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "manifest": {"version": "1", "bank": {}},
        }
    )
    assert resp.manifest == {"version": "1", "bank": {}}


def test_me_profile_response():
    """MeProfileResponse has correct shape."""
    from hindclaw_ext.http_models import MeProfileResponse

    resp = MeProfileResponse(
        id="alice",
        display_name="Alice",
        email="alice@example.com",
        is_active=True,
        channels=[],
    )
    assert resp.id == "alice"
    assert resp.channels == []
