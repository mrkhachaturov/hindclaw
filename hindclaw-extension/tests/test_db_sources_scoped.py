"""Tests for scoped template source database queries."""

from unittest.mock import AsyncMock, patch

import pytest

from hindclaw_ext import db
from hindclaw_ext.models import TemplateSourceRecord


def _fake_source_row(**overrides) -> dict:
    """Build a complete scoped template source row dict for mocking asyncpg results."""
    defaults = {
        "name": "hindclaw",
        "scope": "server",
        "owner": None,
        "url": "https://github.com/hindclaw/community-templates",
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


class TestCreateTemplateSourceServer:
    @pytest.mark.asyncio
    async def test_create_template_source_server(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_source_row(scope="server", owner=None)
        with patch.object(db, "_pool", mock_pool):
            result = await db.create_template_source(
                name="hindclaw",
                url="https://github.com/hindclaw/community-templates",
                scope="server",
            )
        assert isinstance(result, TemplateSourceRecord)
        assert result.name == "hindclaw"
        assert result.scope == "server"
        assert result.owner is None


class TestCreateTemplateSourcePersonal:
    @pytest.mark.asyncio
    async def test_create_template_source_personal(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_source_row(
            name="my-templates",
            scope="personal",
            owner="alice",
            url="https://github.com/alice/private-templates",
        )
        with patch.object(db, "_pool", mock_pool):
            result = await db.create_template_source(
                name="my-templates",
                url="https://github.com/alice/private-templates",
                scope="personal",
                owner="alice",
            )
        assert isinstance(result, TemplateSourceRecord)
        assert result.scope == "personal"
        assert result.owner == "alice"


class TestGetTemplateSourceScoped:
    @pytest.mark.asyncio
    async def test_get_template_source_scoped(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_source_row(scope="server", owner=None)
        with patch.object(db, "_pool", mock_pool):
            result = await db.get_template_source("hindclaw", scope="server")
        assert result is not None
        assert result.scope == "server"

    @pytest.mark.asyncio
    async def test_get_template_source_personal(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_source_row(
            name="my-templates",
            scope="personal",
            owner="alice",
        )
        with patch.object(db, "_pool", mock_pool):
            result = await db.get_template_source("my-templates", scope="personal", owner="alice")
        assert result is not None
        assert result.scope == "personal"
        assert result.owner == "alice"


class TestListTemplateSourcesByScope:
    @pytest.mark.asyncio
    async def test_list_template_sources_by_scope(self, mock_pool):
        mock_pool.fetch.return_value = [
            _fake_source_row(name="hindclaw", scope="server"),
            _fake_source_row(name="astrateam", scope="server"),
        ]
        with patch.object(db, "_pool", mock_pool):
            result = await db.list_template_sources(scope="server")
        assert len(result) == 2
        assert all(r.scope == "server" for r in result)

    @pytest.mark.asyncio
    async def test_list_template_sources_personal(self, mock_pool):
        mock_pool.fetch.return_value = [
            _fake_source_row(name="my-templates", scope="personal", owner="alice"),
        ]
        with patch.object(db, "_pool", mock_pool):
            result = await db.list_template_sources(scope="personal", owner="alice")
        assert len(result) == 1
        assert result[0].owner == "alice"


class TestResolveSource:
    @pytest.mark.asyncio
    async def test_resolve_source_unambiguous(self, mock_pool):
        """Single match returns it."""
        mock_pool.fetch.return_value = [
            _fake_source_row(name="hindclaw", scope="server"),
        ]
        with patch.object(db, "_pool", mock_pool):
            result = await db.resolve_source(name="hindclaw", caller="alice")
        assert isinstance(result, TemplateSourceRecord)
        assert result.name == "hindclaw"

    @pytest.mark.asyncio
    async def test_resolve_source_ambiguous(self, mock_pool):
        """Two matches raises ValueError('Ambiguous')."""
        mock_pool.fetch.return_value = [
            _fake_source_row(name="hindclaw", scope="server"),
            _fake_source_row(name="hindclaw", scope="personal", owner="alice"),
        ]
        with patch.object(db, "_pool", mock_pool):
            with pytest.raises(ValueError, match="Ambiguous"):
                await db.resolve_source(name="hindclaw", caller="alice")

    @pytest.mark.asyncio
    async def test_resolve_source_with_explicit_scope(self, mock_pool):
        """source_scope filters to exact match."""
        mock_pool.fetch.return_value = [
            _fake_source_row(name="hindclaw", scope="server"),
        ]
        with patch.object(db, "_pool", mock_pool):
            result = await db.resolve_source(
                name="hindclaw",
                caller="alice",
                source_scope="server",
            )
        assert result.scope == "server"

    @pytest.mark.asyncio
    async def test_resolve_source_not_found(self, mock_pool):
        """No match raises KeyError."""
        mock_pool.fetch.return_value = []
        with patch.object(db, "_pool", mock_pool):
            with pytest.raises(KeyError):
                await db.resolve_source(name="nonexistent", caller="alice")


class TestDeleteTemplateSourceScoped:
    @pytest.mark.asyncio
    async def test_delete_template_source_scoped(self, mock_pool):
        """Delete with scope+owner."""
        mock_pool.execute.return_value = "DELETE 1"
        with patch.object(db, "_pool", mock_pool):
            result = await db.delete_template_source(
                "my-templates",
                scope="personal",
                owner="alice",
            )
        assert result is True
        call_args = mock_pool.execute.call_args
        sql = call_args[0][0]
        assert "scope" in sql
        assert "owner" in sql

    @pytest.mark.asyncio
    async def test_delete_template_source_server(self, mock_pool):
        """Delete server scope (no owner)."""
        mock_pool.execute.return_value = "DELETE 1"
        with patch.object(db, "_pool", mock_pool):
            result = await db.delete_template_source("hindclaw", scope="server")
        assert result is True
