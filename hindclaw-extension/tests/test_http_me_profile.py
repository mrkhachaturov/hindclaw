"""Tests for GET /me profile endpoint."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindsight_api.extensions import AuthenticationError
from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import UserRecord


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-for-profile!!")


@pytest.fixture
def alice_app():
    """Test app where GET /me resolves to alice.

    _authenticate_user is used via Depends() which captures the function
    object at route-definition time.  Patching with AsyncMock confuses
    FastAPI's dependency introspection.  Instead we patch with a proper
    async function that carries the right signature (HTTPBearer credentials).
    """
    from fastapi.security import HTTPAuthorizationCredentials

    async def _fake_authenticate_user(
        credentials: HTTPAuthorizationCredentials = None,
    ) -> dict:
        return {"principal_type": "user", "user_id": "alice"}

    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    ext = HindclawHttp({})
    memory = AsyncMock()

    with patch("hindclaw_ext.http._authenticate_user", new=_fake_authenticate_user):
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


ALICE_USER = UserRecord(
    id="alice",
    display_name="Alice",
    email="alice@example.com",
    is_active=True,
)


# --- Profile ---


def test_get_me_profile(alice_client, headers, mock_db):
    """GET /me returns user record with channels."""
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    mock_db.get_user = AsyncMock(return_value=ALICE_USER)
    pool.fetch = AsyncMock(return_value=[
        {"provider": "telegram", "sender_id": "123456"},
    ])
    resp = alice_client.get("/ext/hindclaw/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "alice"
    assert body["display_name"] == "Alice"
    assert body["email"] == "alice@example.com"
    assert body["is_active"] is True
    assert len(body["channels"]) == 1
    assert body["channels"][0]["provider"] == "telegram"
    assert body["channels"][0]["sender_id"] == "123456"
    mock_db.get_user.assert_called_once_with("alice")


def test_get_me_profile_no_channels(alice_client, headers, mock_db):
    """GET /me returns empty channels list when user has no channels."""
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    mock_db.get_user = AsyncMock(return_value=ALICE_USER)
    pool.fetch = AsyncMock(return_value=[])
    resp = alice_client.get("/ext/hindclaw/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["channels"] == []


def test_get_me_profile_no_email(alice_client, headers, mock_db):
    """GET /me returns null email when user has no email."""
    user_no_email = UserRecord(id="alice", display_name="Alice", email=None, is_active=True)
    pool = AsyncMock()
    mock_db.get_pool = AsyncMock(return_value=pool)
    mock_db.get_user = AsyncMock(return_value=user_no_email)
    pool.fetch = AsyncMock(return_value=[])
    resp = alice_client.get("/ext/hindclaw/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] is None


# --- SA Credential Rejection ---


def test_get_me_rejects_sa_credentials(sa_client):
    """GET /me rejects SA token with 403."""
    resp = sa_client.get(
        "/ext/hindclaw/me",
        headers={"Authorization": "Bearer hc_sa_test-sa_abc123"},
    )
    assert resp.status_code == 403
    assert "Service account" in resp.json()["detail"]


def test_get_me_rejects_invalid_api_key(sa_client):
    """GET /me rejects an unknown user API key with 401."""
    with patch("hindclaw_ext.http.db") as mock_db:
        mock_db.get_api_key = AsyncMock(return_value=None)
        resp = sa_client.get(
            "/ext/hindclaw/me",
            headers={"Authorization": "Bearer hc_u_nonexistent_abc123"},
        )
    assert resp.status_code == 401
