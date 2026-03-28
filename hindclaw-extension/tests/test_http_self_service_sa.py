"""Tests for self-service SA endpoints at /me/service-accounts."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindsight_api.extensions import AuthenticationError
from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import ServiceAccountRecord, ServiceAccountKeyRecord


# --- Fixtures ---
# NOTE: require_admin_for_action is resolved by name at call time (not
# definition time) inside _require_iam closures.  The patch MUST stay
# active for the lifetime of the test — hence yield inside the with block,
# matching the pattern in test_http.py:47-54.


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-for-self-service!!")


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
def bob_app():
    """Test app where _require_iam resolves to bob."""
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
        return_value={"principal_type": "user", "user_id": "bob"},
    ):
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        yield app


@pytest.fixture
def bob_client(bob_app):
    return TestClient(bob_app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer fake-token"}


@pytest.fixture
def mock_db():
    with patch("hindclaw_ext.http.db") as mock:
        mock.get_pool = AsyncMock()
        yield mock


ALICE_SA = ServiceAccountRecord(
    id="alice-sa", owner_user_id="alice",
    display_name="Alice SA", is_active=True, scoping_policy_id=None,
)

BOB_SA = ServiceAccountRecord(
    id="bob-sa", owner_user_id="bob",
    display_name="Bob SA", is_active=True, scoping_policy_id="policy-1",
)


# --- List ---


def test_list_my_service_accounts(alice_client, headers, mock_db):
    """GET /me/service-accounts lists only caller's SAs."""
    mock_db.list_service_accounts_by_owner = AsyncMock(return_value=[ALICE_SA])
    resp = alice_client.get("/ext/hindclaw/me/service-accounts", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == "alice-sa"
    mock_db.list_service_accounts_by_owner.assert_called_once_with("alice")


# --- Create ---


def test_create_my_service_account(alice_client, headers, mock_db):
    """POST /me/service-accounts creates SA owned by caller."""
    mock_db.create_service_account = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/service-accounts",
        json={"id": "new-sa", "display_name": "New SA"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "new-sa"
    assert body["owner_user_id"] == "alice"
    mock_db.create_service_account.assert_called_once_with(
        "new-sa", "alice", "New SA", None,
    )


def test_create_my_service_account_rejects_owner_user_id(alice_client, headers, mock_db):
    """POST /me/service-accounts rejects owner_user_id with 422."""
    resp = alice_client.post(
        "/ext/hindclaw/me/service-accounts",
        json={"id": "sa", "display_name": "SA", "owner_user_id": "bob"},
        headers=headers,
    )
    # extra="forbid" on CreateSelfServiceAccountRequest — Pydantic rejects unknown fields
    assert resp.status_code == 422


def test_create_my_service_account_with_scoping_policy(alice_client, headers, mock_db):
    """POST /me/service-accounts passes scoping_policy_id through."""
    mock_db.create_service_account = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/service-accounts",
        json={"id": "scoped-sa", "display_name": "Scoped", "scoping_policy_id": "readonly"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["scoping_policy_id"] == "readonly"
    mock_db.create_service_account.assert_called_once_with(
        "scoped-sa", "alice", "Scoped", "readonly",
    )


# --- Get ---


def test_get_my_service_account_owned(alice_client, headers, mock_db):
    """GET /me/service-accounts/{id} returns SA if owned by caller."""
    mock_db.get_service_account = AsyncMock(return_value=ALICE_SA)
    resp = alice_client.get("/ext/hindclaw/me/service-accounts/alice-sa", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == "alice-sa"


def test_get_my_service_account_not_owned_returns_404(alice_client, headers, mock_db):
    """GET /me/service-accounts/{id} returns 404 if not owned by caller."""
    mock_db.get_service_account = AsyncMock(return_value=BOB_SA)
    resp = alice_client.get("/ext/hindclaw/me/service-accounts/bob-sa", headers=headers)
    assert resp.status_code == 404


def test_get_my_service_account_nonexistent_returns_404(alice_client, headers, mock_db):
    """GET /me/service-accounts/{id} returns 404 for nonexistent SA."""
    mock_db.get_service_account = AsyncMock(return_value=None)
    resp = alice_client.get("/ext/hindclaw/me/service-accounts/nope", headers=headers)
    assert resp.status_code == 404


# --- Update ---


def test_update_my_service_account_display_name(alice_client, headers, mock_db):
    """PUT /me/service-accounts/{id} updates display_name only."""
    updated_sa = ServiceAccountRecord(
        id="alice-sa", owner_user_id="alice",
        display_name="Renamed", is_active=True, scoping_policy_id=None,
    )
    mock_db.get_service_account = AsyncMock(side_effect=[ALICE_SA, updated_sa])
    mock_db.update_service_account = AsyncMock(return_value=True)
    resp = alice_client.put(
        "/ext/hindclaw/me/service-accounts/alice-sa",
        json={"display_name": "Renamed"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Renamed"
    mock_db.update_service_account.assert_called_once_with("alice-sa", display_name="Renamed")


def test_update_my_service_account_not_owned_returns_404(alice_client, headers, mock_db):
    """PUT /me/service-accounts/{id} returns 404 for SA not owned."""
    mock_db.get_service_account = AsyncMock(return_value=BOB_SA)
    resp = alice_client.put(
        "/ext/hindclaw/me/service-accounts/bob-sa",
        json={"display_name": "Hack"},
        headers=headers,
    )
    assert resp.status_code == 404
    mock_db.update_service_account.assert_not_called()


def test_update_my_service_account_rejects_scoping_policy(alice_client, headers, mock_db):
    """PUT /me/service-accounts/{id} rejects scoping_policy_id with 422."""
    resp = alice_client.put(
        "/ext/hindclaw/me/service-accounts/alice-sa",
        json={"display_name": "OK", "scoping_policy_id": "escalation-attempt"},
        headers=headers,
    )
    assert resp.status_code == 422


# --- Delete ---


def test_delete_my_service_account(alice_client, headers, mock_db):
    """DELETE /me/service-accounts/{id} deletes owned SA."""
    mock_db.get_service_account = AsyncMock(return_value=ALICE_SA)
    mock_db.delete_service_account = AsyncMock()
    resp = alice_client.delete("/ext/hindclaw/me/service-accounts/alice-sa", headers=headers)
    assert resp.status_code == 204
    mock_db.delete_service_account.assert_called_once_with("alice-sa")


def test_delete_my_service_account_not_owned_returns_404(alice_client, headers, mock_db):
    """DELETE /me/service-accounts/{id} returns 404 for SA not owned."""
    mock_db.get_service_account = AsyncMock(return_value=BOB_SA)
    mock_db.delete_service_account = AsyncMock()
    resp = alice_client.delete("/ext/hindclaw/me/service-accounts/bob-sa", headers=headers)
    assert resp.status_code == 404
    mock_db.delete_service_account.assert_not_called()


# --- Keys ---


def test_list_my_sa_keys(alice_client, headers, mock_db):
    """GET /me/service-accounts/{id}/keys lists keys for owned SA."""
    mock_db.get_service_account = AsyncMock(return_value=ALICE_SA)
    mock_db.list_sa_keys = AsyncMock(return_value=[
        ServiceAccountKeyRecord(id="k1", service_account_id="alice-sa", api_key="hc_sa_alice-sa_abc123def456", description="CI"),
    ])
    resp = alice_client.get("/ext/hindclaw/me/service-accounts/alice-sa/keys", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == "k1"


def test_list_my_sa_keys_not_owned_returns_404(alice_client, headers, mock_db):
    """GET /me/service-accounts/{id}/keys returns 404 for unowned SA."""
    mock_db.get_service_account = AsyncMock(return_value=BOB_SA)
    resp = alice_client.get("/ext/hindclaw/me/service-accounts/bob-sa/keys", headers=headers)
    assert resp.status_code == 404


def test_create_my_sa_key(alice_client, headers, mock_db):
    """POST /me/service-accounts/{id}/keys creates key for owned SA."""
    mock_db.get_service_account = AsyncMock(return_value=ALICE_SA)
    mock_db.create_sa_key = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/service-accounts/alice-sa/keys",
        json={"description": "CI key"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["api_key"].startswith("hc_sa_alice-sa_")
    mock_db.create_sa_key.assert_called_once()


def test_create_my_sa_key_not_owned_returns_404(alice_client, headers, mock_db):
    """POST /me/service-accounts/{id}/keys returns 404 for unowned SA."""
    mock_db.get_service_account = AsyncMock(return_value=BOB_SA)
    mock_db.create_sa_key = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/service-accounts/bob-sa/keys",
        json={"description": "nope"},
        headers=headers,
    )
    assert resp.status_code == 404
    mock_db.create_sa_key.assert_not_called()


def test_delete_my_sa_key(alice_client, headers, mock_db):
    """DELETE /me/service-accounts/{id}/keys/{kid} deletes key for owned SA."""
    mock_db.get_service_account = AsyncMock(return_value=ALICE_SA)
    mock_db.get_sa_key = AsyncMock(return_value=ServiceAccountKeyRecord(
        id="k1", service_account_id="alice-sa", api_key="hc_sa_alice-sa_x", description=None,
    ))
    mock_db.delete_sa_key = AsyncMock()
    resp = alice_client.delete("/ext/hindclaw/me/service-accounts/alice-sa/keys/k1", headers=headers)
    assert resp.status_code == 204
    mock_db.delete_sa_key.assert_called_once_with("k1", "alice-sa")


def test_delete_my_sa_key_not_owned_returns_404(alice_client, headers, mock_db):
    """DELETE /me/service-accounts/{id}/keys/{kid} returns 404 for unowned SA."""
    mock_db.get_service_account = AsyncMock(return_value=BOB_SA)
    mock_db.delete_sa_key = AsyncMock()
    resp = alice_client.delete("/ext/hindclaw/me/service-accounts/bob-sa/keys/k1", headers=headers)
    assert resp.status_code == 404
    mock_db.delete_sa_key.assert_not_called()


# --- Admin surface permission tests ---


def test_admin_list_uses_manage_action(headers):
    """GET /service-accounts requires iam:service_accounts:manage."""
    captured_actions = []
    original_require = AsyncMock(return_value={"principal_type": "user", "user_id": "admin"})

    async def capturing_require(action, credentials=None):
        captured_actions.append(action)
        return await original_require(action, credentials)

    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    ext = HindclawHttp({})
    memory = AsyncMock()

    # Patch must stay active for the request — keep client.get inside the block
    with patch("hindclaw_ext.http.require_admin_for_action", side_effect=capturing_require):
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        client = TestClient(app)
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.list_service_accounts = AsyncMock(return_value=[])
            client.get("/ext/hindclaw/service-accounts", headers=headers)

    assert "iam:service_accounts:manage" in captured_actions


# --- SA-as-caller ---


def test_sa_caller_sees_owner_sas(headers, mock_db):
    """SA caller resolves to owner — sees owner's SAs via /me/."""
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
        return_value={"principal_type": "service_account", "user_id": "alice", "sa_id": "alice-sa"},
    ):
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        client = TestClient(app)
        mock_db.list_service_accounts_by_owner = AsyncMock(return_value=[ALICE_SA])
        resp = client.get("/ext/hindclaw/me/service-accounts", headers=headers)
    assert resp.status_code == 200
    mock_db.list_service_accounts_by_owner.assert_called_once_with("alice")
