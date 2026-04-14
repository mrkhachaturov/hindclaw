"""Tests for hindclaw_ext.http — HindclawHttp extension."""

import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hindsight_api.extensions import AuthenticationError

from hindclaw_ext.http import HindclawHttp

TEST_SECRET = "test-secret-key-for-http-tests!!"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Ensure tests use test env vars, not any real values on this host."""
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", TEST_SECRET)


def _make_admin_jwt(client_id: str = "app-prod") -> str:
    """Create a signed admin JWT for test requests."""
    return pyjwt.encode(
        {"client_id": client_id, "exp": int(time.time()) + 300},
        TEST_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def app():
    """Create test app with HindclawHttp router, auth overridden to pass."""
    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=401, content={"detail": str(exc)})

    ext = HindclawHttp({})
    memory = AsyncMock()

    # Patch require_admin_for_action so all _require_iam closures short-circuit.
    # CRUD tests test endpoint logic, not auth — auth is tested separately.
    with patch(
        "hindclaw_ext.http.require_admin_for_action",
        new_callable=AsyncMock,
        return_value={"principal_type": "user", "user_id": "test-admin"},
    ):
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        yield app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {_make_admin_jwt()}"}


@pytest.fixture
def mock_db_pool():
    """Patch hindclaw_ext.http.db and yield (mock_db, pool).

    Provides a mock pool with all common methods (execute, fetch, fetchrow,
    fetchval). Tests configure return values on the yielded pool.
    """
    with patch("hindclaw_ext.http.db") as mock_db:
        pool = AsyncMock()
        mock_db.get_pool = AsyncMock(return_value=pool)
        yield mock_db, pool


@pytest.fixture
def mock_db_pool_with_tx():
    """Patch hindclaw_ext.http.db and yield (mock_db, pool, conn).

    Like mock_db_pool but also mocks pool.acquire() -> conn with transaction
    support. Used by tests for delete_user/delete_group cascade.
    """
    with patch("hindclaw_ext.http.db") as mock_db:
        pool = AsyncMock()
        mock_db.get_pool = AsyncMock(return_value=pool)

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=AsyncMock())

        @asynccontextmanager
        async def fake_acquire():
            yield conn

        pool.acquire = fake_acquire

        yield mock_db, pool, conn


@pytest.fixture
def real_auth_app():
    """Test app with real IAM auth (not overridden) for auth-specific tests."""
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
def real_auth_client(real_auth_app):
    return TestClient(real_auth_app)


def test_no_auth_returns_401(real_auth_client):
    """Missing Authorization header returns 403 (HTTPBearer rejects)."""
    resp = real_auth_client.get("/ext/hindclaw/users")
    assert resp.status_code in (401, 403)


def test_bad_api_key_returns_401(real_auth_client):
    """Invalid API key returns 401."""
    with patch("hindclaw_ext.http.db.get_api_key", return_value=None):
        resp = real_auth_client.get(
            "/ext/hindclaw/users",
            headers={"Authorization": "Bearer hc_u_bad_key"},
        )
    assert resp.status_code == 401


def test_create_user(client, admin_headers, mock_db_pool):
    """POST /ext/hindclaw/users creates a user."""
    _, pool = mock_db_pool
    resp = client.post(
        "/ext/hindclaw/users",
        json={"id": "alice", "display_name": "Alice", "email": "alice@example.com"},
        headers=admin_headers,
    )
    assert resp.status_code == 201


def test_list_users(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/users returns user list."""
    _, pool = mock_db_pool
    pool.fetch = AsyncMock(
        return_value=[
            {
                "id": "alice",
                "display_name": "Alice",
                "email": "alice@example.com",
                "is_active": True,
            },
        ]
    )

    resp = client.get("/ext/hindclaw/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "alice"


def test_delete_user(client, admin_headers, mock_db_pool):
    """DELETE /ext/hindclaw/users/:id deletes user (FK CASCADE handles related rows)."""
    _, pool = mock_db_pool
    pool.fetchval = AsyncMock(return_value="alice")  # user exists

    resp = client.delete("/ext/hindclaw/users/alice", headers=admin_headers)
    assert resp.status_code == 204
    pool.execute.assert_called_once()


def test_get_user_not_found(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/users/:id returns 404 for unknown user."""
    _, pool = mock_db_pool
    pool.fetchrow = AsyncMock(return_value=None)

    resp = client.get("/ext/hindclaw/users/nobody", headers=admin_headers)
    assert resp.status_code == 404


def test_create_group(client, admin_headers, mock_db_pool):
    """POST /ext/hindclaw/groups creates a group."""
    _, pool = mock_db_pool
    resp = client.post(
        "/ext/hindclaw/groups",
        json={"id": "engineering", "display_name": "Engineering"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json() == {"id": "engineering", "display_name": "Engineering"}


def test_get_group(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/groups/:id returns group identity fields."""
    _, pool = mock_db_pool
    pool.fetchrow = AsyncMock(
        return_value={
            "id": "engineering",
            "display_name": "Engineering",
        }
    )

    resp = client.get("/ext/hindclaw/groups/engineering", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "engineering"
    assert data["display_name"] == "Engineering"


def test_get_group_not_found(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/groups/:id returns 404 for unknown group."""
    _, pool = mock_db_pool
    pool.fetchrow = AsyncMock(return_value=None)

    resp = client.get("/ext/hindclaw/groups/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


def test_create_api_key(client, admin_headers, mock_db_pool):
    """POST /ext/hindclaw/users/:id/api-keys generates a key."""
    _, pool = mock_db_pool
    resp = client.post(
        "/ext/hindclaw/users/alice/api-keys",
        json={"description": "Claude Code MCP"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["api_key"].startswith("hc_u_")
    assert data["description"] == "Claude Code MCP"


def test_debug_resolve_user(client, admin_headers):
    """Debug resolve returns access result for a user."""
    from hindclaw_ext.policy_engine import AccessResult

    mock_access = AccessResult(allowed=True, recall_budget="high")

    with (
        patch(
            "hindclaw_ext.validator._resolve_user_access",
            new_callable=AsyncMock,
            return_value=mock_access,
        ),
        patch(
            "hindclaw_ext.http.db.get_bank_policy",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        resp = client.get(
            "/ext/hindclaw/debug/resolve?bank=yoda&action=bank:recall&user_id=alice",
            headers=admin_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["principal_type"] == "user"
    assert data["access"]["allowed"] is True


def test_debug_resolve_bad_sender(client, admin_headers):
    """GET /ext/hindclaw/debug/resolve with malformed sender returns 400."""
    resp = client.get(
        "/ext/hindclaw/debug/resolve?bank=agent-alpha&sender=no_colon",
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_debug_resolve_no_params(client, admin_headers):
    """Debug resolve without sender/user_id/sa_id returns 400."""
    resp = client.get(
        "/ext/hindclaw/debug/resolve?bank=yoda",
        headers=admin_headers,
    )
    assert resp.status_code == 400


# --- Channel tests ---


def test_list_user_channels(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/users/:id/channels returns channel list."""
    _, pool = mock_db_pool
    pool.fetch = AsyncMock(
        return_value=[
            {"provider": "telegram", "sender_id": "100001"},
            {"provider": "slack", "sender_id": "U100001"},
        ]
    )

    resp = client.get("/ext/hindclaw/users/alice/channels", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.json()[0] == {"provider": "telegram", "sender_id": "100001"}


def test_add_user_channel(client, admin_headers, mock_db_pool):
    """POST /ext/hindclaw/users/:id/channels adds a channel mapping."""
    _, pool = mock_db_pool
    resp = client.post(
        "/ext/hindclaw/users/alice/channels",
        json={"provider": "telegram", "sender_id": "100001"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json() == {"provider": "telegram", "sender_id": "100001"}


# --- Group member tests ---


def test_add_group_member(client, admin_headers, mock_db_pool):
    """POST /ext/hindclaw/groups/:id/members adds a member."""
    _, pool = mock_db_pool
    resp = client.post(
        "/ext/hindclaw/groups/engineering/members",
        json={"user_id": "alice"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json() == {"group_id": "engineering", "user_id": "alice"}


def test_list_group_members(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/groups/:id/members returns member list."""
    _, pool = mock_db_pool
    pool.fetch = AsyncMock(return_value=[{"user_id": "alice"}, {"user_id": "bob"}])

    resp = client.get("/ext/hindclaw/groups/engineering/members", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- Error case tests ---


def test_update_user_empty_body(client, admin_headers, mock_db_pool):
    """PUT /ext/hindclaw/users/:id with empty body returns 400."""
    resp = client.put("/ext/hindclaw/users/alice", json={}, headers=admin_headers)
    assert resp.status_code == 400


# --- Happy path: GET/PUT/DELETE by ID ---


def test_get_user(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/users/:id returns user."""
    _, pool = mock_db_pool
    pool.fetchrow = AsyncMock(
        return_value={
            "id": "alice",
            "display_name": "Alice",
            "email": "alice@example.com",
            "is_active": True,
        }
    )

    resp = client.get("/ext/hindclaw/users/alice", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == "alice"


def test_update_user(client, admin_headers, mock_db_pool):
    """PUT /ext/hindclaw/users/:id updates and returns full user."""
    _, pool = mock_db_pool
    pool.execute = AsyncMock(return_value="UPDATE 1")
    pool.fetchrow = AsyncMock(
        return_value={
            "id": "alice",
            "display_name": "Alice K.",
            "email": "alice@example.com",
            "is_active": True,
        }
    )

    resp = client.put(
        "/ext/hindclaw/users/alice",
        json={"display_name": "Alice K."},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Alice K."
    assert resp.json()["email"] == "alice@example.com"


def test_update_user_not_found(client, admin_headers, mock_db_pool):
    """PUT /ext/hindclaw/users/:id returns 404 if user doesn't exist."""
    _, pool = mock_db_pool
    pool.fetchrow = AsyncMock(return_value=None)  # UPDATE RETURNING yields None

    resp = client.put(
        "/ext/hindclaw/users/nobody",
        json={"display_name": "Ghost"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_update_group(client, admin_headers, mock_db_pool):
    """PUT /ext/hindclaw/groups/:id updates display_name."""
    _, pool = mock_db_pool
    pool.fetchrow = AsyncMock(
        return_value={
            "id": "engineering",
            "display_name": "Eng Team",
        }
    )

    resp = client.put(
        "/ext/hindclaw/groups/engineering",
        json={"display_name": "Eng Team"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "engineering"
    assert resp.json()["display_name"] == "Eng Team"


def test_delete_group(client, admin_headers, mock_db_pool_with_tx):
    """DELETE /ext/hindclaw/groups/:id cascades and deletes."""
    _, pool, conn = mock_db_pool_with_tx
    pool.fetchval = AsyncMock(return_value="engineering")

    resp = client.delete("/ext/hindclaw/groups/engineering", headers=admin_headers)
    assert resp.status_code == 204


def test_remove_user_channel(client, admin_headers, mock_db_pool):
    """DELETE /ext/hindclaw/users/:id/channels/:provider/:sender_id removes channel."""
    _, pool = mock_db_pool
    resp = client.delete(
        "/ext/hindclaw/users/alice/channels/telegram/100001",
        headers=admin_headers,
    )
    assert resp.status_code == 204


def test_remove_group_member(client, admin_headers, mock_db_pool):
    """DELETE /ext/hindclaw/groups/:id/members/:user_id removes member."""
    _, pool = mock_db_pool
    resp = client.delete(
        "/ext/hindclaw/groups/engineering/members/alice",
        headers=admin_headers,
    )
    assert resp.status_code == 204


def test_list_api_keys(client, admin_headers, mock_db_pool):
    """GET /ext/hindclaw/users/:id/api-keys returns keys with masked values."""
    _, pool = mock_db_pool
    pool.fetch = AsyncMock(
        return_value=[
            {"id": "k1", "api_key": "hc_alice_xxxxxxxxxxxx", "description": "test"},
        ]
    )

    resp = client.get("/ext/hindclaw/users/alice/api-keys", headers=admin_headers)
    assert resp.status_code == 200
    assert "api_key_prefix" in resp.json()[0]
    assert resp.json()[0]["api_key_prefix"].startswith("hc_alice_")
    assert "api_key" not in resp.json()[0]  # full key not exposed in list


def test_delete_api_key(client, admin_headers, mock_db_pool):
    """DELETE /ext/hindclaw/users/:id/api-keys/:key_id deletes key."""
    _, pool = mock_db_pool
    resp = client.delete(
        "/ext/hindclaw/users/alice/api-keys/k1",
        headers=admin_headers,
    )
    assert resp.status_code == 204


def test_create_user_duplicate(client, admin_headers, mock_db_pool):
    """POST /ext/hindclaw/users with existing ID returns 409."""
    import asyncpg as _asyncpg

    _, pool = mock_db_pool
    pool.execute = AsyncMock(side_effect=_asyncpg.UniqueViolationError("duplicate"))

    resp = client.post(
        "/ext/hindclaw/users",
        json={"id": "alice", "display_name": "Alice"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
