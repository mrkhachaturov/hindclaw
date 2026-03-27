"""Tests for template database queries."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from hindclaw_ext import db
from hindclaw_ext.models import TemplateRecord


def _fake_template_row(**overrides) -> dict:
    """Build a complete template row dict suitable for mocking asyncpg results.

    All JSONB columns are pre-serialized as strings (matching asyncpg behavior).
    Override any field by passing keyword arguments.
    """
    defaults = {
        "id": "backend-python",
        "scope": "server",
        "owner": None,
        "source_name": None,
        "schema_version": 1,
        "min_hindclaw_version": "0.2.0",
        "min_hindsight_version": "0.4.20",
        "version": None,
        "source_url": None,
        "source_revision": None,
        "description": "Backend patterns",
        "author": "",
        "tags": "[]",
        "retain_mission": "Extract backend patterns.",
        "reflect_mission": "You are a backend engineer.",
        "observations_mission": None,
        "retain_extraction_mode": "verbose",
        "retain_custom_instructions": None,
        "retain_chunk_size": None,
        "retain_default_strategy": None,
        "retain_strategies": "{}",
        "entity_labels": "[]",
        "entities_allow_free_form": True,
        "enable_observations": True,
        "consolidation_llm_batch_size": None,
        "consolidation_source_facts_max_tokens": None,
        "consolidation_source_facts_max_tokens_per_observation": None,
        "disposition_skepticism": 3,
        "disposition_literalism": 3,
        "disposition_empathy": 3,
        "directive_seeds": "[]",
        "mental_model_seeds": "[]",
        "created_at": "2026-03-25T12:00:00+00:00",
        "updated_at": "2026-03-25T12:00:00+00:00",
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
    """Reset the module-level pool before and after each test."""
    db._pool = None
    yield
    db._pool = None


class TestCreateTemplate:
    @pytest.mark.asyncio
    async def test_creates_template(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_template_row()
        with patch.object(db, "_pool", mock_pool):
            result = await db.create_template(
                id="backend-python",
                scope="server",
                owner=None,
                source_name=None,
                schema_version=1,
                min_hindclaw_version="0.2.0",
                min_hindsight_version="0.4.20",
                description="Backend patterns",
                author="",
                tags=["python"],
                retain_mission="Extract.",
                reflect_mission="You are.",
                retain_extraction_mode="verbose",
                entity_labels=[],
                entities_allow_free_form=True,
                enable_observations=True,
                disposition_skepticism=3,
                disposition_literalism=3,
                disposition_empathy=3,
                directive_seeds=[],
                mental_model_seeds=[],
            )
        assert isinstance(result, TemplateRecord)
        assert result.id == "backend-python"
        mock_pool.fetchrow.assert_called_once()
        call_args = mock_pool.fetchrow.call_args
        assert "INSERT INTO bank_templates" in call_args[0][0]


class TestGetTemplate:
    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, mock_pool):
        mock_pool.fetchrow.return_value = None
        with patch.object(db, "_pool", mock_pool):
            result = await db.get_template("backend-python", "server", source_name=None, owner=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_record_when_found(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_template_row()
        with patch.object(db, "_pool", mock_pool):
            result = await db.get_template("backend-python", "server", source_name=None, owner=None)
        assert isinstance(result, TemplateRecord)
        assert result.id == "backend-python"
        assert result.scope == "server"


class TestListTemplates:
    @pytest.mark.asyncio
    async def test_list_server_templates(self, mock_pool):
        mock_pool.fetch.return_value = []
        with patch.object(db, "_pool", mock_pool):
            result = await db.list_templates(scope="server")
        assert result == []
        mock_pool.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_returns_records(self, mock_pool):
        mock_pool.fetch.return_value = [_fake_template_row(), _fake_template_row(id="frontend-react")]
        with patch.object(db, "_pool", mock_pool):
            result = await db.list_templates(scope="server")
        assert len(result) == 2
        assert all(isinstance(r, TemplateRecord) for r in result)


class TestUpdateTemplate:
    @pytest.mark.asyncio
    async def test_update_returns_none_when_missing(self, mock_pool):
        mock_pool.fetchrow.return_value = None
        with patch.object(db, "_pool", mock_pool):
            result = await db.update_template(
                "backend-python", "server",
                source_name=None, owner=None,
                updates={"description": "Updated"},
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_returns_record(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_template_row(description="Updated")
        with patch.object(db, "_pool", mock_pool):
            result = await db.update_template(
                "backend-python", "server",
                source_name=None, owner=None,
                updates={"description": "Updated"},
            )
        assert isinstance(result, TemplateRecord)
        assert result.description == "Updated"

    @pytest.mark.asyncio
    async def test_update_jsonb_column(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_template_row(tags='["python", "updated"]')
        with patch.object(db, "_pool", mock_pool):
            result = await db.update_template(
                "backend-python", "server",
                source_name=None, owner=None,
                updates={"tags": ["python", "updated"]},
            )
        assert isinstance(result, TemplateRecord)
        call_args = mock_pool.fetchrow.call_args
        sql = call_args[0][0]
        assert "tags = $1::jsonb" in sql

    @pytest.mark.asyncio
    async def test_update_empty_updates_delegates_to_get(self, mock_pool):
        mock_pool.fetchrow.return_value = _fake_template_row()
        with patch.object(db, "_pool", mock_pool):
            result = await db.update_template(
                "backend-python", "server",
                source_name=None, owner=None,
                updates={},
            )
        assert isinstance(result, TemplateRecord)


class TestDeleteTemplate:
    @pytest.mark.asyncio
    async def test_delete_returns_true(self, mock_pool):
        mock_pool.execute.return_value = "DELETE 1"
        with patch.object(db, "_pool", mock_pool):
            result = await db.delete_template("backend-python", "server", source_name=None, owner=None)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_missing(self, mock_pool):
        mock_pool.execute.return_value = "DELETE 0"
        with patch.object(db, "_pool", mock_pool):
            result = await db.delete_template("backend-python", "server", source_name=None, owner=None)
        assert result is False
