"""Tests for hindclaw_ext.validator — policy-based access control."""

from unittest.mock import AsyncMock, patch

import pytest

from hindclaw_ext.policy_engine import AccessResult
from hindclaw_ext.tenant import _jwt_claims
from hindclaw_ext.validator import HindclawValidator
from tests.helpers import (
    FakeRecallContext,
    FakeReflectContext,
    FakeRequestContext,
    FakeRetainContext,
)


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-key-for-validator-tests")


@pytest.fixture(autouse=True)
def _reset_jwt_claims():
    _jwt_claims.set({})
    yield
    _jwt_claims.set({})


# --- Recall ---


@pytest.mark.asyncio
async def test_recall_allowed_with_tag_groups():
    """Recall allowed with tag_groups enrichment."""
    validator = HindclawValidator({})
    ctx = FakeRecallContext(bank_id="yoda", tenant_id="alice")
    _jwt_claims.set({"agent": "yoda"})

    access = AccessResult(
        allowed=True,
        recall_tag_groups=[{"not": {"tags": ["restricted"], "match": "any_strict"}}],
    )

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=access):
        result = await validator.validate_recall(ctx)

    assert result.allowed is True
    assert result.tag_groups is not None
    assert len(result.tag_groups) == 1


@pytest.mark.asyncio
async def test_recall_denied():
    """Recall denied returns reject with reason."""
    validator = HindclawValidator({})
    ctx = FakeRecallContext(bank_id="r2d2", tenant_id="alice")
    _jwt_claims.set({})

    with patch(
        "hindclaw_ext.validator._resolve_user_access",
        return_value=AccessResult(allowed=False),
    ):
        result = await validator.validate_recall(ctx)

    assert result.allowed is False
    assert "recall denied" in result.reason


@pytest.mark.asyncio
async def test_recall_no_tag_groups():
    """Recall with no tag_groups returns plain accept."""
    validator = HindclawValidator({})
    ctx = FakeRecallContext(bank_id="yoda", tenant_id="alice")
    _jwt_claims.set({})

    with patch(
        "hindclaw_ext.validator._resolve_user_access",
        return_value=AccessResult(allowed=True),
    ):
        result = await validator.validate_recall(ctx)

    assert result.allowed is True
    assert result.tag_groups is None


# --- Retain ---


@pytest.mark.asyncio
async def test_retain_enriches_tags_and_strategy():
    """Retain enriches content with policy tags, auto tags, and strategy."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(
        bank_id="yoda",
        tenant_id="alice",
        contents=[
            {"content": "conversation", "tags": ["existing:tag"]},
        ],
    )
    _jwt_claims.set({"agent": "yoda", "channel": "telegram"})

    access = AccessResult(
        allowed=True,
        retain_tags=["department:engineering"],
        retain_strategy="yoda-deep",
        resolved_user_id="alice",
    )

    with (
        patch("hindclaw_ext.validator._resolve_user_access", return_value=access),
        patch("hindclaw_ext.validator.db.get_bank_policy", return_value=None),
    ):
        result = await validator.validate_retain(ctx)

    assert result.allowed is True
    tags = result.contents[0]["tags"]
    assert "existing:tag" in tags
    assert "department:engineering" in tags
    assert "user:alice" in tags  # auto-injected
    assert "agent:yoda" in tags  # auto-injected
    assert result.contents[0]["strategy"] == "yoda-deep"


@pytest.mark.asyncio
async def test_retain_strategy_falls_back_to_bank_policy():
    """When no principal-level strategy, use bank policy."""
    from hindclaw_ext.models import BankPolicyRecord

    validator = HindclawValidator({})
    ctx = FakeRetainContext(bank_id="yoda", tenant_id="alice", contents=[{"content": "test"}])
    _jwt_claims.set({"agent": "yoda", "channel": "telegram"})

    access = AccessResult(allowed=True, retain_strategy=None, resolved_user_id="alice")

    bank_policy = BankPolicyRecord(
        bank_id="yoda",
        document_json={
            "version": "2026-03-24",
            "default_strategy": "yoda-default",
            "strategy_overrides": [
                {"scope": "provider", "value": "telegram", "strategy": "yoda-telegram"},
            ],
        },
    )

    with (
        patch("hindclaw_ext.validator._resolve_user_access", return_value=access),
        patch("hindclaw_ext.validator.db.get_bank_policy", return_value=bank_policy),
    ):
        result = await validator.validate_retain(ctx)

    assert result.contents[0]["strategy"] == "yoda-telegram"


@pytest.mark.asyncio
async def test_retain_denied():
    """Retain denied returns reject."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(bank_id="yoda", tenant_id="alice")
    _jwt_claims.set({})

    with patch(
        "hindclaw_ext.validator._resolve_user_access",
        return_value=AccessResult(allowed=False),
    ):
        result = await validator.validate_retain(ctx)

    assert result.allowed is False


@pytest.mark.asyncio
async def test_retain_no_existing_tags():
    """Retain works when content has no existing tags (None)."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(bank_id="yoda", tenant_id="alice", contents=[{"content": "test"}])
    _jwt_claims.set({})

    access = AccessResult(allowed=True, resolved_user_id="alice")

    with (
        patch("hindclaw_ext.validator._resolve_user_access", return_value=access),
        patch("hindclaw_ext.validator.db.get_bank_policy", return_value=None),
    ):
        result = await validator.validate_retain(ctx)

    assert "user:alice" in result.contents[0]["tags"]


# --- Reflect ---


@pytest.mark.asyncio
async def test_reflect_independent_of_recall():
    """Reflect checks bank:reflect, not bank:recall."""
    validator = HindclawValidator({})
    ctx = FakeReflectContext(bank_id="yoda", tenant_id="alice")
    _jwt_claims.set({})

    access = AccessResult(allowed=True)

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=access) as mock:
        result = await validator.validate_reflect(ctx)

    assert result.allowed is True
    mock.assert_called_once_with("alice", "bank:reflect", "yoda")


@pytest.mark.asyncio
async def test_reflect_denied():
    """Reflect denied returns reject."""
    validator = HindclawValidator({})
    ctx = FakeReflectContext(bank_id="yoda", tenant_id="alice")
    _jwt_claims.set({})

    with patch(
        "hindclaw_ext.validator._resolve_user_access",
        return_value=AccessResult(allowed=False),
    ):
        result = await validator.validate_reflect(ctx)

    assert result.allowed is False


# --- Internal bypass ---


@pytest.mark.asyncio
async def test_internal_bypass_recall():
    """Internal calls (no auth, tenant_id=None) bypass permissions."""
    validator = HindclawValidator({})
    ctx = FakeRecallContext(tenant_id=None)
    ctx.request_context.api_key = None

    with patch("hindclaw_ext.validator._resolve_user_access") as mock:
        result = await validator.validate_recall(ctx)

    assert result.allowed is True
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_internal_bypass_retain():
    """Internal retain calls bypass permissions."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(tenant_id=None)
    ctx.request_context.api_key = None

    with patch("hindclaw_ext.validator._resolve_user_access") as mock:
        result = await validator.validate_retain(ctx)

    assert result.allowed is True
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_internal_bypass_reflect():
    """Internal reflect calls bypass permissions."""
    validator = HindclawValidator({})
    ctx = FakeReflectContext(tenant_id=None)
    ctx.request_context.api_key = None

    with patch("hindclaw_ext.validator._resolve_user_access") as mock:
        result = await validator.validate_reflect(ctx)

    assert result.allowed is True
    mock.assert_not_called()


# --- SA access ---


@pytest.mark.asyncio
async def test_sa_access_routed():
    """sa: prefixed tenant_id routes to SA access resolver."""
    validator = HindclawValidator({})
    ctx = FakeRecallContext(bank_id="yoda", tenant_id="sa:ceo-claude")
    _jwt_claims.set({})

    access = AccessResult(allowed=True, recall_budget="mid")

    with patch("hindclaw_ext.validator._resolve_sa_access", return_value=access) as mock:
        result = await validator.validate_recall(ctx)

    assert result.allowed is True
    mock.assert_called_once_with("ceo-claude", "bank:recall", "yoda")


# --- Public access ---


@pytest.mark.asyncio
async def test_unmapped_recall_public_access():
    """Unmapped sender gets recall via bank public access."""
    validator = HindclawValidator({})
    ctx = FakeRecallContext(bank_id="yoda", tenant_id="_unmapped")
    _jwt_claims.set({"channel": "telegram"})

    access = AccessResult(allowed=True, recall_budget="low", recall_max_tokens=256)

    with patch("hindclaw_ext.validator._resolve_public_access", return_value=access):
        result = await validator.validate_recall(ctx)

    assert result.allowed is True


@pytest.mark.asyncio
async def test_unmapped_retain_denied_no_public():
    """Unmapped sender denied retain when bank has no public access for it."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(bank_id="r2d2", tenant_id="_unmapped")
    _jwt_claims.set({})

    with patch(
        "hindclaw_ext.validator._resolve_public_access",
        return_value=AccessResult(allowed=False),
    ):
        result = await validator.validate_retain(ctx)

    assert result.allowed is False


# --- Internal bypass edge cases ---


@pytest.mark.asyncio
async def test_unmapped_with_jwt_is_not_internal():
    """_unmapped with JWT claims present is NOT internal."""
    from tests.helpers import FakeRequestContext

    validator = HindclawValidator({})
    assert not validator._is_internal_server_call(FakeRequestContext(api_key="eyJtoken", tenant_id="_unmapped"))
    _jwt_claims.set({"sender": "telegram:999"})
    assert not validator._is_internal_server_call(FakeRequestContext(api_key="eyJtoken", tenant_id="_unmapped"))


def test_internal_check_true_when_no_auth():
    """No API key + no claims + None tenant = internal."""
    from tests.helpers import FakeRequestContext

    validator = HindclawValidator({})
    _jwt_claims.set({})
    assert validator._is_internal_server_call(FakeRequestContext(api_key=None, tenant_id=None))


# --- filter_mcp_tools ---


@pytest.mark.asyncio
async def test_filter_mcp_tools_recall_only():
    """User with only bank:recall sees read tools, not write or admin."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="alice")

    all_tools = frozenset(
        {
            "recall",
            "retain",
            "reflect",
            "list_memories",
            "get_memory",
            "delete_memory",
            "list_mental_models",
            "create_mental_model",
            "get_bank",
            "update_bank",
        }
    )

    recall_allowed = AccessResult(allowed=True)
    retain_denied = AccessResult(allowed=False)
    reflect_denied = AccessResult(allowed=False)
    admin_denied = AccessResult(allowed=False)

    async def mock_resolve(tenant_id, action, bank_id):
        if action == "bank:recall":
            return recall_allowed
        if action == "bank:retain":
            return retain_denied
        if action == "bank:reflect":
            return reflect_denied
        if action == "bank:admin":
            return admin_denied
        return AccessResult(allowed=False)

    with patch("hindclaw_ext.validator._resolve_user_access", side_effect=mock_resolve):
        result = await validator.filter_mcp_tools("test-bank", ctx, all_tools)

    assert "recall" in result
    assert "list_memories" in result
    assert "get_memory" in result
    assert "list_mental_models" in result
    assert "get_bank" in result
    assert "retain" not in result
    assert "delete_memory" not in result
    assert "create_mental_model" not in result
    assert "reflect" not in result
    assert "update_bank" not in result


@pytest.mark.asyncio
async def test_filter_mcp_tools_readwrite_sees_all():
    """User with bank:readwrite sees recall, retain, and reflect tools."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="admin-user")

    tools = frozenset({"recall", "retain", "reflect", "list_memories", "delete_memory"})

    all_allowed = AccessResult(allowed=True)

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=all_allowed):
        result = await validator.filter_mcp_tools("test-bank", ctx, tools)

    assert result == tools


@pytest.mark.asyncio
async def test_filter_mcp_tools_reflect_only():
    """User with only bank:reflect sees reflect tool and nothing else."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="reader")

    tools = frozenset({"recall", "retain", "reflect", "list_memories"})

    async def mock_resolve(tenant_id, action, bank_id):
        if action == "bank:reflect":
            return AccessResult(allowed=True)
        return AccessResult(allowed=False)

    with patch("hindclaw_ext.validator._resolve_user_access", side_effect=mock_resolve):
        result = await validator.filter_mcp_tools("domain::backend", ctx, tools)

    assert result == frozenset({"reflect"})


@pytest.mark.asyncio
async def test_filter_mcp_tools_unknown_tools_pass_through():
    """Tools not in _TOOL_ACTION_MAP are visible (fail-open)."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="alice")

    tools = frozenset({"recall", "some_future_tool"})

    with patch(
        "hindclaw_ext.validator._resolve_user_access",
        return_value=AccessResult(allowed=True),
    ):
        result = await validator.filter_mcp_tools("test-bank", ctx, tools)

    assert "recall" in result
    assert "some_future_tool" in result


@pytest.mark.asyncio
async def test_filter_mcp_tools_no_tenant_returns_all():
    """No tenant_id means no filtering (pass all tools through)."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id=None)

    tools = frozenset({"recall", "retain", "reflect"})

    result = await validator.filter_mcp_tools("test-bank", ctx, tools)

    assert result == tools


@pytest.mark.asyncio
async def test_filter_mcp_tools_caches_per_action():
    """Multiple tools mapping to same action trigger only one policy check."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="alice")

    tools = frozenset({"recall", "list_memories", "get_memory"})

    mock_resolve = AsyncMock(return_value=AccessResult(allowed=True))

    with patch("hindclaw_ext.validator._resolve_user_access", mock_resolve):
        result = await validator.filter_mcp_tools("test-bank", ctx, tools)

    assert result == tools
    assert mock_resolve.call_count == 1
    mock_resolve.assert_called_once_with("alice", "bank:recall", "test-bank")


@pytest.mark.asyncio
async def test_filter_mcp_tools_admin_tools():
    """Admin tools require bank:admin action."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="alice")

    tools = frozenset({"recall", "update_bank", "delete_bank", "create_bank"})

    async def mock_resolve(tenant_id, action, bank_id):
        if action == "bank:recall":
            return AccessResult(allowed=True)
        if action == "bank:admin":
            return AccessResult(allowed=False)
        return AccessResult(allowed=False)

    with patch("hindclaw_ext.validator._resolve_user_access", side_effect=mock_resolve):
        result = await validator.filter_mcp_tools("test-bank", ctx, tools)

    assert "recall" in result
    assert "update_bank" not in result
    assert "delete_bank" not in result
    assert "create_bank" not in result


@pytest.mark.asyncio
async def test_filter_mcp_tools_sa_identity():
    """Service account identity routes through _resolve_access correctly."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="sa:terraform-ci")

    tools = frozenset({"recall", "retain", "reflect"})

    with patch(
        "hindclaw_ext.validator._resolve_sa_access",
        return_value=AccessResult(allowed=True),
    ) as mock_sa:
        result = await validator.filter_mcp_tools("test-bank", ctx, tools)

    assert result == tools
    assert mock_sa.call_count >= 1


@pytest.mark.asyncio
async def test_filter_mcp_tools_unmapped_identity():
    """Unmapped sender routes to public access resolution."""
    validator = HindclawValidator({})
    ctx = FakeRequestContext(tenant_id="_unmapped")
    _jwt_claims.set({"channel": "telegram"})

    tools = frozenset({"recall", "retain", "reflect"})

    # Public access only allows recall
    async def mock_public(bank_id, action):
        if action == "bank:recall":
            return AccessResult(allowed=True)
        return AccessResult(allowed=False)

    with patch("hindclaw_ext.validator._resolve_public_access", side_effect=mock_public):
        result = await validator.filter_mcp_tools("test-bank", ctx, tools)

    assert "recall" in result
    assert "retain" not in result
    assert "reflect" not in result
