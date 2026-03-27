"""Tests for in-process bank bootstrap from template."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hindclaw_ext.bank_bootstrap import bootstrap_bank_from_template
from hindclaw_ext.models import TemplateRecord


def _make_template(**overrides) -> TemplateRecord:
    defaults = dict(
        id="backend-python",
        scope="server",
        owner=None,
        source_name="hindclaw",
        schema_version=1,
        min_hindclaw_version="0.2.0",
        min_hindsight_version=None,
        version="2.1.0",
        source_url=None,
        source_revision=None,
        description="Backend patterns",
        author="community",
        tags=["python"],
        retain_mission="Extract backend patterns.",
        reflect_mission="You are a backend engineer.",
        observations_mission="Identify patterns.",
        retain_extraction_mode="verbose",
        retain_custom_instructions=None,
        retain_chunk_size=None,
        retain_default_strategy=None,
        retain_strategies={},
        entity_labels=[
            {
                "key": "domain",
                "type": "value",
                "values": [{"value": "api", "description": "API patterns"}],
            },
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
            {"name": "No PII", "content": "Never store PII.", "priority": 0, "is_active": True},
        ],
        mental_model_seeds=[
            {"name": "Python Patterns", "source_query": "What Python patterns exist?"},
        ],
        created_at="2026-03-25T12:00:00+00:00",
        updated_at="2026-03-25T12:00:00+00:00",
    )
    defaults.update(overrides)
    return TemplateRecord(**defaults)


class TestBootstrapBankFromTemplate:
    @pytest.mark.asyncio
    async def test_successful_bootstrap(self):
        memory = AsyncMock()
        memory.get_bank_profile = AsyncMock(return_value={"bank_id": "my-bank"})
        memory.update_bank = AsyncMock(return_value={"bank_id": "my-bank"})
        memory._config_resolver = AsyncMock()
        memory._config_resolver.update_bank_config = AsyncMock()
        memory.create_directive = AsyncMock(return_value={"id": "dir-001", "name": "No PII"})
        memory.create_mental_model = AsyncMock(return_value={
            "id": "mm-001", "name": "Python Patterns",
        })
        memory.submit_async_refresh_mental_model = AsyncMock(return_value={
            "operation_id": "op-001",
        })

        template = _make_template()
        result = await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
            bank_name=None,
        )

        assert result.bank_created is True
        assert result.config_applied is True
        assert len(result.directives) == 1
        assert result.directives[0].created is True
        assert len(result.mental_models) == 1
        assert result.mental_models[0].created is True
        assert result.mental_models[0].operation_id == "op-001"
        # Verify refresh was scheduled
        memory.submit_async_refresh_mental_model.assert_called_once()
        assert result.errors == []

        # Verify internal request context was used
        update_call = memory.update_bank.call_args
        ctx = update_call.kwargs["request_context"]
        assert ctx.internal is True
        assert ctx.tenant_id is None  # None so validator's _is_internal_server_call() bypasses

    @pytest.mark.asyncio
    async def test_bank_creation_failure(self):
        memory = AsyncMock()
        memory.get_bank_profile = AsyncMock(side_effect=Exception("DB connection failed"))

        template = _make_template()
        with pytest.raises(Exception, match="DB connection failed"):
            await bootstrap_bank_from_template(
                memory=memory,
                bank_id="my-bank",
                template=template,
                requesting_user_id="admin@example.com",
            )

    @pytest.mark.asyncio
    async def test_config_failure_partial_success(self):
        memory = AsyncMock()
        memory.get_bank_profile = AsyncMock(return_value={"bank_id": "my-bank"})
        memory.update_bank = AsyncMock(return_value={"bank_id": "my-bank"})
        memory._config_resolver = AsyncMock()
        memory._config_resolver.update_bank_config = AsyncMock(
            side_effect=Exception("Config error"),
        )
        memory.create_directive = AsyncMock(return_value={"id": "dir-001"})
        memory.create_mental_model = AsyncMock(return_value={"id": "mm-001"})
        memory.submit_async_refresh_mental_model = AsyncMock(return_value={
            "operation_id": "op-001",
        })

        template = _make_template()
        result = await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
        )

        assert result.bank_created is True
        assert result.config_applied is False
        assert "Config" in result.errors[0]

    @pytest.mark.asyncio
    async def test_directive_failure_continues(self):
        memory = AsyncMock()
        memory.get_bank_profile = AsyncMock(return_value={"bank_id": "my-bank"})
        memory.update_bank = AsyncMock(return_value={"bank_id": "my-bank"})
        memory._config_resolver = AsyncMock()
        memory._config_resolver.update_bank_config = AsyncMock()
        memory.create_directive = AsyncMock(side_effect=Exception("Directive error"))
        memory.create_mental_model = AsyncMock(return_value={"id": "mm-001"})
        memory.submit_async_refresh_mental_model = AsyncMock(return_value={
            "operation_id": "op-002",
        })

        template = _make_template()
        result = await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
        )

        assert result.bank_created is True
        assert result.directives[0].created is False
        assert result.directives[0].error is not None
        # Mental model should still succeed
        assert result.mental_models[0].created is True

    @pytest.mark.asyncio
    async def test_custom_bank_name(self):
        memory = AsyncMock()
        memory.get_bank_profile = AsyncMock(return_value={"bank_id": "my-bank"})
        memory.update_bank = AsyncMock(return_value={"bank_id": "my-bank"})
        memory._config_resolver = AsyncMock()
        memory._config_resolver.update_bank_config = AsyncMock()
        memory.create_directive = AsyncMock(return_value={"id": "dir-001"})
        memory.create_mental_model = AsyncMock(return_value={"id": "mm-001"})
        memory.submit_async_refresh_mental_model = AsyncMock(return_value={
            "operation_id": "op-001",
        })

        template = _make_template()
        await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
            bank_name="My Custom Bank",
        )

        update_call = memory.update_bank.call_args
        assert update_call.kwargs["name"] == "My Custom Bank"

    @pytest.mark.asyncio
    async def test_template_without_seeds(self):
        memory = AsyncMock()
        memory.get_bank_profile = AsyncMock(return_value={"bank_id": "my-bank"})
        memory.update_bank = AsyncMock(return_value={"bank_id": "my-bank"})
        memory._config_resolver = AsyncMock()
        memory._config_resolver.update_bank_config = AsyncMock()

        template = _make_template(directive_seeds=[], mental_model_seeds=[])
        result = await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
        )

        assert result.bank_created is True
        assert result.directives == []
        assert result.mental_models == []
        memory.create_directive.assert_not_called()
        memory.create_mental_model.assert_not_called()
