"""Tests for /me/templates and /me/templates/install endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindsight_api.extensions import AuthenticationError
from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import TemplateRecord, TemplateSourceRecord
from hindclaw_ext.template_models import MarketplaceTemplate


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-for-me-templates!!")


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


# --- Helpers ---


def _make_template_record(**overrides) -> TemplateRecord:
    """Build a TemplateRecord with personal-scope defaults."""
    defaults = {
        "id": "test-template",
        "scope": "personal",
        "owner": "alice",
        "source_name": None,
        "schema_version": 1,
        "min_hindclaw_version": "0.1.0",
        "min_hindsight_version": None,
        "version": None,
        "source_url": None,
        "source_revision": None,
        "description": "test",
        "author": "alice",
        "tags": [],
        "retain_mission": "test mission",
        "reflect_mission": "test reflect",
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
        "created_at": "2026-03-29T00:00:00Z",
        "updated_at": "2026-03-29T00:00:00Z",
    }
    defaults.update(overrides)
    return TemplateRecord(**defaults)


def _make_marketplace_template(**overrides) -> MarketplaceTemplate:
    """Build a MarketplaceTemplate with defaults."""
    defaults = {
        "schema_version": 1,
        "min_hindclaw_version": "0.1.0",
        "min_hindsight_version": None,
        "name": "community-template",
        "version": "1.0.0",
        "description": "community template",
        "author": "community",
        "tags": [],
        "retain_mission": "Extract patterns.",
        "reflect_mission": "Reflect.",
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
    }
    defaults.update(overrides)
    return MarketplaceTemplate(**defaults)


def _make_source(**overrides) -> TemplateSourceRecord:
    """Build a TemplateSourceRecord with server-scope defaults."""
    defaults = {
        "name": "community",
        "url": "https://github.com/hindclaw/community-templates",
        "scope": "server",
        "owner": None,
        "auth_token": None,
        "created_at": "2026-03-29T00:00:00Z",
    }
    defaults.update(overrides)
    return TemplateSourceRecord(**defaults)


# --- List ---


def test_list_my_templates(alice_client, headers, mock_db):
    """GET /me/templates returns personal templates for the caller."""
    record = _make_template_record()
    mock_db.list_templates = AsyncMock(return_value=[record])

    resp = alice_client.get("/ext/hindclaw/me/templates", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == "test-template"
    assert body[0]["scope"] == "personal"
    mock_db.list_templates.assert_called_once_with(scope="personal", owner="alice")


# --- Create ---


def test_create_my_template(alice_client, headers, mock_db):
    """POST /me/templates creates a personal template with scope=personal and owner=alice."""
    record = _make_template_record()
    mock_db.create_template = AsyncMock(return_value=record)

    resp = alice_client.post(
        "/ext/hindclaw/me/templates",
        json={
            "id": "test-template",
            "scope": "personal",
            "min_hindclaw_version": "0.1.0",
            "retain_mission": "test mission",
            "reflect_mission": "test reflect",
        },
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "test-template"
    assert body["scope"] == "personal"
    assert body["owner"] == "alice"

    call_kwargs = mock_db.create_template.call_args[1]
    assert call_kwargs["scope"] == "personal"
    assert call_kwargs["owner"] == "alice"
    assert call_kwargs["source_name"] is None


def test_create_my_template_duplicate_returns_409(alice_client, headers, mock_db):
    """POST /me/templates returns 409 when template id already exists."""
    mock_db.create_template = AsyncMock(
        side_effect=asyncpg.UniqueViolationError("duplicate"),
    )

    resp = alice_client.post(
        "/ext/hindclaw/me/templates",
        json={
            "id": "test-template",
            "scope": "personal",
            "min_hindclaw_version": "0.1.0",
            "retain_mission": "test mission",
            "reflect_mission": "test reflect",
        },
        headers=headers,
    )

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


# --- Get ---


def test_get_my_template(alice_client, headers, mock_db):
    """GET /me/templates/{name} returns the single matching template."""
    record = _make_template_record()
    mock_db.list_templates = AsyncMock(return_value=[record])

    resp = alice_client.get("/ext/hindclaw/me/templates/test-template", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "test-template"
    assert body["owner"] == "alice"


def test_get_my_template_ambiguous_returns_409(alice_client, headers, mock_db):
    """GET /me/templates/{name} returns 409 when multiple templates share the same name."""
    record_custom = _make_template_record(source_name=None)
    record_sourced = _make_template_record(source_name="community")
    mock_db.list_templates = AsyncMock(return_value=[record_custom, record_sourced])

    resp = alice_client.get("/ext/hindclaw/me/templates/test-template", headers=headers)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "Ambiguous" in detail
    assert "source=" in detail


def test_get_my_template_with_source_disambiguates(alice_client, headers, mock_db):
    """GET /me/templates/{name}?source=community selects the sourced template."""
    record_custom = _make_template_record(source_name=None)
    record_sourced = _make_template_record(source_name="community")
    mock_db.list_templates = AsyncMock(return_value=[record_custom, record_sourced])

    resp = alice_client.get(
        "/ext/hindclaw/me/templates/test-template?source=community",
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_name"] == "community"


def test_get_my_template_empty_source_selects_custom(alice_client, headers, mock_db):
    """GET /me/templates/{name}?source= (empty string) selects the custom template (source_name=None)."""
    record_custom = _make_template_record(source_name=None)
    record_sourced = _make_template_record(source_name="community")
    mock_db.list_templates = AsyncMock(return_value=[record_custom, record_sourced])

    resp = alice_client.get(
        "/ext/hindclaw/me/templates/test-template?source=",
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_name"] is None


def test_get_my_template_not_found(alice_client, headers, mock_db):
    """GET /me/templates/{name} returns 404 when template does not exist."""
    mock_db.list_templates = AsyncMock(return_value=[])

    resp = alice_client.get("/ext/hindclaw/me/templates/nonexistent", headers=headers)

    assert resp.status_code == 404


# --- Update ---


def test_update_my_template(alice_client, headers, mock_db):
    """PUT /me/templates/{name} updates the matched template."""
    record = _make_template_record()
    updated = _make_template_record(description="updated description")
    mock_db.list_templates = AsyncMock(return_value=[record])
    mock_db.update_template = AsyncMock(return_value=updated)

    resp = alice_client.put(
        "/ext/hindclaw/me/templates/test-template",
        json={"description": "updated description"},
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "updated description"

    mock_db.update_template.assert_called_once_with(
        "test-template",
        "personal",
        owner="alice",
        source_name=None,
        updates={"description": "updated description"},
    )


# --- Delete ---


def test_delete_my_template(alice_client, headers, mock_db):
    """DELETE /me/templates/{name} deletes the matched template."""
    record = _make_template_record()
    mock_db.list_templates = AsyncMock(return_value=[record])
    mock_db.delete_template = AsyncMock(return_value=True)

    resp = alice_client.delete("/ext/hindclaw/me/templates/test-template", headers=headers)

    assert resp.status_code == 204
    mock_db.delete_template.assert_called_once_with(
        "test-template",
        "personal",
        owner="alice",
        source_name=None,
    )


def test_delete_my_template_not_found(alice_client, headers, mock_db):
    """DELETE /me/templates/{name} returns 404 when template does not exist."""
    mock_db.list_templates = AsyncMock(return_value=[])

    resp = alice_client.delete("/ext/hindclaw/me/templates/nonexistent", headers=headers)

    assert resp.status_code == 404


def test_update_my_template_ambiguous_returns_409(alice_client, headers, mock_db):
    """PUT /me/templates/{name} returns 409 when multiple sources match."""
    record_custom = _make_template_record(source_name=None)
    record_sourced = _make_template_record(source_name="community")
    mock_db.list_templates = AsyncMock(return_value=[record_custom, record_sourced])

    resp = alice_client.put(
        "/ext/hindclaw/me/templates/test-template",
        headers=headers,
        json={"description": "updated"},
    )

    assert resp.status_code == 409
    assert "Ambiguous" in resp.json()["detail"]


def test_delete_my_template_ambiguous_returns_409(alice_client, headers, mock_db):
    """DELETE /me/templates/{name} returns 409 when multiple sources match."""
    record_custom = _make_template_record(source_name=None)
    record_sourced = _make_template_record(source_name="community")
    mock_db.list_templates = AsyncMock(return_value=[record_custom, record_sourced])

    resp = alice_client.delete("/ext/hindclaw/me/templates/test-template", headers=headers)

    assert resp.status_code == 409
    assert "Ambiguous" in resp.json()["detail"]


# --- Install ---


def test_install_my_template(alice_client, headers, mock_db):
    """POST /me/templates/install installs a template from a visible source to personal scope."""
    source = _make_source()
    mkt_template = _make_marketplace_template()
    record = _make_template_record(
        source_name="community",
        source_url="https://github.com/hindclaw/community-templates",
        version="1.0.0",
    )

    mock_db.resolve_source = AsyncMock(return_value=source)
    mock_db.upsert_template_from_marketplace = AsyncMock(return_value=record)

    with patch("hindclaw_ext.http.marketplace") as mock_mkt:
        mock_mkt.fetch_template = AsyncMock(return_value=mkt_template)
        mock_mkt.validate_template = MagicMock(return_value=[])

        resp = alice_client.post(
            "/ext/hindclaw/me/templates/install",
            json={"source_name": "community", "name": "community-template"},
            headers=headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["source_name"] == "community"

    call_kwargs = mock_db.upsert_template_from_marketplace.call_args[1]
    assert call_kwargs["scope"] == "personal"
    assert call_kwargs["owner"] == "alice"


def test_install_my_template_ambiguous_source(alice_client, headers, mock_db):
    """POST /me/templates/install returns 409 when resolve_source raises ValueError (ambiguous)."""
    mock_db.resolve_source = AsyncMock(
        side_effect=ValueError("Ambiguous source 'community': found in both personal and server scopes"),
    )

    resp = alice_client.post(
        "/ext/hindclaw/me/templates/install",
        json={"source_name": "community", "name": "community-template"},
        headers=headers,
    )

    assert resp.status_code == 409
    assert "Ambiguous" in resp.json()["detail"]


def test_install_my_template_source_not_found(alice_client, headers, mock_db):
    """POST /me/templates/install returns 404 when resolve_source raises KeyError (not found)."""
    mock_db.resolve_source = AsyncMock(
        side_effect=KeyError("Source not found: 'unknown'"),
    )

    resp = alice_client.post(
        "/ext/hindclaw/me/templates/install",
        json={"source_name": "unknown", "name": "community-template"},
        headers=headers,
    )

    assert resp.status_code == 404
