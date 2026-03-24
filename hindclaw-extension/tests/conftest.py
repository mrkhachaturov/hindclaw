"""Shared test fixtures for hindclaw-extension tests."""
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_pool():
    """Mock asyncpg connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    # Also support pool.fetchrow / pool.fetch directly
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetchval = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def seed_data():
    """Standard test data matching spec examples."""
    return {
        "users": [
            {"id": "alice", "display_name": "Alice", "email": "alice@example.com"},
            {"id": "bob", "display_name": "Bob", "email": None},
        ],
        "channels": [
            {"user_id": "alice", "provider": "telegram", "sender_id": "100001"},
            {"user_id": "bob", "provider": "telegram", "sender_id": "100002"},
        ],
        "groups": [
            {"id": "team-lead", "display_name": "Team Lead"},
            {"id": "engineering", "display_name": "Engineering"},
        ],
        "memberships": [
            {"group_id": "team-lead", "user_id": "alice"},
            {"group_id": "engineering", "user_id": "alice"},
            {"group_id": "engineering", "user_id": "bob"},
        ],
    }
