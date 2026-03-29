"""Tests for server-scope gates on template write endpoints.

Verifies that:
- POST/PUT/DELETE /templates with scope=server require template:admin (403 when missing)
- POST /templates with scope=personal works without template:admin
- POST /templates/install with scope=server requires template:admin
- POST /templates/{scope}/{source}/{name}/update with scope=server requires template:admin
- POST/GET/DELETE /admin/template-sources require template:admin
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from hindsight_api.extensions import AuthenticationError
from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import TemplateRecord, TemplateSourceRecord
from hindclaw_ext.policy_engine import AccessResult
from hindclaw_ext.template_models import MarketplaceTemplate


_AUTH_HEADER = {"Authorization": "Bearer hc_u_test-key"}


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-scope-gates!!")


def _make_app_with_iam_access(*, iam_allowed: bool):
    """Build a TestClient where require_admin_for_action succeeds but
    _evaluate_iam_access returns the given allowed value.

    The _require_iam dependency calls require_admin_for_action (patched to
    succeed).  The scope gate calls _evaluate_iam_access directly (patched
    independently to allow or deny template:admin).
    """
    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request, exc):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    ext = HindclawHttp({})
    memory = AsyncMock()

    with patch(
        "hindclaw_ext.http.require_admin_for_action",
        new_callable=AsyncMock,
        return_value={"principal_type": "user", "user_id": "test-user"},
    ), patch(
        "hindclaw_ext.http._evaluate_iam_access",
        new_callable=AsyncMock,
        return_value=AccessResult(allowed=iam_allowed),
    ):
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        yield TestClient(app)


@pytest.fixture
def client_no_admin():
    """Client whose user has template:create but NOT template:admin."""
    yield from _make_app_with_iam_access(iam_allowed=False)


@pytest.fixture
def client_with_admin():
    """Client whose user has template:admin."""
    yield from _make_app_with_iam_access(iam_allowed=True)


def _fake_template_record(**overrides) -> TemplateRecord:
    defaults = {
        "id": "my-template",
        "scope": "server",
        "owner": None,
        "source_name": None,
        "schema_version": 1,
        "min_hindclaw_version": "0.2.0",
        "min_hindsight_version": None,
        "version": None,
        "source_url": None,
        "source_revision": None,
        "description": "",
        "author": "",
        "tags": [],
        "retain_mission": "Extract.",
        "reflect_mission": "You are.",
        "observations_mission": None,
        "retain_extraction_mode": "concise",
        "retain_custom_instructions": None,
        "retain_chunk_size": None,
        "retain_default_strategy": None,
        "retain_strategies": {},
        "entity_labels": [],
        "entities_allow_free_form": True,
        "enable_observations": True,
        "consolidation_llm_batch_size": None,
        "consolidation_source_facts_max_tokens": None,
        "consolidation_source_facts_max_tokens_per_observation": None,
        "disposition_skepticism": 3,
        "disposition_literalism": 3,
        "disposition_empathy": 3,
        "directive_seeds": [],
        "mental_model_seeds": [],
        "created_at": "2026-03-29T12:00:00",
        "updated_at": "2026-03-29T12:00:00",
    }
    defaults.update(overrides)
    return TemplateRecord(**defaults)


def _fake_source(**overrides) -> TemplateSourceRecord:
    defaults = dict(
        name="community",
        url="https://github.com/hindclaw/community-templates",
        auth_token=None,
        created_at="2026-03-29T12:00:00+00:00",
    )
    defaults.update(overrides)
    return TemplateSourceRecord(**defaults)


def _fake_marketplace_template(**overrides) -> MarketplaceTemplate:
    defaults = dict(
        schema_version=1,
        min_hindclaw_version="0.2.0",
        min_hindsight_version=None,
        name="backend-python",
        version="2.0.0",
        description="Backend patterns",
        author="community",
        tags=[],
        retain_mission="Extract.",
        reflect_mission="You are.",
        observations_mission=None,
        retain_extraction_mode="concise",
        retain_custom_instructions=None,
        retain_chunk_size=None,
        retain_default_strategy=None,
        retain_strategies={},
        entity_labels=[],
        entities_allow_free_form=True,
        enable_observations=True,
        consolidation_llm_batch_size=None,
        consolidation_source_facts_max_tokens=None,
        consolidation_source_facts_max_tokens_per_observation=None,
        disposition_skepticism=3,
        disposition_literalism=3,
        disposition_empathy=3,
        directive_seeds=[],
        mental_model_seeds=[],
    )
    defaults.update(overrides)
    return MarketplaceTemplate(**defaults)


_MINIMAL_TEMPLATE_BODY = {
    "id": "my-template",
    "scope": "server",
    "min_hindclaw_version": "0.2.0",
    "retain_mission": "Extract.",
    "reflect_mission": "You are.",
}


# --- POST /templates ---


class TestCreateTemplateServerScope:
    def test_server_scope_denied_without_admin(self, client_no_admin):
        """POST /templates with scope=server returns 403 when user lacks template:admin."""
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template = AsyncMock()
            resp = client_no_admin.post(
                "/ext/hindclaw/templates",
                json=_MINIMAL_TEMPLATE_BODY,
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 403
        mock_db.create_template.assert_not_called()

    def test_server_scope_allowed_with_admin(self, client_with_admin):
        """POST /templates with scope=server returns 201 when user has template:admin."""
        rec = _fake_template_record()
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template = AsyncMock(return_value=rec)
            resp = client_with_admin.post(
                "/ext/hindclaw/templates",
                json=_MINIMAL_TEMPLATE_BODY,
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 201

    def test_personal_scope_allowed_without_admin(self, client_no_admin):
        """POST /templates with scope=personal does not require template:admin."""
        rec = _fake_template_record(scope="personal", owner="test-user")
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template = AsyncMock(return_value=rec)
            resp = client_no_admin.post(
                "/ext/hindclaw/templates",
                json={**_MINIMAL_TEMPLATE_BODY, "scope": "personal"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 201


# --- PUT /templates/{scope}/{name} ---


class TestUpdateTemplateServerScope:
    def test_server_scope_denied_without_admin(self, client_no_admin):
        """PUT /templates/server/{name} returns 403 when user lacks template:admin."""
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.update_template = AsyncMock()
            resp = client_no_admin.put(
                "/ext/hindclaw/templates/server/my-template",
                json={"description": "updated"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 403
        mock_db.update_template.assert_not_called()

    def test_server_scope_allowed_with_admin(self, client_with_admin):
        """PUT /templates/server/{name} returns 200 when user has template:admin."""
        rec = _fake_template_record(description="updated")
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.update_template = AsyncMock(return_value=rec)
            resp = client_with_admin.put(
                "/ext/hindclaw/templates/server/my-template",
                json={"description": "updated"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200

    def test_personal_scope_allowed_without_admin(self, client_no_admin):
        """PUT /templates/personal/{name} does not require template:admin."""
        rec = _fake_template_record(scope="personal", owner="test-user", description="updated")
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.update_template = AsyncMock(return_value=rec)
            resp = client_no_admin.put(
                "/ext/hindclaw/templates/personal/my-template",
                json={"description": "updated"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200


# --- DELETE /templates/{scope}/{name} ---


class TestDeleteTemplateServerScope:
    def test_server_scope_denied_without_admin(self, client_no_admin):
        """DELETE /templates/server/{name} returns 403 when user lacks template:admin."""
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.delete_template = AsyncMock(return_value=True)
            resp = client_no_admin.delete(
                "/ext/hindclaw/templates/server/my-template",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 403
        mock_db.delete_template.assert_not_called()

    def test_server_scope_allowed_with_admin(self, client_with_admin):
        """DELETE /templates/server/{name} returns 204 when user has template:admin."""
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.delete_template = AsyncMock(return_value=True)
            resp = client_with_admin.delete(
                "/ext/hindclaw/templates/server/my-template",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 204

    def test_personal_scope_allowed_without_admin(self, client_no_admin):
        """DELETE /templates/personal/{name} does not require template:admin."""
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.delete_template = AsyncMock(return_value=True)
            resp = client_no_admin.delete(
                "/ext/hindclaw/templates/personal/my-template",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 204


# --- POST /templates/install ---


class TestInstallTemplateServerScope:
    def test_server_scope_denied_without_admin(self, client_no_admin):
        """POST /templates/install with scope=server returns 403 when user lacks template:admin."""
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.resolve_source = AsyncMock(return_value=_fake_source())
            resp = client_no_admin.post(
                "/ext/hindclaw/templates/install",
                json={"name": "backend-python", "source_name": "community", "scope": "server"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 403

    def test_server_scope_allowed_with_admin(self, client_with_admin):
        """POST /templates/install with scope=server returns 201 when user has template:admin."""
        tmpl = _fake_marketplace_template()
        rec = _fake_template_record(source_name="community", version="2.0.0")
        with patch("hindclaw_ext.http.db") as mock_db, \
             patch("hindclaw_ext.http.marketplace") as mock_mp:
            mock_db.resolve_source = AsyncMock(return_value=_fake_source())
            mock_db.upsert_template_from_marketplace = AsyncMock(return_value=rec)
            mock_mp.fetch_template = AsyncMock(return_value=tmpl)
            mock_mp.validate_template = lambda t: []
            resp = client_with_admin.post(
                "/ext/hindclaw/templates/install",
                json={"name": "backend-python", "source_name": "community", "scope": "server"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 201

    def test_personal_scope_allowed_without_admin(self, client_no_admin):
        """POST /templates/install with scope=personal does not require template:admin."""
        tmpl = _fake_marketplace_template()
        rec = _fake_template_record(scope="personal", owner="test-user", source_name="community", version="2.0.0")
        with patch("hindclaw_ext.http.db") as mock_db, \
             patch("hindclaw_ext.http.marketplace") as mock_mp:
            mock_db.resolve_source = AsyncMock(return_value=_fake_source())
            mock_db.upsert_template_from_marketplace = AsyncMock(return_value=rec)
            mock_mp.fetch_template = AsyncMock(return_value=tmpl)
            mock_mp.validate_template = lambda t: []
            resp = client_no_admin.post(
                "/ext/hindclaw/templates/install",
                json={"name": "backend-python", "source_name": "community", "scope": "personal"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 201


# --- POST /templates/{scope}/{source}/{name}/update ---


class TestUpdateFromMarketplaceServerScope:
    def test_server_scope_denied_without_admin(self, client_no_admin):
        """POST /templates/server/{source}/{name}/update returns 403 when user lacks template:admin."""
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.get_template = AsyncMock()
            resp = client_no_admin.post(
                "/ext/hindclaw/templates/server/community/backend-python/update",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 403
        mock_db.get_template.assert_not_called()

    def test_server_scope_allowed_with_admin(self, client_with_admin):
        """POST /templates/server/{source}/{name}/update returns 200 when user has template:admin."""
        installed = _fake_template_record(source_name="community", version="1.0.0")
        latest_tmpl = _fake_marketplace_template(version="2.0.0")
        updated_rec = _fake_template_record(source_name="community", version="2.0.0")
        src = _fake_source()
        with patch("hindclaw_ext.http.db") as mock_db, \
             patch("hindclaw_ext.http.marketplace") as mock_mp:
            mock_db.get_template = AsyncMock(return_value=installed)
            mock_db.get_template_source = AsyncMock(return_value=src)
            mock_db.upsert_template_from_marketplace = AsyncMock(return_value=updated_rec)
            mock_mp.fetch_template = AsyncMock(return_value=latest_tmpl)
            mock_mp.validate_template = lambda t: []
            resp = client_with_admin.post(
                "/ext/hindclaw/templates/server/community/backend-python/update",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200

    def test_personal_scope_allowed_without_admin(self, client_no_admin):
        """POST /templates/personal/{source}/{name}/update does not require template:admin."""
        installed = _fake_template_record(scope="personal", owner="test-user", source_name="community", version="1.0.0")
        latest_tmpl = _fake_marketplace_template(version="2.0.0")
        updated_rec = _fake_template_record(scope="personal", owner="test-user", source_name="community", version="2.0.0")
        src = _fake_source()
        with patch("hindclaw_ext.http.db") as mock_db, \
             patch("hindclaw_ext.http.marketplace") as mock_mp:
            mock_db.get_template = AsyncMock(return_value=installed)
            mock_db.get_template_source = AsyncMock(return_value=src)
            mock_db.upsert_template_from_marketplace = AsyncMock(return_value=updated_rec)
            mock_mp.fetch_template = AsyncMock(return_value=latest_tmpl)
            mock_mp.validate_template = lambda t: []
            resp = client_no_admin.post(
                "/ext/hindclaw/templates/personal/community/backend-python/update",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200


# --- Admin source endpoints require template:admin ---


class TestAdminSourceEndpointsRequireAdmin:
    """Admin source endpoints must require template:admin (tightened from template:source).

    Uses an action-capturing pattern: require_admin_for_action records the
    action it is called with. The patch must stay active during the request
    (not just during router construction), so it is applied inside the test.
    """

    def _make_app_and_captured(self):
        """Return (app, captured_actions) with auth patched to capture action."""
        captured_actions = []
        base_mock = AsyncMock(return_value={"principal_type": "user", "user_id": "admin"})

        async def capturing_require(action, credentials=None):
            captured_actions.append(action)
            return await base_mock(action, credentials)

        app = FastAPI()

        @app.exception_handler(AuthenticationError)
        async def auth_error_handler(request, exc):
            return JSONResponse(status_code=401, content={"detail": str(exc)})

        ext = HindclawHttp({})
        memory = AsyncMock()
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        return app, captured_actions, capturing_require

    def test_create_source_requires_template_admin(self):
        """POST /admin/template-sources passes template:admin to IAM."""
        app, captured, capturing_require = self._make_app_and_captured()
        with patch("hindclaw_ext.http.require_admin_for_action", side_effect=capturing_require), \
             patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template_source = AsyncMock(return_value=_fake_source())
            TestClient(app).post(
                "/ext/hindclaw/admin/template-sources",
                json={"url": "https://github.com/hindclaw/community-templates"},
                headers=_AUTH_HEADER,
            )
        assert "template:admin" in captured

    def test_list_sources_requires_template_admin(self):
        """GET /admin/template-sources passes template:admin to IAM."""
        app, captured, capturing_require = self._make_app_and_captured()
        with patch("hindclaw_ext.http.require_admin_for_action", side_effect=capturing_require), \
             patch("hindclaw_ext.http.db") as mock_db:
            mock_db.list_template_sources = AsyncMock(return_value=[])
            TestClient(app).get("/ext/hindclaw/admin/template-sources", headers=_AUTH_HEADER)
        assert "template:admin" in captured

    def test_delete_source_requires_template_admin(self):
        """DELETE /admin/template-sources/{name} passes template:admin to IAM."""
        app, captured, capturing_require = self._make_app_and_captured()
        with patch("hindclaw_ext.http.require_admin_for_action", side_effect=capturing_require), \
             patch("hindclaw_ext.http.db") as mock_db:
            mock_db.delete_template_source = AsyncMock(return_value=True)
            TestClient(app).delete(
                "/ext/hindclaw/admin/template-sources/community",
                headers=_AUTH_HEADER,
            )
        assert "template:admin" in captured

    def test_create_source_does_not_use_template_source(self):
        """POST /admin/template-sources no longer uses the weaker template:source action."""
        app, captured, capturing_require = self._make_app_and_captured()
        with patch("hindclaw_ext.http.require_admin_for_action", side_effect=capturing_require), \
             patch("hindclaw_ext.http.db") as mock_db:
            mock_db.create_template_source = AsyncMock(return_value=_fake_source())
            TestClient(app).post(
                "/ext/hindclaw/admin/template-sources",
                json={"url": "https://github.com/hindclaw/community-templates"},
                headers=_AUTH_HEADER,
            )
        assert "template:source" not in captured


# --- Action string captured by scope gate ---


class TestScopeGateDenialMessage:
    def test_403_message_names_required_action(self, client_no_admin):
        """403 response body names the required action."""
        with patch("hindclaw_ext.http.db"):
            resp = client_no_admin.post(
                "/ext/hindclaw/templates",
                json=_MINIMAL_TEMPLATE_BODY,
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 403
        assert "template:admin" in resp.json()["detail"]
