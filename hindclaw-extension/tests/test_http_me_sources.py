"""Tests for self-service template source endpoints at /me/template-sources."""
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindsight_api.extensions import AuthenticationError
from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import TemplateSourceRecord


# --- Fixtures ---
# NOTE: require_admin_for_action is resolved by name at call time (not
# definition time) inside _require_iam closures.  The patch MUST stay
# active for the lifetime of the test — hence yield inside the with block,
# matching the pattern in test_http_self_service_sa.py.


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-for-me-sources!!")


@pytest.fixture
def alice_app():
    """Test app where _require_iam resolves to alice."""
    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    ext = HindclawHttp({})
    memory = AsyncMock()

    with patch(
        "hindclaw_ext.http.require_admin_for_action",
        new_callable=AsyncMock,
        return_value={"principal_type": "user", "user_id": "alice"},
    ):
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        yield app


@pytest.fixture
def alice_client(alice_app):
    return TestClient(alice_app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer fake-token"}


@pytest.fixture
def mock_db():
    with patch("hindclaw_ext.http.db") as mock:
        mock.get_pool = AsyncMock()
        yield mock


def _make_source(**overrides) -> TemplateSourceRecord:
    """Build a TemplateSourceRecord with personal-scope defaults."""
    defaults = dict(
        name="my-templates",
        url="https://github.com/alice/my-templates",
        scope="personal",
        owner="alice",
        auth_token=None,
        created_at="2026-03-29T10:00:00+00:00",
    )
    defaults.update(overrides)
    return TemplateSourceRecord(**defaults)


# --- List ---


def test_list_my_template_sources(alice_client, headers, mock_db):
    """GET /me/template-sources returns sources for the caller."""
    source = _make_source()
    mock_db.list_template_sources = AsyncMock(return_value=[source])

    resp = alice_client.get("/ext/hindclaw/me/template-sources", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "my-templates"
    assert body[0]["url"] == "https://github.com/alice/my-templates"
    assert body[0]["has_auth"] is False
    mock_db.list_template_sources.assert_called_once_with(scope="personal", owner="alice")


def test_list_my_template_sources_empty(alice_client, headers, mock_db):
    """GET /me/template-sources returns empty list when no sources exist."""
    mock_db.list_template_sources = AsyncMock(return_value=[])

    resp = alice_client.get("/ext/hindclaw/me/template-sources", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == []
    mock_db.list_template_sources.assert_called_once_with(scope="personal", owner="alice")


# --- Create ---


def test_create_my_template_source(alice_client, headers, mock_db):
    """POST /me/template-sources creates a personal source with derived name.

    derive_source_name extracts the first path segment (org/user), so
    'https://github.com/alice/my-templates' → name='alice'.
    """
    source = _make_source(name="alice")
    mock_db.create_template_source = AsyncMock(return_value=source)

    resp = alice_client.post(
        "/ext/hindclaw/me/template-sources",
        json={"url": "https://github.com/alice/my-templates"},
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "alice"
    assert body["url"] == "https://github.com/alice/my-templates"
    assert body["has_auth"] is False
    mock_db.create_template_source.assert_called_once_with(
        name="alice",
        url="https://github.com/alice/my-templates",
        scope="personal",
        owner="alice",
        auth_token=None,
    )


def test_create_my_template_source_with_alias(alice_client, headers, mock_db):
    """POST /me/template-sources uses alias instead of derived name when provided."""
    source = _make_source(name="private")
    mock_db.create_template_source = AsyncMock(return_value=source)

    resp = alice_client.post(
        "/ext/hindclaw/me/template-sources",
        json={"url": "https://github.com/alice/my-templates", "alias": "private"},
        headers=headers,
    )

    assert resp.status_code == 201
    assert resp.json()["name"] == "private"
    mock_db.create_template_source.assert_called_once_with(
        name="private",
        url="https://github.com/alice/my-templates",
        scope="personal",
        owner="alice",
        auth_token=None,
    )


def test_create_my_template_source_duplicate(alice_client, headers, mock_db):
    """POST /me/template-sources returns 409 when source name already exists."""
    mock_db.create_template_source = AsyncMock(
        side_effect=asyncpg.UniqueViolationError("duplicate"),
    )

    resp = alice_client.post(
        "/ext/hindclaw/me/template-sources",
        json={"url": "https://github.com/alice/my-templates"},
        headers=headers,
    )

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()
    assert "personal sources" in resp.json()["detail"].lower()


# --- Delete ---


def test_delete_my_template_source(alice_client, headers, mock_db):
    """DELETE /me/template-sources/{name} deletes caller's personal source."""
    mock_db.delete_template_source = AsyncMock(return_value=True)

    resp = alice_client.delete("/ext/hindclaw/me/template-sources/my-templates", headers=headers)

    assert resp.status_code == 204
    mock_db.delete_template_source.assert_called_once_with(
        "my-templates", scope="personal", owner="alice",
    )


def test_delete_my_template_source_not_found(alice_client, headers, mock_db):
    """DELETE /me/template-sources/{name} returns 404 when source not found."""
    mock_db.delete_template_source = AsyncMock(return_value=False)

    resp = alice_client.delete("/ext/hindclaw/me/template-sources/nonexistent", headers=headers)

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
    assert "personal sources" in resp.json()["detail"].lower()
