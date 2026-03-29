"""Tests for template HTTP endpoints."""

import time
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import TemplateRecord
from hindclaw_ext.policy_engine import AccessResult


TEST_SECRET = "test-secret-key-for-http-tests!!"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", TEST_SECRET)


def _make_admin_jwt() -> str:
    """Create a signed admin JWT for test requests."""
    return pyjwt.encode(
        {"client_id": "app-prod", "exp": int(time.time()) + 300},
        TEST_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def app():
    """Create test app with auth overridden -- matches test_http.py pattern."""
    a = FastAPI()
    ext = HindclawHttp({})
    memory = AsyncMock()
    with patch(
        "hindclaw_ext.http.require_admin_for_action",
        new_callable=AsyncMock,
        return_value={"principal_type": "user", "user_id": "test-admin"},
    ), patch(
        "hindclaw_ext.http._evaluate_iam_access",
        new_callable=AsyncMock,
        return_value=AccessResult(allowed=True),
    ):
        router = ext.get_router(memory)
        a.include_router(router, prefix="/ext")
        yield a


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {_make_admin_jwt()}"}


@pytest.fixture
def mock_db():
    """Patch hindclaw_ext.http.db and yield mock_db module.

    All db.* calls inside http.py hit this mock.
    """
    with patch("hindclaw_ext.http.db") as mdb:
        yield mdb


def _fake_template_record(**overrides) -> TemplateRecord:
    """Build a TemplateRecord for mocking db return values."""
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
        "created_at": "2026-03-25T12:00:00+00:00",
        "updated_at": "2026-03-25T12:00:00+00:00",
    }
    defaults.update(overrides)
    return TemplateRecord(**defaults)


class TestListTemplates:
    def test_list_empty(self, client, admin_headers, mock_db):
        mock_db.list_templates = AsyncMock(return_value=[])
        resp = client.get("/ext/hindclaw/templates", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_scope_filter(self, client, admin_headers, mock_db):
        rec = _fake_template_record()
        mock_db.list_templates = AsyncMock(return_value=[rec])
        resp = client.get("/ext/hindclaw/templates?scope=server", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == "my-template"


class TestCreateTemplate:
    def test_create_minimal(self, client, admin_headers, mock_db):
        rec = _fake_template_record()
        mock_db.create_template = AsyncMock(return_value=rec)
        resp = client.post(
            "/ext/hindclaw/templates",
            json={
                "id": "my-template",
                "scope": "server",
                "min_hindclaw_version": "0.2.0",
                "retain_mission": "Extract.",
                "reflect_mission": "You are.",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == "my-template"

    def test_create_invalid_scope(self, client, admin_headers, mock_db):
        resp = client.post(
            "/ext/hindclaw/templates",
            json={
                "id": "x",
                "scope": "invalid",
                "min_hindclaw_version": "0.2.0",
                "retain_mission": "x",
                "reflect_mission": "x",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestGetTemplate:
    def test_not_found(self, client, admin_headers, mock_db):
        mock_db.get_template = AsyncMock(return_value=None)
        resp = client.get("/ext/hindclaw/templates/server/backend-python", headers=admin_headers)
        assert resp.status_code == 404

    def test_found(self, client, admin_headers, mock_db):
        rec = _fake_template_record(id="backend-python")
        mock_db.get_template = AsyncMock(return_value=rec)
        resp = client.get("/ext/hindclaw/templates/server/backend-python", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == "backend-python"


class TestUpdateTemplate:
    def test_update_not_found(self, client, admin_headers, mock_db):
        mock_db.update_template = AsyncMock(return_value=None)
        resp = client.put(
            "/ext/hindclaw/templates/server/my-template",
            json={"description": "Updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_update_success(self, client, admin_headers, mock_db):
        mock_record = _fake_template_record(description="Updated desc")
        mock_db.update_template = AsyncMock(return_value=mock_record)
        resp = client.put(
            "/ext/hindclaw/templates/server/my-template",
            json={"description": "Updated desc"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated desc"

    def test_update_cross_field_validation_fails(self, client, admin_headers, mock_db):
        """Setting extraction mode to 'custom' without instructions should fail."""
        existing = _fake_template_record()
        mock_db.get_template = AsyncMock(return_value=existing)
        resp = client.put(
            "/ext/hindclaw/templates/server/my-template",
            json={"retain_extraction_mode": "custom"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "retain_custom_instructions" in resp.json()["detail"]


class TestDeleteTemplate:
    def test_not_found(self, client, admin_headers, mock_db):
        mock_db.delete_template = AsyncMock(return_value=False)
        resp = client.delete("/ext/hindclaw/templates/server/backend-python", headers=admin_headers)
        assert resp.status_code == 404

    def test_success(self, client, admin_headers, mock_db):
        mock_db.delete_template = AsyncMock(return_value=True)
        resp = client.delete("/ext/hindclaw/templates/server/backend-python", headers=admin_headers)
        assert resp.status_code == 204
