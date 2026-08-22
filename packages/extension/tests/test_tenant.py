"""Tests for hindclaw_ext.tenant — HindclawTenant extension."""

import time
from unittest.mock import patch

import jwt as pyjwt
import pytest
from hindsight_api.extensions import AuthenticationError

from hindclaw_ext.models import ApiKeyRecord, UserRecord
from hindclaw_ext.tenant import HindclawTenant, _jwt_claims
from tests.helpers import FakeRequestContext

TEST_SECRET = "test-secret-key-for-tenant-tests"


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch):
    """Ensure tests use test secret, not any real HINDCLAW_JWT_SECRET on this host."""
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", TEST_SECRET)


@pytest.fixture(autouse=True)
def _reset_jwt_claims():
    """Reset _jwt_claims contextvar between tests to prevent state leakage."""
    _jwt_claims.set({})
    yield
    _jwt_claims.set({})


def _make_jwt(claims: dict, secret: str = TEST_SECRET) -> str:
    return pyjwt.encode(claims, secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_jwt_auth_known_sender():
    """JWT with known sender resolves to user_id."""
    tenant = HindclawTenant({})
    token = _make_jwt(
        {
            "client_id": "app-prod",
            "sender": "telegram:100001",
            "agent": "agent-alpha",
            "exp": int(time.time()) + 300,
        }
    )
    ctx = FakeRequestContext(api_key=token)
    user = UserRecord(id="alice", display_name="Alice", email=None, is_active=True)

    with (
        patch("hindclaw_ext.tenant.db.get_user_by_channel", return_value=user),
        patch("hindclaw_ext.tenant.db.get_user", return_value=user),
    ):
        result = await tenant.authenticate(ctx)

    assert ctx.tenant_id == "alice"
    assert result.schema_name == "public"
    # JWT claims stored in contextvar
    claims = _jwt_claims.get({})
    assert claims["agent"] == "agent-alpha"


@pytest.mark.asyncio
async def test_jwt_auth_unknown_sender_unmapped():
    """JWT with unknown sender sets tenant_id to _unmapped (not _anonymous)."""
    tenant = HindclawTenant({})
    token = _make_jwt(
        {
            "sender": "telegram:999999",
            "exp": int(time.time()) + 300,
        }
    )
    ctx = FakeRequestContext(api_key=token)

    with patch("hindclaw_ext.tenant.db.get_user_by_channel", return_value=None):
        result = await tenant.authenticate(ctx)

    assert ctx.tenant_id == "_unmapped"
    assert result.schema_name == "public"


@pytest.mark.asyncio
async def test_jwt_auth_no_sender_rejected():
    """JWT without sender claim raises AuthenticationError."""
    tenant = HindclawTenant({})
    token = _make_jwt({"exp": int(time.time()) + 300})
    ctx = FakeRequestContext(api_key=token)

    with pytest.raises(AuthenticationError, match="sender claim"):
        await tenant.authenticate(ctx)


@pytest.mark.asyncio
async def test_jwt_auth_inactive_user():
    """JWT with sender mapping to inactive user sets _unmapped."""
    tenant = HindclawTenant({})
    token = _make_jwt(
        {
            "sender": "telegram:100001",
            "exp": int(time.time()) + 300,
        }
    )
    ctx = FakeRequestContext(api_key=token)
    channel_user = UserRecord(id="alice", display_name="Alice", email=None, is_active=True)
    inactive_user = UserRecord(id="alice", display_name="Alice", email=None, is_active=False)

    with (
        patch("hindclaw_ext.tenant.db.get_user_by_channel", return_value=channel_user),
        patch("hindclaw_ext.tenant.db.get_user", return_value=inactive_user),
    ):
        await tenant.authenticate(ctx)

    assert ctx.tenant_id == "_unmapped"


@pytest.mark.asyncio
async def test_api_key_auth():
    """API key resolves to user via DB lookup."""
    tenant = HindclawTenant({})
    ctx = FakeRequestContext(api_key="hc_alice_xxxx")
    key_record = ApiKeyRecord(id="k1", api_key="hc_alice_xxxx", user_id="alice")
    user = UserRecord(id="alice", display_name="Alice", email=None, is_active=True)

    with (
        patch("hindclaw_ext.tenant.db.get_api_key", return_value=key_record),
        patch("hindclaw_ext.tenant.db.get_user", return_value=user),
    ):
        result = await tenant.authenticate(ctx)

    assert ctx.tenant_id == "alice"
    assert result.schema_name == "public"


@pytest.mark.asyncio
async def test_api_key_invalid():
    """Invalid API key raises AuthenticationError."""
    tenant = HindclawTenant({})
    ctx = FakeRequestContext(api_key="hc_bad_key")

    with patch("hindclaw_ext.tenant.db.get_api_key", return_value=None):
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            await tenant.authenticate(ctx)


@pytest.mark.asyncio
async def test_missing_token():
    """No token raises AuthenticationError."""
    tenant = HindclawTenant({})
    ctx = FakeRequestContext(api_key=None)

    with pytest.raises(AuthenticationError, match="Missing"):
        await tenant.authenticate(ctx)


@pytest.mark.asyncio
async def test_expired_jwt():
    """Expired JWT raises AuthenticationError."""
    tenant = HindclawTenant({})
    token = _make_jwt({"exp": int(time.time()) - 10})
    ctx = FakeRequestContext(api_key=token)

    with pytest.raises(AuthenticationError, match="expired"):
        await tenant.authenticate(ctx)


@pytest.mark.asyncio
async def test_sa_api_key_auth():
    """SA API key (hc_sa_ prefix) resolves to sa:<sa_id> tenant_id."""
    from hindclaw_ext.models import ServiceAccountRecord

    tenant = HindclawTenant({})
    ctx = FakeRequestContext(api_key="hc_sa_ceo_claude_xxx")
    sa = ServiceAccountRecord(
        id="ceo-claude",
        owner_user_id="ceo@astrateam.net",
        display_name="CEO Claude",
        is_active=True,
        scoping_policy_id=None,
    )
    parent = UserRecord(id="ceo@astrateam.net", display_name="CEO", is_active=True)

    with (
        patch("hindclaw_ext.tenant.db.get_service_account_by_api_key", return_value=sa),
        patch("hindclaw_ext.tenant.db.get_user", return_value=parent),
    ):
        result = await tenant.authenticate(ctx)

    assert ctx.tenant_id == "sa:ceo-claude"
    assert result.schema_name == "public"


@pytest.mark.asyncio
async def test_sa_api_key_inactive():
    """Inactive SA is rejected."""
    from hindclaw_ext.models import ServiceAccountRecord

    tenant = HindclawTenant({})
    ctx = FakeRequestContext(api_key="hc_sa_disabled_xxx")
    sa = ServiceAccountRecord(
        id="disabled-sa",
        owner_user_id="ceo@astrateam.net",
        display_name="Disabled",
        is_active=False,
        scoping_policy_id=None,
    )

    with patch("hindclaw_ext.tenant.db.get_service_account_by_api_key", return_value=sa):
        with pytest.raises(AuthenticationError, match="inactive"):
            await tenant.authenticate(ctx)


@pytest.mark.asyncio
async def test_sa_api_key_invalid():
    """Unknown SA API key is rejected."""
    tenant = HindclawTenant({})
    ctx = FakeRequestContext(api_key="hc_sa_unknown_xxx")

    with patch("hindclaw_ext.tenant.db.get_service_account_by_api_key", return_value=None):
        with pytest.raises(AuthenticationError, match="Invalid"):
            await tenant.authenticate(ctx)


@pytest.mark.asyncio
async def test_user_api_key_prefix():
    """User API key (hc_u_ prefix) routes to user key lookup."""
    tenant = HindclawTenant({})
    ctx = FakeRequestContext(api_key="hc_u_alice_xxx")
    key_record = ApiKeyRecord(id="k1", api_key="hc_u_alice_xxx", user_id="alice")
    user = UserRecord(id="alice", display_name="Alice", email=None, is_active=True)

    with (
        patch("hindclaw_ext.tenant.db.get_api_key", return_value=key_record),
        patch("hindclaw_ext.tenant.db.get_user", return_value=user),
    ):
        await tenant.authenticate(ctx)

    assert ctx.tenant_id == "alice"
