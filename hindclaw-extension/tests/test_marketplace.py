"""Tests for marketplace index fetching, caching, and search."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hindclaw_ext.marketplace import (
    MarketplaceIndex,
    derive_source_name,
    _resolve_file_url,
    clear_cache,
    fetch_index,
    fetch_template,
    search_marketplace,
    validate_template,
)
from hindclaw_ext.models import TemplateSourceRecord
from hindclaw_ext.template_models import MarketplaceTemplate


# --- URL derivation tests ---


class TestDeriveSourceName:
    def test_github_org(self):
        assert derive_source_name("https://github.com/hindclaw/community-templates") == "hindclaw"

    def test_github_user(self):
        assert derive_source_name("https://github.com/mrkhachaturov/templates") == "mrkhachaturov"

    def test_gitlab(self):
        assert derive_source_name("https://gitlab.com/myorg/templates") == "myorg"

    def test_self_hosted(self):
        assert derive_source_name("https://git.internal.company.com/engineering/templates") == "engineering"

    def test_trailing_slash(self):
        assert derive_source_name("https://github.com/hindclaw/templates/") == "hindclaw"

    def test_dot_git_suffix(self):
        assert derive_source_name("https://github.com/hindclaw/templates.git") == "hindclaw"

    def test_bare_host_raises(self):
        with pytest.raises(ValueError, match="Cannot derive source name"):
            derive_source_name("https://example.com/")

    def test_bare_host_no_path_raises(self):
        with pytest.raises(ValueError, match="Cannot derive source name"):
            derive_source_name("https://example.com")


class TestResolveFileUrl:
    def test_github_url(self):
        url = _resolve_file_url("https://github.com/hindclaw/community-templates", "index.json")
        assert url == "https://raw.githubusercontent.com/hindclaw/community-templates/main/index.json"

    def test_github_trailing_slash(self):
        url = _resolve_file_url("https://github.com/hindclaw/templates/", "index.json")
        assert url == "https://raw.githubusercontent.com/hindclaw/templates/main/index.json"

    def test_gitlab_url(self):
        url = _resolve_file_url("https://gitlab.com/org/repo", "index.json")
        assert url == "https://gitlab.com/org/repo/-/raw/main/index.json"

    def test_gitlab_self_hosted(self):
        url = _resolve_file_url("https://gitlab.internal.company.com/engineering/templates", "index.json")
        assert url == "https://gitlab.internal.company.com/engineering/templates/-/raw/main/index.json"

    def test_other_host_appends_path(self):
        url = _resolve_file_url("https://templates.mycompany.com/repo", "index.json")
        assert url == "https://templates.mycompany.com/repo/index.json"

    def test_github_template_file(self):
        url = _resolve_file_url("https://github.com/hindclaw/templates", "templates/backend-python.json")
        assert url == "https://raw.githubusercontent.com/hindclaw/templates/main/templates/backend-python.json"


# --- Index fetching tests ---


def _sample_index() -> dict:
    """Return a sample marketplace index.json structure."""
    return {
        "templates": [
            {
                "name": "backend-python",
                "version": "2.1.0",
                "description": "Backend patterns for Python projects",
                "author": "community",
                "tags": ["python", "backend", "api"],
            },
            {
                "name": "frontend-react",
                "version": "1.0.0",
                "description": "Frontend patterns for React apps",
                "author": "community",
                "tags": ["react", "frontend", "typescript"],
            },
        ],
    }


class TestFetchIndex:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        clear_cache()
        yield
        clear_cache()

    @pytest.mark.asyncio
    async def test_fetches_and_parses_index(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value=json.dumps(_sample_index()))

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="hindclaw",
            url="https://github.com/hindclaw/community-templates",
            auth_token=None,
            created_at="2026-03-25T12:00:00+00:00",
        )

        result = await fetch_index(source, session=mock_session)
        assert isinstance(result, MarketplaceIndex)
        assert len(result.templates) == 2
        assert result.templates[0]["name"] == "backend-python"

    @pytest.mark.asyncio
    async def test_returns_cached_on_second_call(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value=json.dumps(_sample_index()))

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="hindclaw",
            url="https://github.com/hindclaw/community-templates",
            auth_token=None,
            created_at="2026-03-25T12:00:00+00:00",
        )

        result1 = await fetch_index(source, session=mock_session)
        result2 = await fetch_index(source, session=mock_session)
        assert result1 is result2
        # Session.get context manager should only be entered once
        assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_sends_auth_header(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value=json.dumps(_sample_index()))

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="private",
            url="https://github.com/astrateam/private-templates",
            auth_token="ghp_abc123",
            created_at="2026-03-25T12:00:00+00:00",
        )

        await fetch_index(source, session=mock_session)
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer ghp_abc123"

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not Found")

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="bad",
            url="https://github.com/missing/repo",
            auth_token=None,
            created_at="2026-03-25T12:00:00+00:00",
        )

        result = await fetch_index(source, session=mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_stale_cache_on_fetch_error(self):
        """If cache exists but is expired, return stale data on fetch failure."""
        mock_response_ok = AsyncMock()
        mock_response_ok.status = 200
        mock_response_ok.content_type = "application/json"
        mock_response_ok.text = AsyncMock(return_value=json.dumps(_sample_index()))

        mock_response_err = AsyncMock()
        mock_response_err.status = 500
        mock_response_err.text = AsyncMock(return_value="Internal Server Error")

        mock_session = AsyncMock()

        source = TemplateSourceRecord(
            name="hindclaw",
            url="https://github.com/hindclaw/community-templates",
            auth_token=None,
            created_at="2026-03-25T12:00:00+00:00",
        )

        # First call succeeds
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response_ok),
            __aexit__=AsyncMock(return_value=False),
        ))
        result1 = await fetch_index(source, session=mock_session)
        assert result1 is not None

        # Expire the cache
        from hindclaw_ext.marketplace import _index_cache
        _index_cache[("hindclaw", "server", None)] = (result1, time.time() - 600)

        # Second call fails — should return stale cache
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response_err),
            __aexit__=AsyncMock(return_value=False),
        ))
        result2 = await fetch_index(source, session=mock_session)
        assert result2 is result1


# --- Search tests ---


class TestSearchMarketplace:
    def test_search_by_query(self):
        index = MarketplaceIndex(templates=_sample_index()["templates"])
        results = search_marketplace(index, source_name="hindclaw", query="python")
        assert len(results) == 1
        assert results[0].name == "backend-python"
        assert results[0].source == "hindclaw"

    def test_search_by_tag(self):
        index = MarketplaceIndex(templates=_sample_index()["templates"])
        results = search_marketplace(index, source_name="hindclaw", tag="react")
        assert len(results) == 1
        assert results[0].name == "frontend-react"

    def test_search_matches_description(self):
        index = MarketplaceIndex(templates=_sample_index()["templates"])
        results = search_marketplace(index, source_name="hindclaw", query="frontend")
        assert len(results) == 1
        assert results[0].name == "frontend-react"

    def test_search_no_match(self):
        index = MarketplaceIndex(templates=_sample_index()["templates"])
        results = search_marketplace(index, source_name="hindclaw", query="golang")
        assert len(results) == 0

    def test_search_no_filters_returns_all(self):
        index = MarketplaceIndex(templates=_sample_index()["templates"])
        results = search_marketplace(index, source_name="hindclaw")
        assert len(results) == 2

    def test_search_result_has_source(self):
        index = MarketplaceIndex(templates=_sample_index()["templates"])
        results = search_marketplace(index, source_name="astrateam")
        for r in results:
            assert r.source == "astrateam"


# --- Template fetch and validation tests ---


def _sample_template_json() -> dict:
    """Return a valid marketplace template JSON."""
    return {
        "schema_version": 1,
        "min_hindclaw_version": "0.2.0",
        "min_hindsight_version": None,
        "name": "backend-python",
        "version": "2.1.0",
        "description": "Backend patterns for Python projects",
        "author": "community",
        "tags": ["python", "backend"],
        "retain_mission": "Extract backend patterns.",
        "reflect_mission": "You are a backend engineer.",
        "observations_mission": None,
        "retain_extraction_mode": "verbose",
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


class TestFetchTemplate:
    @pytest.fixture(autouse=True)
    def _clear(self):
        clear_cache()
        yield
        clear_cache()

    @pytest.mark.asyncio
    async def test_fetches_and_parses_template(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value=json.dumps(_sample_template_json()))

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="hindclaw",
            url="https://github.com/hindclaw/community-templates",
            auth_token=None,
            created_at="2026-03-25T12:00:00+00:00",
        )

        result = await fetch_template(source, "backend-python", session=mock_session)
        assert isinstance(result, MarketplaceTemplate)
        assert result.name == "backend-python"
        assert result.version == "2.1.0"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self):
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not Found")

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="hindclaw",
            url="https://github.com/hindclaw/community-templates",
            auth_token=None,
            created_at="2026-03-25T12:00:00+00:00",
        )

        result = await fetch_template(source, "nonexistent", session=mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value=json.dumps({"name": "incomplete"}))

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="hindclaw",
            url="https://github.com/hindclaw/community-templates",
            auth_token=None,
            created_at="2026-03-25T12:00:00+00:00",
        )

        result = await fetch_template(source, "broken", session=mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_sends_auth_header(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value=json.dumps(_sample_template_json()))

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        source = TemplateSourceRecord(
            name="private",
            url="https://github.com/astrateam/templates",
            auth_token="ghp_secret",
            created_at="2026-03-25T12:00:00+00:00",
        )

        await fetch_template(source, "backend-python", session=mock_session)
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer ghp_secret"


class TestCacheCompositeKey:
    def test_cache_uses_composite_key(self):
        """Marketplace cache keys by (name, scope, owner) not just name."""
        from hindclaw_ext import marketplace
        from hindclaw_ext.models import TemplateSourceRecord

        marketplace.clear_cache()

        from hindclaw_ext.marketplace import MarketplaceIndex
        marketplace._index_cache[("hindclaw", "server", None)] = (
            MarketplaceIndex(templates=[{"name": "server-t"}]), 9999999999.0,
        )
        marketplace._index_cache[("hindclaw", "personal", "alice")] = (
            MarketplaceIndex(templates=[{"name": "personal-t"}]), 9999999999.0,
        )

        assert len(marketplace._index_cache) == 2
        server_cached = marketplace._index_cache[("hindclaw", "server", None)]
        personal_cached = marketplace._index_cache[("hindclaw", "personal", "alice")]
        assert server_cached[0].templates[0]["name"] == "server-t"
        assert personal_cached[0].templates[0]["name"] == "personal-t"

        marketplace.clear_cache()


class TestValidateTemplate:
    def test_valid_template_passes(self):
        t = MarketplaceTemplate(**_sample_template_json())
        errors = validate_template(t)
        assert errors == []

    def test_unsupported_schema_version(self):
        t = MarketplaceTemplate(**_sample_template_json())
        t = t.model_copy(update={"schema_version": 99})
        errors = validate_template(t)
        assert any("schema_version" in e for e in errors)

    def test_hindclaw_version_too_new(self):
        t = MarketplaceTemplate(**_sample_template_json())
        t = t.model_copy(update={"min_hindclaw_version": "99.0.0"})
        errors = validate_template(t)
        assert any("hindclaw" in e.lower() for e in errors)

    def test_hindclaw_version_compatible(self):
        t = MarketplaceTemplate(**_sample_template_json())
        t = t.model_copy(update={"min_hindclaw_version": "0.1.0"})
        errors = validate_template(t)
        assert errors == []

    def test_hindsight_version_too_new(self):
        t = MarketplaceTemplate(**_sample_template_json())
        t = t.model_copy(update={"min_hindsight_version": "99.0.0"})
        errors = validate_template(t)
        assert any("hindsight" in e.lower() for e in errors)

    def test_hindsight_version_none_skips_check(self):
        t = MarketplaceTemplate(**_sample_template_json())
        t = t.model_copy(update={"min_hindsight_version": None})
        errors = validate_template(t)
        assert not any("hindsight" in e.lower() for e in errors)
