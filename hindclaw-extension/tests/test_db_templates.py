"""Tests for the bank_templates schema and query functions after the
convergence refactor. All tests mock asyncpg per the project convention
(pytest-asyncio strict + mocked pool fixtures in conftest.py)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from hindclaw_ext.db import (
    BANK_TEMPLATES_DDL,
    create_template,
    delete_template,
    fetch_installed_template_for_apply,
    get_template,
    list_templates,
    update_template,
)
from hindclaw_ext.models import TemplateRecord
from hindclaw_ext.template_models import TemplateScope

# Note: Async tests in this file use @pytest.mark.asyncio individually (rather
# than a module-level pytestmark) because the DDL string assertions are sync.


def _fixed_now() -> datetime:
    return datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)


def _sample_record(
    *,
    id: str = "backend-python",
    scope: TemplateScope = TemplateScope.PERSONAL,
    owner: str | None = "user-1",
    source_name: str | None = "hindclaw-official",
    source_scope: TemplateScope | None = TemplateScope.SERVER,
    source_owner: str | None = None,
) -> TemplateRecord:
    now = _fixed_now()
    return TemplateRecord(
        id=id,
        scope=scope,
        owner=owner,
        source_name=source_name,
        source_scope=source_scope,
        source_owner=source_owner,
        source_template_id=id,
        source_url="https://example.com/raw",
        source_revision="etag-abc",
        name=f"{id} name",
        description="desc",
        category="coding",
        integrations=["claude-code"],
        tags=["python"],
        manifest={"version": "1", "bank": {"reflect_mission": "m"}},
        installed_at=now,
        updated_at=now,
    )


# --------------------------------------------------------------------------- #
# DDL — guarantees from Section 4.3 of the spec
# --------------------------------------------------------------------------- #


def test_ddl_has_surrogate_row_id_primary_key():
    assert "row_id" in BANK_TEMPLATES_DDL
    assert "BIGSERIAL PRIMARY KEY" in BANK_TEMPLATES_DDL


def test_ddl_has_nulls_not_distinct_natural_key_index():
    assert "bank_templates_natural_key" in BANK_TEMPLATES_DDL
    assert "NULLS NOT DISTINCT" in BANK_TEMPLATES_DDL
    assert "(id, scope, owner)" in BANK_TEMPLATES_DDL


def test_ddl_has_scope_owner_check_constraint():
    assert "bank_templates_scope_owner" in BANK_TEMPLATES_DDL
    assert "scope = 'personal' AND owner IS NOT NULL" in BANK_TEMPLATES_DDL
    assert "scope = 'server' AND owner IS NULL" in BANK_TEMPLATES_DDL


def test_ddl_has_tags_gin_index():
    assert "bank_templates_tags_gin" in BANK_TEMPLATES_DDL
    assert "USING GIN (tags jsonb_path_ops)" in BANK_TEMPLATES_DDL


def test_ddl_has_category_index():
    assert "bank_templates_category_idx" in BANK_TEMPLATES_DDL


def test_ddl_has_source_attribution_columns():
    for col in (
        "source_name",
        "source_scope",
        "source_owner",
        "source_template_id",
        "source_url",
        "source_revision",
    ):
        assert col in BANK_TEMPLATES_DDL, f"column {col} missing from DDL"


# --------------------------------------------------------------------------- #
# Query functions
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_template_inserts_record(mock_pool):
    record = _sample_record()
    await create_template(mock_pool, record)

    mock_pool.execute.assert_awaited()
    call_args = mock_pool.execute.call_args_list[-1]
    sql = call_args.args[0]
    assert "INSERT INTO bank_templates" in sql
    # Pure INSERT — must NOT silently upsert on natural-key collision.
    # The route layer raises 409 on UniqueViolationError per the
    # convergence design (Finding 3 fix).
    assert "ON CONFLICT" not in sql


@pytest.mark.asyncio
async def test_get_template_takes_natural_key_tuple(mock_pool):
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "id": "backend-python",
            "scope": "personal",
            "owner": "user-1",
            "source_name": "hindclaw-official",
            "source_scope": "server",
            "source_owner": None,
            "source_template_id": "backend-python",
            "source_url": "https://example.com/raw",
            "source_revision": "etag",
            "name": "Backend Python",
            "description": "d",
            "category": "coding",
            "integrations": '["claude-code"]',
            "tags": '["python"]',
            "manifest": '{"version": "1", "bank": {}}',
            "installed_at": _fixed_now(),
            "updated_at": _fixed_now(),
        }
    )

    record = await get_template(
        mock_pool,
        id="backend-python",
        scope=TemplateScope.PERSONAL,
        owner="user-1",
    )
    assert record is not None
    assert record.id == "backend-python"
    assert record.scope is TemplateScope.PERSONAL
    assert record.owner == "user-1"
    assert record.manifest == {"version": "1", "bank": {}}


@pytest.mark.asyncio
async def test_get_template_returns_none_on_miss(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    record = await get_template(
        mock_pool,
        id="missing",
        scope=TemplateScope.PERSONAL,
        owner="user-1",
    )
    assert record is None


@pytest.mark.asyncio
async def test_list_templates_filters_by_scope_and_owner(mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    await list_templates(mock_pool, scope=TemplateScope.PERSONAL, owner="user-1")
    assert mock_pool.fetch.await_count == 1
    sql, *params = mock_pool.fetch.call_args.args
    assert "WHERE scope" in sql
    assert "owner" in sql


@pytest.mark.asyncio
async def test_list_templates_filter_by_category(mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    await list_templates(
        mock_pool,
        scope=TemplateScope.SERVER,
        owner=None,
        category="coding",
    )
    sql, *params = mock_pool.fetch.call_args.args
    assert "category" in sql
    assert "coding" in params


@pytest.mark.asyncio
async def test_list_templates_filter_by_tag(mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    await list_templates(
        mock_pool,
        scope=TemplateScope.SERVER,
        owner=None,
        tag="python",
    )
    sql, *params = mock_pool.fetch.call_args.args
    assert "tags @>" in sql or "tags ? " in sql


@pytest.mark.asyncio
async def test_update_template_replaces_manifest(mock_pool):
    record = _sample_record()
    mock_pool.execute = AsyncMock()
    await update_template(mock_pool, record)
    sql, *params = mock_pool.execute.call_args.args
    assert "UPDATE bank_templates" in sql
    assert "SET" in sql


@pytest.mark.asyncio
async def test_delete_template_uses_natural_key(mock_pool):
    mock_pool.execute = AsyncMock(return_value="DELETE 1")
    deleted = await delete_template(
        mock_pool,
        id="backend-python",
        scope=TemplateScope.PERSONAL,
        owner="user-1",
    )
    assert deleted is True
    sql, *params = mock_pool.execute.call_args.args
    assert "DELETE FROM bank_templates" in sql
    assert "id = $1" in sql


@pytest.mark.asyncio
async def test_delete_template_returns_false_on_miss(mock_pool):
    mock_pool.execute = AsyncMock(return_value="DELETE 0")
    deleted = await delete_template(
        mock_pool,
        id="missing",
        scope=TemplateScope.PERSONAL,
        owner="user-1",
    )
    assert deleted is False


@pytest.mark.asyncio
async def test_fetch_installed_template_for_apply_parses_personal_ref(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    await fetch_installed_template_for_apply(
        mock_pool,
        template="personal/backend-python",
        current_user="user-1",
    )
    sql, *params = mock_pool.fetchrow.call_args.args
    assert "id = $1" in sql
    assert "backend-python" in params
    assert "user-1" in params


@pytest.mark.asyncio
async def test_fetch_installed_template_for_apply_parses_server_ref(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    await fetch_installed_template_for_apply(
        mock_pool,
        template="server/conversation",
        current_user="user-1",
    )
    sql, *params = mock_pool.fetchrow.call_args.args
    assert "owner IS NULL" in sql


@pytest.mark.asyncio
async def test_fetch_installed_template_for_apply_rejects_bad_ref(mock_pool):
    with pytest.raises(ValueError):
        await fetch_installed_template_for_apply(
            mock_pool,
            template="not-a-ref",
            current_user="user-1",
        )
