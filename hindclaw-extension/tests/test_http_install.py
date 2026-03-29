"""Tests for template install and update endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import TemplateRecord, TemplateSourceRecord
from hindclaw_ext.policy_engine import AccessResult
from hindclaw_ext.template_models import MarketplaceTemplate


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
    patcher_iam = patch(
        "hindclaw_ext.http._evaluate_iam_access",
        new_callable=AsyncMock,
        return_value=AccessResult(allowed=True),
    )
    patcher.start()
    patcher_iam.start()
    yield
    patcher.stop()
    patcher_iam.stop()


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


def _make_marketplace_template(**overrides) -> MarketplaceTemplate:
    defaults = dict(
        schema_version=1,
        min_hindclaw_version="0.2.0",
        min_hindsight_version=None,
        name="backend-python",
        version="2.1.0",
        description="Backend patterns",
        author="community",
        tags=["python"],
        retain_mission="Extract patterns.",
        reflect_mission="You are an engineer.",
        observations_mission=None,
        retain_extraction_mode="verbose",
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


def _make_template_record(**overrides) -> TemplateRecord:
    defaults = dict(
        id="backend-python",
        scope="server",
        owner=None,
        source_name="hindclaw",
        schema_version=1,
        min_hindclaw_version="0.2.0",
        min_hindsight_version=None,
        version="2.1.0",
        source_url="https://github.com/hindclaw/community-templates",
        source_revision=None,
        description="Backend patterns",
        author="community",
        tags=["python"],
        retain_mission="Extract patterns.",
        reflect_mission="You are an engineer.",
        observations_mission=None,
        retain_extraction_mode="verbose",
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
        created_at="2026-03-25T12:00:00+00:00",
        updated_at="2026-03-25T12:00:00+00:00",
    )
    defaults.update(overrides)
    return TemplateRecord(**defaults)


class TestInstallTemplate:
    def test_install_success(self, client):
        source = _make_source()
        mkt_template = _make_marketplace_template()
        record = _make_template_record()

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.resolve_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=mkt_template)
            mock_mkt.validate_template = MagicMock(return_value=[])
            mock_db.upsert_template_from_marketplace = AsyncMock(return_value=record)

            resp = client.post(
                "/ext/hindclaw/templates/install",
                json={"source": "hindclaw", "name": "backend-python", "scope": "server"},
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "backend-python"
        assert body["source_name"] == "hindclaw"

    def test_install_source_not_found(self, client):
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.resolve_source = AsyncMock(side_effect=KeyError("Source not found: 'unknown'"))
            resp = client.post(
                "/ext/hindclaw/templates/install",
                json={"source": "unknown", "name": "test", "scope": "server"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 404
        assert "source" in resp.json()["detail"].lower()

    def test_install_template_not_found(self, client):
        source = _make_source()
        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.resolve_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=None)
            resp = client.post(
                "/ext/hindclaw/templates/install",
                json={"source": "hindclaw", "name": "nonexistent", "scope": "server"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 404
        assert "template" in resp.json()["detail"].lower()

    def test_install_incompatible(self, client):
        source = _make_source()
        mkt_template = _make_marketplace_template(min_hindclaw_version="99.0.0")

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.resolve_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=mkt_template)
            mock_mkt.validate_template = MagicMock(
                return_value=["Requires hindclaw >= 99.0.0"],
            )
            resp = client.post(
                "/ext/hindclaw/templates/install",
                json={"source": "hindclaw", "name": "backend-python", "scope": "server"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 422
        assert "99.0.0" in resp.json()["detail"]

    def test_install_personal_sets_owner(self, client):
        source = _make_source()
        mkt_template = _make_marketplace_template()
        record = _make_template_record(scope="personal", owner="test-admin")

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.resolve_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=mkt_template)
            mock_mkt.validate_template = MagicMock(return_value=[])
            mock_db.upsert_template_from_marketplace = AsyncMock(return_value=record)

            resp = client.post(
                "/ext/hindclaw/templates/install",
                json={"source": "hindclaw", "name": "backend-python", "scope": "personal"},
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 201
        # Verify owner was passed to upsert
        call_kwargs = mock_db.upsert_template_from_marketplace.call_args[1]
        assert call_kwargs["owner"] == "test-admin"

    def test_install_name_mismatch(self, client):
        source = _make_source()
        mkt_template = _make_marketplace_template(name="other-template")

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.resolve_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=mkt_template)
            resp = client.post(
                "/ext/hindclaw/templates/install",
                json={"source": "hindclaw", "name": "backend-python", "scope": "server"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 422
        assert "mismatch" in resp.json()["detail"].lower()


class TestUpdateTemplate:
    def test_update_success(self, client):
        installed = _make_template_record(version="2.0.0")
        source = _make_source()
        newer = _make_marketplace_template(version="3.0.0")
        updated_record = _make_template_record(version="3.0.0")

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.get_template = AsyncMock(return_value=installed)
            mock_db.get_template_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=newer)
            mock_mkt.validate_template = MagicMock(return_value=[])
            mock_db.upsert_template_from_marketplace = AsyncMock(return_value=updated_record)

            resp = client.post(
                "/ext/hindclaw/templates/server/hindclaw/backend-python/update",
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["updated"] is True
        assert body["previous_version"] == "2.0.0"
        assert body["new_version"] == "3.0.0"

    def test_update_no_newer_version(self, client):
        installed = _make_template_record(version="2.1.0")
        source = _make_source()
        same = _make_marketplace_template(version="2.1.0")

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.get_template = AsyncMock(return_value=installed)
            mock_db.get_template_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=same)
            mock_mkt.validate_template = MagicMock(return_value=[])

            resp = client.post(
                "/ext/hindclaw/templates/server/hindclaw/backend-python/update",
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["updated"] is False

    def test_update_template_not_installed(self, client):
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.get_template = AsyncMock(return_value=None)
            resp = client.post(
                "/ext/hindclaw/templates/server/hindclaw/backend-python/update",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 404

    def test_update_source_not_found(self, client):
        installed = _make_template_record()
        with patch("hindclaw_ext.http.db") as mock_db:
            mock_db.get_template = AsyncMock(return_value=installed)
            mock_db.get_template_source = AsyncMock(return_value=None)
            resp = client.post(
                "/ext/hindclaw/templates/server/hindclaw/backend-python/update",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 404
        assert "source" in resp.json()["detail"].lower()

    def test_update_name_mismatch(self, client):
        installed = _make_template_record()
        source = _make_source()
        mismatched = _make_marketplace_template(name="wrong-name")

        with (
            patch("hindclaw_ext.http.db") as mock_db,
            patch("hindclaw_ext.http.marketplace") as mock_mkt,
        ):
            mock_db.get_template = AsyncMock(return_value=installed)
            mock_db.get_template_source = AsyncMock(return_value=source)
            mock_mkt.fetch_template = AsyncMock(return_value=mismatched)
            resp = client.post(
                "/ext/hindclaw/templates/server/hindclaw/backend-python/update",
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 422
        assert "mismatch" in resp.json()["detail"].lower()
