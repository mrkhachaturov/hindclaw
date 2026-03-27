"""Tests for bank creation from template endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindclaw_ext.bank_bootstrap import BankBootstrapResult
from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.http_models import DirectiveSeedResult, MentalModelSeedResult
from hindclaw_ext.models import TemplateRecord


TEST_SECRET = "test-secret-key-for-http-tests!!"

# Dummy bearer token -- require_admin_for_action is patched so the value
# does not matter, but HTTPBearer requires the header to be present.
_AUTH_HEADER = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.test.test"}


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", TEST_SECRET)


@pytest.fixture
def _auth_bypass():
    """Patch require_admin_for_action for the entire test lifetime."""
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
    """Create test app with auth bypassed."""
    a = FastAPI()
    ext = HindclawHttp({})
    memory = AsyncMock()
    router = ext.get_router(memory)
    a.include_router(router, prefix="/ext")
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


def _make_template(**overrides) -> TemplateRecord:
    """Build a TemplateRecord for testing."""
    defaults = dict(
        id="backend-python",
        scope="server",
        owner=None,
        source_name="hindclaw",
        schema_version=1,
        min_hindclaw_version="0.2.0",
        min_hindsight_version="0.4.20",
        version="1.0.0",
        source_url=None,
        source_revision=None,
        description="Backend patterns for Python",
        author="community",
        tags=["python", "backend"],
        retain_mission="Extract reusable backend patterns.",
        reflect_mission="You are a senior backend engineer.",
        observations_mission="Identify recurring patterns.",
        retain_extraction_mode="verbose",
        retain_custom_instructions=None,
        retain_chunk_size=None,
        retain_default_strategy=None,
        retain_strategies={},
        entity_labels=[
            {
                "key": "domain",
                "description": "Backend domain area",
                "type": "value",
                "optional": False,
                "tag": False,
                "values": [
                    {"value": "api-design", "description": "API routing"},
                    {"value": "testing", "description": "Testing strategies"},
                ],
            }
        ],
        entities_allow_free_form=True,
        enable_observations=True,
        consolidation_llm_batch_size=None,
        consolidation_source_facts_max_tokens=None,
        consolidation_source_facts_max_tokens_per_observation=None,
        disposition_skepticism=3,
        disposition_literalism=3,
        disposition_empathy=3,
        directive_seeds=[
            {"name": "No PII Storage", "content": "Never store PII.", "priority": 0, "is_active": True},
        ],
        mental_model_seeds=[
            {"name": "Python Best Practices", "source_query": "What Python patterns are established?"},
        ],
        created_at="2026-03-25T12:00:00+00:00",
        updated_at="2026-03-25T12:00:00+00:00",
    )
    defaults.update(overrides)
    return TemplateRecord(**defaults)


class TestCreateBankFromTemplate:
    def test_template_not_found(self, client):
        with patch("hindclaw_ext.http.db.get_template", new_callable=AsyncMock, return_value=None):
            resp = client.post(
                "/ext/hindclaw/banks",
                json={
                    "bank_id": "agent-alpha",
                    "template": "server/hindclaw/backend-python",
                },
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 404
        assert "not installed" in resp.json()["detail"].lower()

    def test_invalid_template_ref(self, client):
        resp = client.post(
            "/ext/hindclaw/banks",
            json={
                "bank_id": "agent-alpha",
                "template": "backend-python",
            },
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 422

    def test_successful_creation(self, client):
        template = _make_template()

        bootstrap_result = BankBootstrapResult(
            bank_created=True,
            config_applied=True,
            directives=[
                DirectiveSeedResult(name="No PII Storage", created=True, directive_id="dir-001"),
            ],
            mental_models=[
                MentalModelSeedResult(
                    name="Python Best Practices", created=True,
                    mental_model_id="mm-001", operation_id="op-001",
                ),
            ],
            errors=[],
        )

        with (
            patch("hindclaw_ext.http.db.get_template", new_callable=AsyncMock, return_value=template),
            patch("hindclaw_ext.http.bootstrap_bank_from_template", new_callable=AsyncMock, return_value=bootstrap_result) as mock_bootstrap,
        ):
            resp = client.post(
                "/ext/hindclaw/banks",
                json={
                    "bank_id": "agent-alpha",
                    "template": "server/hindclaw/backend-python",
                },
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["bank_id"] == "agent-alpha"
        assert body["bank_created"] is True
        assert body["config_applied"] is True
        assert len(body["directives"]) == 1
        assert body["directives"][0]["created"] is True
        assert body["directives"][0]["directive_id"] == "dir-001"
        assert len(body["mental_models"]) == 1
        assert body["mental_models"][0]["created"] is True
        assert body["mental_models"][0]["operation_id"] == "op-001"
        assert body["errors"] == []

        # Verify bootstrap was called with the right arguments
        mock_bootstrap.assert_called_once()
        call_kwargs = mock_bootstrap.call_args.kwargs
        assert call_kwargs["bank_id"] == "agent-alpha"
        assert call_kwargs["requesting_user_id"] == "test-admin"
        assert call_kwargs["bank_name"] is None

    def test_bank_creation_failure(self, client):
        template = _make_template()

        with (
            patch("hindclaw_ext.http.db.get_template", new_callable=AsyncMock, return_value=template),
            patch("hindclaw_ext.http.bootstrap_bank_from_template", new_callable=AsyncMock, side_effect=Exception("DB connection failed")),
        ):
            resp = client.post(
                "/ext/hindclaw/banks",
                json={
                    "bank_id": "agent-alpha",
                    "template": "server/hindclaw/backend-python",
                },
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 502
        assert "bank creation failed" in resp.json()["detail"].lower()

    def test_config_failure_partial_success(self, client):
        template = _make_template()

        bootstrap_result = BankBootstrapResult(
            bank_created=True,
            config_applied=False,
            directives=[
                DirectiveSeedResult(name="No PII Storage", created=True, directive_id="dir-001"),
            ],
            mental_models=[
                MentalModelSeedResult(
                    name="Python Best Practices", created=True,
                    mental_model_id="mm-001", operation_id="op-001",
                ),
            ],
            errors=["Config update failed: Config API error"],
        )

        with (
            patch("hindclaw_ext.http.db.get_template", new_callable=AsyncMock, return_value=template),
            patch("hindclaw_ext.http.bootstrap_bank_from_template", new_callable=AsyncMock, return_value=bootstrap_result),
        ):
            resp = client.post(
                "/ext/hindclaw/banks",
                json={
                    "bank_id": "agent-alpha",
                    "template": "server/hindclaw/backend-python",
                },
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["bank_created"] is True
        assert body["config_applied"] is False
        assert len(body["errors"]) == 1
        assert "config" in body["errors"][0].lower()
        assert len(body["directives"]) == 1
        assert len(body["mental_models"]) == 1

    def test_directive_seed_failure(self, client):
        template = _make_template()

        bootstrap_result = BankBootstrapResult(
            bank_created=True,
            config_applied=True,
            directives=[
                DirectiveSeedResult(name="No PII Storage", created=False, error="Directive API error"),
            ],
            mental_models=[
                MentalModelSeedResult(
                    name="Python Best Practices", created=True,
                    mental_model_id="mm-001", operation_id="op-001",
                ),
            ],
            errors=["Directive 'No PII Storage' failed: Directive API error"],
        )

        with (
            patch("hindclaw_ext.http.db.get_template", new_callable=AsyncMock, return_value=template),
            patch("hindclaw_ext.http.bootstrap_bank_from_template", new_callable=AsyncMock, return_value=bootstrap_result),
        ):
            resp = client.post(
                "/ext/hindclaw/banks",
                json={
                    "bank_id": "agent-alpha",
                    "template": "server/hindclaw/backend-python",
                },
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["bank_created"] is True
        assert body["config_applied"] is True
        assert len(body["directives"]) == 1
        assert body["directives"][0]["created"] is False
        assert body["directives"][0]["error"] is not None
        # Mental models still attempted despite directive failure
        assert len(body["mental_models"]) == 1
        assert body["mental_models"][0]["created"] is True

    def test_with_custom_name(self, client):
        template = _make_template(directive_seeds=[], mental_model_seeds=[])

        bootstrap_result = BankBootstrapResult(
            bank_created=True,
            config_applied=True,
            directives=[],
            mental_models=[],
            errors=[],
        )

        with (
            patch("hindclaw_ext.http.db.get_template", new_callable=AsyncMock, return_value=template),
            patch("hindclaw_ext.http.bootstrap_bank_from_template", new_callable=AsyncMock, return_value=bootstrap_result) as mock_bootstrap,
        ):
            resp = client.post(
                "/ext/hindclaw/banks",
                json={
                    "bank_id": "agent-alpha",
                    "template": "server/hindclaw/backend-python",
                    "name": "Alpha Agent",
                },
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 201
        call_kwargs = mock_bootstrap.call_args.kwargs
        assert call_kwargs["bank_name"] == "Alpha Agent"

    def test_custom_template_no_source(self, client):
        template = _make_template(source_name=None, directive_seeds=[], mental_model_seeds=[])

        bootstrap_result = BankBootstrapResult(
            bank_created=True,
            config_applied=True,
            directives=[],
            mental_models=[],
            errors=[],
        )

        with (
            patch("hindclaw_ext.http.db.get_template", new_callable=AsyncMock, return_value=template),
            patch("hindclaw_ext.http.bootstrap_bank_from_template", new_callable=AsyncMock, return_value=bootstrap_result),
        ):
            resp = client.post(
                "/ext/hindclaw/banks",
                json={
                    "bank_id": "agent-alpha",
                    "template": "server/backend-python",
                },
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 201
