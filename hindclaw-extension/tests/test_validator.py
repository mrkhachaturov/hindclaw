"""Tests for hindclaw_ext.validator — policy-based access control."""
from unittest.mock import patch, AsyncMock

import pytest

from hindclaw_ext.validator import HindclawValidator, _resolve_user_access, _resolve_public_access
from hindclaw_ext.tenant import _jwt_claims
from hindclaw_ext.policy_engine import AccessResult
from tests.helpers import FakeRecallContext, FakeRetainContext, FakeReflectContext


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

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=AccessResult(allowed=False)):
        result = await validator.validate_recall(ctx)

    assert result.allowed is False
    assert "recall denied" in result.reason


@pytest.mark.asyncio
async def test_recall_no_tag_groups():
    """Recall with no tag_groups returns plain accept."""
    validator = HindclawValidator({})
    ctx = FakeRecallContext(bank_id="yoda", tenant_id="alice")
    _jwt_claims.set({})

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=AccessResult(allowed=True)):
        result = await validator.validate_recall(ctx)

    assert result.allowed is True
    assert result.tag_groups is None


# --- Retain ---

@pytest.mark.asyncio
async def test_retain_enriches_tags_and_strategy():
    """Retain enriches content with policy tags, auto tags, and strategy."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(bank_id="yoda", tenant_id="alice", contents=[
        {"content": "conversation", "tags": ["existing:tag"]},
    ])
    _jwt_claims.set({"agent": "yoda", "channel": "telegram"})

    access = AccessResult(
        allowed=True,
        retain_tags=["department:engineering"],
        retain_strategy="yoda-deep",
        resolved_user_id="alice",
    )

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=access), \
         patch("hindclaw_ext.validator.db.get_bank_policy", return_value=None):
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

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=access), \
         patch("hindclaw_ext.validator.db.get_bank_policy", return_value=bank_policy):
        result = await validator.validate_retain(ctx)

    assert result.contents[0]["strategy"] == "yoda-telegram"


@pytest.mark.asyncio
async def test_retain_denied():
    """Retain denied returns reject."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(bank_id="yoda", tenant_id="alice")
    _jwt_claims.set({})

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=AccessResult(allowed=False)):
        result = await validator.validate_retain(ctx)

    assert result.allowed is False


@pytest.mark.asyncio
async def test_retain_no_existing_tags():
    """Retain works when content has no existing tags (None)."""
    validator = HindclawValidator({})
    ctx = FakeRetainContext(bank_id="yoda", tenant_id="alice", contents=[{"content": "test"}])
    _jwt_claims.set({})

    access = AccessResult(allowed=True, resolved_user_id="alice")

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=access), \
         patch("hindclaw_ext.validator.db.get_bank_policy", return_value=None):
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

    with patch("hindclaw_ext.validator._resolve_user_access", return_value=AccessResult(allowed=False)):
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

    with patch("hindclaw_ext.validator._resolve_public_access",
               return_value=AccessResult(allowed=False)):
        result = await validator.validate_retain(ctx)

    assert result.allowed is False
