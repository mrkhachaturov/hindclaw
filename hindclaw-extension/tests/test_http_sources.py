"""Tests for marketplace source admin and search endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.marketplace import MarketplaceIndex
from hindclaw_ext.models import TemplateSourceRecord


TEST_SECRET = "test-secret-key-for-http-tests!!"
_AUTH_HEADER = {"Authorization": "Bearer test-admin-key"}


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", TEST_SECRET)


@pytest.fixture
def _auth_bypass():
    patcher = patch(
        "hindclaw_ext.http.require_admin_for_action",
        new_callable=AsyncMock,
        return_value={"principal_type": "user", "user_id": "test-admin"},
    )
    patcher.start()
    yield
    patcher.stop()


@pytest.fixture
def app(_auth_bypass):
    a = FastAPI()
    ext = HindclawHttp({})
    memory = AsyncMock()
    router = ext.get_router(memory)
    a.include_router(router, prefix="/ext")
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


def _make_source(**overrides) -> TemplateSourceRecord:
    defaults = dict(
        name="hindclaw",
        url="https://github.com/hindclaw/community-templates",
        auth_token=None,
        created_at="2026-03-25T12:00:00+00:00",
    )
    defaults.update(overrides)
    return TemplateSourceRecord(**defaults)


# --- Source Admin Endpoints ---


class TestCreateSource:
    def test_create_success(self, client):
        source = _make_source()
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template_source = AsyncMock(return_value=source)
            resp = client.post(
                "/ext/hindclaw/admin/template-sources",
                json={"url": "https://github.com/hindclaw/community-templates"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "hindclaw"
        assert body["url"] == "https://github.com/hindclaw/community-templates"
        assert body["has_auth"] is False

    def test_create_with_alias(self, client):
        source = _make_source(name="engineering")
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template_source = AsyncMock(return_value=source)
            resp = client.post(
                "/ext/hindclaw/admin/template-sources",
                json={
                    "url": "https://gitlab.internal/engineering/templates",
                    "alias": "engineering",
                },
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "engineering"

    def test_create_with_auth_token(self, client):
        source = _make_source(auth_token="ghp_abc123")
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template_source = AsyncMock(return_value=source)
            resp = client.post(
                "/ext/hindclaw/admin/template-sources",
                json={
                    "url": "https://github.com/astrateam/private-templates",
                    "auth_token": "ghp_abc123",
                },
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 201
        assert resp.json()["has_auth"] is True

    def test_create_duplicate(self, client):
        import asyncpg
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template_source = AsyncMock(
                side_effect=asyncpg.UniqueViolationError("duplicate"),
            )
            resp = client.post(
                "/ext/hindclaw/admin/template-sources",
                json={"url": "https://github.com/hindclaw/community-templates"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_create_empty_url_rejected(self, client):
        resp = client.post(
            "/ext/hindclaw/admin/template-sources",
            json={"url": ""},
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 422

    def test_create_bare_host_url_rejected(self, client):
        resp = client.post(
            "/ext/hindclaw/admin/template-sources",
            json={"url": "https://example.com/"},
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 422
        assert "cannot derive source name" in resp.json()["detail"].lower()


class TestListSources:
    def test_list_empty(self, client):
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.list_template_sources = AsyncMock(return_value=[])
            resp = client.get(
                "/ext/hindclaw/admin/template-sources",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_sources(self, client):
        sources = [
            _make_source(),
            _make_source(name="astrateam", url="https://github.com/astrateam/templates"),
        ]
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.list_template_sources = AsyncMock(return_value=sources)
            resp = client.get(
                "/ext/hindclaw/admin/template-sources",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.json()[0]["name"] == "hindclaw"


class TestDeleteSource:
    def test_delete_success(self, client):
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.delete_template_source = AsyncMock(return_value=True)
            resp = client.delete(
                "/ext/hindclaw/admin/template-sources/hindclaw",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 204

    def test_delete_not_found(self, client):
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.delete_template_source = AsyncMock(return_value=False)
            resp = client.delete(
                "/ext/hindclaw/admin/template-sources/nonexistent",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 404


# --- Marketplace Search ---


class TestMarketplaceSearch:
    def test_search_returns_results(self, client):
        sources = [_make_source()]
        index = MarketplaceIndex(templates=[
            {
                "name": "backend-python",
                "version": "2.1.0",
                "description": "Backend patterns for Python",
                "author": "community",
                "tags": ["python", "backend"],
            },
        ])

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.list_template_sources = AsyncMock(return_value=sources)
            mock_db.list_templates = AsyncMock(return_value=[])
            mock_mkt.fetch_index = AsyncMock(return_value=index)
            from hindclaw_ext.http_models import MarketplaceSearchResult as MSR
            mock_mkt.search_marketplace = MagicMock(return_value=[
                MSR(
                    source="hindclaw",
                    source_scope="server",
                    name="backend-python",
                    version="2.1.0",
                    description="Backend patterns for Python",
                    author="community",
                    tags=["python", "backend"],
                ),
            ])

            resp = client.get(
                "/ext/hindclaw/marketplace/search?q=python",
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["results"][0]["name"] == "backend-python"
        assert body["results"][0]["source"] == "hindclaw"

    def test_search_filter_by_source(self, client):
        sources = [
            _make_source(),
            _make_source(name="astrateam", url="https://github.com/astrateam/templates"),
        ]

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.list_template_sources = AsyncMock(return_value=sources)
            mock_db.list_templates = AsyncMock(return_value=[])
            mock_mkt.fetch_index = AsyncMock(return_value=None)
            mock_mkt.search_marketplace = MagicMock(return_value=[])

            resp = client.get(
                "/ext/hindclaw/marketplace/search?source=hindclaw",
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        # Only the matching source should be queried
        fetch_calls = mock_mkt.fetch_index.call_args_list
        assert len(fetch_calls) == 1
        assert fetch_calls[0][0][0].name == "hindclaw"

    def test_search_marks_installed(self, client):
        sources = [_make_source()]
        index = MarketplaceIndex(templates=[
            {
                "name": "backend-python",
                "version": "2.1.0",
                "description": "Backend patterns",
                "author": "community",
                "tags": ["python"],
            },
        ])

        from hindclaw_ext.http_models import MarketplaceSearchResult

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.list_template_sources = AsyncMock(return_value=sources)
            mock_db.list_templates = AsyncMock(return_value=[])
            mock_mkt.fetch_index = AsyncMock(return_value=index)
            mock_mkt.search_marketplace = MagicMock(return_value=[
                MarketplaceSearchResult(
                    source="hindclaw",
                    source_scope="server",
                    name="backend-python",
                    version="2.1.0",
                    description="Backend patterns",
                    author="community",
                    tags=["python"],
                    installed_in=["server"],
                ),
            ])

            resp = client.get(
                "/ext/hindclaw/marketplace/search?q=python",
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        result = resp.json()["results"][0]
        assert result["installed_in"] == ["server"]
        assert result["source_scope"] == "server"

    def test_search_no_sources_returns_empty(self, client):
        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace"),
        ):
            mock_db.list_template_sources = AsyncMock(return_value=[])
            resp = client.get(
                "/ext/hindclaw/marketplace/search?q=python",
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["results"] == []
