"""Tests for self-service /me/api-keys endpoints."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindsight_api.extensions import AuthenticationError
from hindclaw_ext.http import HindclawHttp


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-for-api-keys!!")


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


@pytest.fixture
def sa_test_app():
    """App WITHOUT patched auth — actual auth code runs to test SA rejection."""
    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    ext = HindclawHttp({})
    memory = AsyncMock()
    router = ext.get_router(memory)
    app.include_router(router, prefix="/ext")
    return app


@pytest.fixture
def sa_client(sa_test_app):
    return TestClient(sa_test_app, raise_server_exceptions=False)


# --- List ---


def test_list_my_api_keys(alice_client, headers, mock_db):
    """GET /me/api-keys returns masked keys for the caller."""
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    pool.fetch = AsyncMock(return_value=[
        {"id": "k1", "api_key": "hc_u_alice_abcdef123456xyz0", "description": "CI"},
    ])
    resp = alice_client.get("/ext/hindclaw/me/api-keys", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == "k1"
    assert body[0]["api_key_prefix"] == "hc_u_alice_a..."
    assert body[0]["description"] == "CI"


def test_list_my_api_keys_only_own_keys(alice_client, headers, mock_db):
    """GET /me/api-keys filters by caller's user_id."""
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    pool.fetch = AsyncMock(return_value=[])
    resp = alice_client.get("/ext/hindclaw/me/api-keys", headers=headers)
    assert resp.status_code == 200
    pool.fetch.assert_called_once()
    call_args = pool.fetch.call_args
    # user_id "alice" must appear as positional argument to parameterised query
    assert "alice" in call_args.args


# --- Create ---


def test_create_my_api_key(alice_client, headers, mock_db):
    """POST /me/api-keys returns 201 with full api_key."""
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    pool.execute = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/api-keys",
        headers=headers,
        json={"description": "test key"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "api_key" in body
    assert body["api_key"].startswith("hc_u_alice_")
    assert body["description"] == "test key"
    assert "id" in body
    pool.execute.assert_called_once()


def test_create_my_api_key_no_description(alice_client, headers, mock_db):
    """POST /me/api-keys accepts empty body (description optional)."""
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    pool.execute = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/api-keys",
        headers=headers,
        json={},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] is None


# --- Delete ---


def test_delete_my_api_key(alice_client, headers, mock_db):
    """DELETE /me/api-keys/{key_id} returns 204."""
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    pool.execute = AsyncMock()
    resp = alice_client.delete("/ext/hindclaw/me/api-keys/k1", headers=headers)
    assert resp.status_code == 204
    pool.execute.assert_called_once()
    call_args = pool.execute.call_args
    # Both key_id "k1" and user_id "alice" must appear in the SQL call
    assert "k1" in call_args.args
    assert "alice" in call_args.args


# --- SA Credential Rejection ---


def test_me_api_keys_rejects_sa_credentials(sa_client):
    """POST /me/api-keys rejects SA token with 403."""
    resp = sa_client.post(
        "/ext/hindclaw/me/api-keys",
        headers={"Authorization": "Bearer hc_sa_test-sa_abc123"},
        json={"description": "test"},
    )
    assert resp.status_code == 403
    assert "Service account" in resp.json()["detail"]


def test_list_my_api_keys_rejects_sa_credentials(sa_client):
    """GET /me/api-keys rejects SA token with 403."""
    resp = sa_client.get(
        "/ext/hindclaw/me/api-keys",
        headers={"Authorization": "Bearer hc_sa_test-sa_abc123"},
    )
    assert resp.status_code == 403
    assert "Service account" in resp.json()["detail"]


def test_delete_my_api_key_rejects_sa_credentials(sa_client):
    """DELETE /me/api-keys/{id} rejects SA token with 403."""
    resp = sa_client.delete(
        "/ext/hindclaw/me/api-keys/some-key",
        headers={"Authorization": "Bearer hc_sa_test-sa_abc123"},
    )
    assert resp.status_code == 403
    assert "Service account" in resp.json()["detail"]
