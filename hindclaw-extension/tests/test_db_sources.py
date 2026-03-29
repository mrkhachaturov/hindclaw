"""Tests for template source database queries."""

from unittest.mock import AsyncMock, patch

import pytest

from hindclaw_ext import db
from hindclaw_ext.models import TemplateSourceRecord


def _fake_source_row(**overrides) -> dict:
    """Build a complete template source row dict for mocking asyncpg results."""
    defaults = {
        "name": "hindclaw",
        "url": "https://github.com/hindclaw/community-templates",
        "scope": "server",
        "owner": None,
        "auth_token": None,
        "created_at": "2026-03-25T12:00:00+00:00",
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    return pool


@pytest.fixture(autouse=True)
def _reset_pool():
    db._pool = None
    yield
    db._pool = None


class TestCreateSource:
    @pytest.mark.asyncio
    async def test_inserts_source(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_source_row()
        with patch.object(db, "_pool", mock_pool):
            result = await db.create_template_source(
                name="hindclaw",
                url="https://github.com/hindclaw/community-templates",
                auth_token=None,
            )
        assert isinstance(result, TemplateSourceRecord)
        assert result.name == "hindclaw"
        call_args = mock_pool.fetchrow.call_args
        sql = call_args[0][0]
        assert "INSERT INTO template_sources" in sql

    @pytest.mark.asyncio
    async def test_passes_auth_token(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_source_row(auth_token="ghp_abc123")
        with patch.object(db, "_pool", mock_pool):
            result = await db.create_template_source(
                name="private",
                url="https://github.com/astrateam/private-templates",
                auth_token="ghp_abc123",
            )
        assert result.auth_token == "ghp_abc123"


class TestGetSource:
    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, mock_pool):
        with patch.object(db, "_pool", mock_pool):
            result = await db.get_template_source("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_record_when_found(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_source_row()
        with patch.object(db, "_pool", mock_pool):
            result = await db.get_template_source("hindclaw")
        assert isinstance(result, TemplateSourceRecord)
        assert result.url == "https://github.com/hindclaw/community-templates"


class TestListSources:
    @pytest.mark.asyncio
    async def test_list_empty(self, mock_pool):
        with patch.object(db, "_pool", mock_pool):
            result = await db.list_template_sources()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_returns_records(self, mock_pool):
        mock_pool.fetch.return_value = [
            _fake_source_row(),
            _fake_source_row(name="astrateam", url="https://github.com/astrateam/templates"),
        ]
        with patch.object(db, "_pool", mock_pool):
            result = await db.list_template_sources()
        assert len(result) == 2
        assert result[0].name == "hindclaw"
        assert result[1].name == "astrateam"


class TestDeleteSource:
    @pytest.mark.asyncio
    async def test_delete_returns_true(self, mock_pool):
        mock_pool.execute.return_value = "DELETE 1"
        with patch.object(db, "_pool", mock_pool):
            result = await db.delete_template_source("hindclaw")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_missing(self, mock_pool):
        mock_pool.execute.return_value = "DELETE 0"
        with patch.object(db, "_pool", mock_pool):
            result = await db.delete_template_source("nonexistent")
        assert result is False
