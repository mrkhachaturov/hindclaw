"""Tests for hindclaw_ext.db — connection pool and queries."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.helpers import MockRecord, make_records


@pytest.fixture(autouse=True)
def _reset_pool():
    """Ensure db._pool is reset before and after each test."""
    from hindclaw_ext import db
    original = db._pool
    db._pool = None
    yield
    db._pool = original


@pytest.fixture(autouse=True)
def _set_db_url(monkeypatch):
    """Ensure HINDSIGHT_API_DATABASE_URL is set for pool init tests."""
    monkeypatch.setenv("HINDSIGHT_API_DATABASE_URL", "postgresql://test:test@localhost/test")


@pytest.mark.asyncio
async def test_get_pool_lazy_init():
    """Pool is created lazily on first call."""
    from hindclaw_ext import db

    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock(return_value=AsyncMock())

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    mock_pool = AsyncMock()
    mock_pool.acquire = fake_acquire

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as create:
        pool = await db.get_pool()
        assert pool is mock_pool
        create.assert_called_once()

        # Second call reuses the pool
        pool2 = await db.get_pool()
        assert pool2 is mock_pool
        create.assert_called_once()  # still just once


@pytest.mark.asyncio
async def test_get_user_by_channel(mock_pool):
    """Resolve sender ID to user."""
    from hindclaw_ext import db

    mock_pool.fetchrow.return_value = MockRecord({"id": "alice", "display_name": "Alice", "email": "alice@example.com", "is_active": True})

    with patch.object(db, "_pool", mock_pool):
        user = await db.get_user_by_channel("telegram", "100001")
        assert user is not None
        assert user.id == "alice"
        assert user.is_active is True

    mock_pool.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_by_channel_not_found(mock_pool):
    """Unknown sender returns None."""
    from hindclaw_ext import db

    mock_pool.fetchrow.return_value = None

    with patch.object(db, "_pool", mock_pool):
        user = await db.get_user_by_channel("telegram", "999999")
        assert user is None


@pytest.mark.asyncio
async def test_get_api_key(mock_pool):
    """Look up API key."""
    from hindclaw_ext import db

    mock_pool.fetchrow.return_value = MockRecord({"id": "key1", "api_key": "hc_alice_xxx", "user_id": "alice", "description": "test"})

    with patch.object(db, "_pool", mock_pool):
        key = await db.get_api_key("hc_alice_xxx")
        assert key is not None
        assert key.user_id == "alice"


@pytest.mark.asyncio
async def test_get_user_groups(mock_pool):
    """Get groups for a user."""
    from hindclaw_ext import db

    mock_pool.fetch.return_value = make_records([
        {"id": "team-lead", "display_name": "Team Lead"},
    ])

    with patch.object(db, "_pool", mock_pool):
        groups = await db.get_user_groups("alice")
        assert len(groups) == 1
        assert groups[0].id == "team-lead"


@pytest.mark.asyncio
async def test_ddl_creates_new_tables():
    """DDL creates policy, SA, and bank_policy tables."""
    from hindclaw_ext import db

    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock(return_value=AsyncMock())

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    mock_pool = AsyncMock()
    mock_pool.acquire = fake_acquire

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await db.get_pool()

    # Verify DDL was executed (check across all execute calls)
    all_calls = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    assert "hindclaw_policies" in all_calls
    assert "hindclaw_policy_attachments" in all_calls
    assert "hindclaw_service_accounts" in all_calls
    assert "hindclaw_service_account_keys" in all_calls
    assert "hindclaw_bank_policies" in all_calls
    assert "scoping_policy_id" in all_calls
    assert "is_active" in all_calls


@pytest.mark.asyncio
async def test_builtin_policies_seeded():
    """Built-in policies are seeded on first pool init."""
    from hindclaw_ext import db

    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock(return_value=AsyncMock())

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    mock_pool = AsyncMock()
    mock_pool.acquire = fake_acquire

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await db.get_pool()

    all_calls = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    # Built-in policies: bank:readwrite, bank:readonly, bank:retain-only, bank:admin, iam:admin
    assert "bank:readwrite" in all_calls
    assert "bank:readonly" in all_calls
    assert "bank:retain-only" in all_calls
    assert "bank:admin" in all_calls
    assert "iam:admin" in all_calls
    assert "is_builtin" in all_calls


@pytest.mark.asyncio
async def test_root_user_bootstrap(monkeypatch):
    """Root user is created from env vars on first pool init."""
    from hindclaw_ext import db

    monkeypatch.setenv("HINDCLAW_ROOT_USER", "ruben")
    monkeypatch.setenv("HINDCLAW_ROOT_API_KEY", "hc_u_root_xxx")

    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock(return_value=AsyncMock())

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    mock_pool = AsyncMock()
    mock_pool.acquire = fake_acquire

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await db.get_pool()

    # Check that root user seeding queries were executed
    all_calls = [str(c) for c in mock_conn.execute.call_args_list]
    all_text = " ".join(all_calls)
    assert "ruben" in all_text
    assert "hc_u_root_xxx" in all_text


@pytest.mark.asyncio
async def test_get_user_found(mock_pool):
    """get_user returns UserRecord for an existing user."""
    from hindclaw_ext import db

    mock_pool.fetchrow.return_value = MockRecord({
        "id": "alice", "display_name": "Alice", "email": "alice@example.com", "is_active": True,
    })

    with patch.object(db, "_pool", mock_pool):
        result = await db.get_user("alice")
    assert result is not None
    assert result.id == "alice"
    assert result.is_active is True


@pytest.mark.asyncio
async def test_get_user_not_found(mock_pool):
    """get_user returns None for unknown user."""
    from hindclaw_ext import db

    mock_pool.fetchrow.return_value = None

    with patch.object(db, "_pool", mock_pool):
        result = await db.get_user("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_service_account_found(mock_pool):
    """get_service_account returns ServiceAccountRecord."""
    from hindclaw_ext import db

    mock_pool.fetchrow.return_value = MockRecord({
        "id": "ceo-claude", "owner_user_id": "ruben",
        "display_name": "CEO Claude", "is_active": True,
        "scoping_policy_id": None,
    })

    with patch.object(db, "_pool", mock_pool):
        result = await db.get_service_account("ceo-claude")
    assert result is not None
    assert result.id == "ceo-claude"
    assert result.owner_user_id == "ruben"
    assert result.is_active is True


@pytest.mark.asyncio
async def test_get_service_account_not_found(mock_pool):
    """get_service_account returns None for unknown SA."""
    from hindclaw_ext import db

    mock_pool.fetchrow.return_value = None

    with patch.object(db, "_pool", mock_pool):
        result = await db.get_service_account("nonexistent")
    assert result is None


# --- update_service_account sentinel tests ---


@pytest.mark.asyncio
async def test_update_sa_only_provided_fields(mock_pool):
    """update_service_account only sets columns for provided fields."""
    from hindclaw_ext import db

    mock_pool.execute.return_value = "UPDATE 1"

    with patch.object(db, "_pool", mock_pool):
        result = await db.update_service_account("sa-1", display_name="New Name")
    assert result is True
    sql = mock_pool.execute.call_args[0][0]
    assert "display_name" in sql
    assert "scoping_policy_id" not in sql
    assert "is_active" not in sql


@pytest.mark.asyncio
async def test_update_sa_clear_scoping_policy_to_null(mock_pool):
    """Passing scoping_policy_id=None sets the column to SQL NULL."""
    from hindclaw_ext import db

    mock_pool.execute.return_value = "UPDATE 1"

    with patch.object(db, "_pool", mock_pool):
        result = await db.update_service_account("sa-1", scoping_policy_id=None)
    assert result is True
    sql = mock_pool.execute.call_args[0][0]
    assert "scoping_policy_id" in sql
    # The parameter for scoping_policy_id should be None (SQL NULL)
    params = mock_pool.execute.call_args[0][1:]
    assert None in params


@pytest.mark.asyncio
async def test_update_sa_no_fields_is_noop(mock_pool):
    """Calling with no arguments returns True without executing SQL."""
    from hindclaw_ext import db

    with patch.object(db, "_pool", mock_pool):
        result = await db.update_service_account("sa-1")
    assert result is True
    mock_pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_sa_set_scoping_policy(mock_pool):
    """Passing a string sets scoping_policy_id to that value."""
    from hindclaw_ext import db

    mock_pool.execute.return_value = "UPDATE 1"

    with patch.object(db, "_pool", mock_pool):
        await db.update_service_account("sa-1", scoping_policy_id="policy-abc")
    params = mock_pool.execute.call_args[0][1:]
    assert "policy-abc" in params
