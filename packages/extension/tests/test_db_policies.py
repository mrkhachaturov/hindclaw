"""Tests for policy-related DB query functions."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.helpers import MockRecord


@pytest.mark.asyncio
async def test_get_policy():
    """Fetch a single policy by ID."""
    import hindclaw_ext.db as db_mod
    from hindclaw_ext.models import PolicyRecord

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value=MockRecord(
            {
                "id": "fleet-access",
                "display_name": "Fleet Access",
                "document_json": '{"version":"2026-03-24","statements":[]}',
                "is_builtin": False,
            }
        )
    )

    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.get_policy("fleet-access")
    assert isinstance(result, PolicyRecord)
    assert result.id == "fleet-access"


@pytest.mark.asyncio
async def test_get_policy_not_found():
    """Return None for nonexistent policy."""
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)

    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.get_policy("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_policies_for_principal():
    """Fetch all policies attached to a user (direct + group)."""
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(
        return_value=[
            MockRecord(
                {
                    "id": "fleet-access",
                    "display_name": "Fleet",
                    "document_json": '{"version":"2026-03-24","statements":[]}',
                    "is_builtin": False,
                    "principal_type": "user",
                    "principal_id": "alice",
                    "priority": 0,
                }
            ),
            MockRecord(
                {
                    "id": "executive",
                    "display_name": "Executive",
                    "document_json": '{"version":"2026-03-24","statements":[]}',
                    "is_builtin": False,
                    "principal_type": "group",
                    "principal_id": "operators",
                    "priority": 10,
                }
            ),
        ]
    )

    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.get_policies_for_user("alice", ["operators"])
    assert len(result) == 2
    assert result[0].priority == 0
    assert result[1].priority == 10


@pytest.mark.asyncio
async def test_get_sa_by_api_key():
    """Look up service account by API key."""
    import hindclaw_ext.db as db_mod
    from hindclaw_ext.models import ServiceAccountRecord

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value=MockRecord(
            {
                "id": "ceo-claude",
                "owner_user_id": "ceo@astrateam.net",
                "scoping_policy_id": "claude-readonly",
                "display_name": "CEO Claude",
                "is_active": True,
            }
        )
    )

    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.get_service_account_by_api_key("hc_sa_xxx")
    assert isinstance(result, ServiceAccountRecord)
    assert result.id == "ceo-claude"
    assert result.scoping_policy_id == "claude-readonly"


@pytest.mark.asyncio
async def test_get_bank_policy():
    """Fetch bank policy by bank ID."""
    import hindclaw_ext.db as db_mod
    from hindclaw_ext.models import BankPolicyRecord

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value=MockRecord(
            {
                "bank_id": "yoda",
                "document_json": '{"version":"2026-03-24","default_strategy":"yoda-default"}',
            }
        )
    )

    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.get_bank_policy("yoda")
    assert isinstance(result, BankPolicyRecord)
    assert result.bank_id == "yoda"


@pytest.mark.asyncio
async def test_get_bank_policy_not_found():
    """Return None for bank with no policy."""
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)

    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.get_bank_policy("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_create_policy():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock()
    with patch.object(db_mod, "_pool", mock_pool):
        await db_mod.create_policy("fleet", "Fleet Access", {"version": "2026-03-24", "statements": []})
    mock_pool.execute.assert_called_once()
    call_args = mock_pool.execute.call_args[0]
    assert "INSERT INTO hindclaw_policies" in call_args[0]


@pytest.mark.asyncio
async def test_delete_policy():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock()
    with patch.object(db_mod, "_pool", mock_pool):
        await db_mod.delete_policy("fleet")
    mock_pool.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_policy_attachment():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock()
    with patch.object(db_mod, "_pool", mock_pool):
        await db_mod.create_policy_attachment("fleet", "group", "default", priority=10)
    mock_pool.execute.assert_called_once()


@pytest.mark.asyncio
async def test_list_policy_attachments():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(
        return_value=[
            MockRecord(
                {
                    "policy_id": "fleet",
                    "principal_type": "group",
                    "principal_id": "default",
                    "priority": 10,
                }
            ),
        ]
    )
    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.list_policy_attachments("fleet")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_create_service_account():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock()
    with patch.object(db_mod, "_pool", mock_pool):
        await db_mod.create_service_account("ceo-claude", "ceo@astrateam.net", "CEO Claude")
    mock_pool.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_sa_key():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock()
    with patch.object(db_mod, "_pool", mock_pool):
        await db_mod.create_sa_key("k1", "ceo-claude", "hc_sa_xxx", "Test key")
    mock_pool.execute.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_bank_policy():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock()
    with patch.object(db_mod, "_pool", mock_pool):
        await db_mod.upsert_bank_policy("yoda", {"version": "2026-03-24", "default_strategy": "yoda-default"})
    mock_pool.execute.assert_called_once()


@pytest.mark.asyncio
async def test_list_service_accounts():
    import hindclaw_ext.db as db_mod

    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(
        return_value=[
            MockRecord(
                {
                    "id": "ceo-claude",
                    "owner_user_id": "ceo@astrateam.net",
                    "display_name": "CEO Claude",
                    "is_active": True,
                    "scoping_policy_id": None,
                }
            ),
        ]
    )
    with patch.object(db_mod, "_pool", mock_pool):
        result = await db_mod.list_service_accounts()
    assert len(result) == 1
    assert result[0].id == "ceo-claude"
