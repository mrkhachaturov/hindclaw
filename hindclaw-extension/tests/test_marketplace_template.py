"""Tests for marketplace.fetch_and_resolve_template() after the refactor."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from hindclaw_ext.marketplace import clear_cache, fetch_and_resolve_template
from hindclaw_ext.template_models import TemplateScope

pytestmark = pytest.mark.asyncio


INLINE_CATALOG = (
    b'{"catalog_version": "1", "templates": [{"id": "conversation", '
    b'"name": "Conversation", "manifest": {"version": "1", "bank": {"reflect_mission": "m"}}}]}'
)

REFERENCE_CATALOG = (
    b'{"catalog_version": "1", "templates": [{"id": "backend-python", '
    b'"name": "Backend Python", "manifest_file": "templates/backend-python.json"}]}'
)

REFERENCED_MANIFEST = b'{"version": "1", "bank": {"reflect_mission": "m", "retain_extraction_mode": "verbose"}}'


class _StubSource:
    def __init__(self, url: str, auth_token: str | None = None):
        self.url = url
        self.auth_token = auth_token
        self.name = "stub"
        self.scope = "server"
        self.owner = None


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


async def test_fetch_and_resolve_inline_entry_single_http_call():
    source = _StubSource("https://example.com/hub")
    with patch(
        "hindclaw_ext.marketplace.db.get_template_source",
        new=AsyncMock(return_value=source),
    ):
        with patch(
            "hindclaw_ext.marketplace._fetch_raw",
            new=AsyncMock(return_value=(INLINE_CATALOG, "etag-inline")),
        ) as fetch_mock:
            entry, manifest, revision = await fetch_and_resolve_template(
                source_name="stub",
                source_scope=TemplateScope.SERVER,
                source_owner=None,
                template_id="conversation",
            )

    assert entry.id == "conversation"
    assert manifest.bank.reflect_mission == "m"
    assert revision == "etag-inline"
    assert fetch_mock.await_count == 1


async def test_fetch_and_resolve_reference_entry_composite_revision():
    source = _StubSource("https://example.com/hub")

    async def _cached(url, token, session=None):
        if url.endswith("templates.json"):
            return REFERENCE_CATALOG, "etag-catalog"
        return REFERENCED_MANIFEST, "etag-manifest"

    with patch(
        "hindclaw_ext.marketplace.db.get_template_source",
        new=AsyncMock(return_value=source),
    ):
        with patch("hindclaw_ext.marketplace._fetch_raw", side_effect=_cached):
            entry, manifest, revision = await fetch_and_resolve_template(
                source_name="stub",
                source_scope=TemplateScope.SERVER,
                source_owner=None,
                template_id="backend-python",
            )

    assert entry.id == "backend-python"
    assert entry.manifest_file == "templates/backend-python.json"
    assert manifest.bank.retain_extraction_mode == "verbose"
    assert revision == "etag-catalog|etag-manifest"


async def test_fetch_and_resolve_unknown_template_id_raises():
    source = _StubSource("https://example.com/hub")
    with patch(
        "hindclaw_ext.marketplace.db.get_template_source",
        new=AsyncMock(return_value=source),
    ):
        with patch(
            "hindclaw_ext.marketplace._fetch_raw",
            new=AsyncMock(return_value=(INLINE_CATALOG, "etag")),
        ):
            with pytest.raises(ValueError) as exc:
                await fetch_and_resolve_template(
                    source_name="stub",
                    source_scope=TemplateScope.SERVER,
                    source_owner=None,
                    template_id="missing",
                )
    assert "missing" in str(exc.value)


async def test_fetch_and_resolve_unknown_source_raises():
    with patch(
        "hindclaw_ext.marketplace.db.get_template_source",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(ValueError) as exc:
            await fetch_and_resolve_template(
                source_name="stub",
                source_scope=TemplateScope.SERVER,
                source_owner=None,
                template_id="x",
            )
    assert "Unknown template source" in str(exc.value)


async def test_fetch_and_resolve_invalid_manifest_raises():
    bad_catalog = (
        b'{"catalog_version": "1", "templates": [{"id": "x", "name": "X", '
        b'"manifest": {"version": "1", "mental_models": [{"id": "dup", "name": "A", "source_query": "q"},'
        b' {"id": "dup", "name": "B", "source_query": "q"}]}}]}'
    )
    source = _StubSource("https://example.com/hub")
    with patch(
        "hindclaw_ext.marketplace.db.get_template_source",
        new=AsyncMock(return_value=source),
    ):
        with patch(
            "hindclaw_ext.marketplace._fetch_raw",
            new=AsyncMock(return_value=(bad_catalog, "etag")),
        ):
            with pytest.raises(ValueError):
                await fetch_and_resolve_template(
                    source_name="stub",
                    source_scope=TemplateScope.SERVER,
                    source_owner=None,
                    template_id="x",
                )
