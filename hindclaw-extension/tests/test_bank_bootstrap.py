"""Tests for in-process bank bootstrap from template."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hindclaw_ext.bank_bootstrap import bootstrap_bank_from_template
from hindclaw_ext.models import TemplateRecord
from hindclaw_ext.template_models import MarketplaceTemplate

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "hindclaw-templates" / "templates"


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
    async def test_update_bank_uses_reflect_mission(self):
        """Bank-level mission should be reflect_mission, not retain_mission."""
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

        template = _make_template(
            retain_mission="Extract backend patterns.",
            reflect_mission="You are a backend engineer.",
        )
        await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
        )

        update_call = memory.update_bank.call_args
        assert update_call.kwargs["mission"] == "You are a backend engineer."

    @pytest.mark.asyncio
    async def test_retain_mission_in_config_updates(self):
        """retain_mission must be stored in bank config, not bank-level mission."""
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

        template = _make_template(retain_mission="Extract backend patterns.")
        await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
        )

        config_call = memory._config_resolver.update_bank_config.call_args
        config_updates = config_call.args[1]
        assert config_updates["retain_mission"] == "Extract backend patterns."

    @pytest.mark.asyncio
    async def test_empty_reflect_mission_falls_back_to_name(self):
        """Bank-level mission falls back to bank name when reflect_mission is empty."""
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

        template = _make_template(reflect_mission="")
        await bootstrap_bank_from_template(
            memory=memory,
            bank_id="my-bank",
            template=template,
            requesting_user_id="admin@example.com",
        )

        update_call = memory.update_bank.call_args
        # Falls back to template.id ("backend-python") since bank_name is None
        assert update_call.kwargs["mission"] == "backend-python"

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


class TestRealMarketplaceTemplateBootstrap:
    """Bootstrap from real marketplace templates — verify all fields propagate.

    Uses actual template JSON from hindclaw-templates-official to catch
    the class of bug where a template field is stored but not applied
    during bank creation (e.g., the retain_mission bug caught earlier).
    """

    @staticmethod
    def _load_template_as_record(name: str) -> TemplateRecord:
        """Load real template JSON and convert to TemplateRecord (as install would)."""
        path = _TEMPLATES_DIR / f"{name}.json"
        if not path.exists():
            pytest.skip(f"Template {name} not found at {path}")
        data = json.loads(path.read_text())
        mkt = MarketplaceTemplate(**data)
        return TemplateRecord(
            id=mkt.name, scope="server", owner=None,
            source_name="hindclaw-official",
            schema_version=mkt.schema_version,
            min_hindclaw_version=mkt.min_hindclaw_version,
            min_hindsight_version=mkt.min_hindsight_version,
            version=mkt.version,
            source_url="https://github.com/mrkhachaturov/hindclaw-templates-official",
            source_revision=None,
            description=mkt.description, author=mkt.author, tags=mkt.tags,
            retain_mission=mkt.retain_mission,
            reflect_mission=mkt.reflect_mission,
            observations_mission=mkt.observations_mission,
            retain_extraction_mode=mkt.retain_extraction_mode,
            retain_custom_instructions=mkt.retain_custom_instructions,
            retain_chunk_size=mkt.retain_chunk_size,
            retain_default_strategy=mkt.retain_default_strategy,
            retain_strategies=mkt.retain_strategies,
            entity_labels=[l.model_dump() for l in mkt.entity_labels],
            entities_allow_free_form=mkt.entities_allow_free_form,
            enable_observations=mkt.enable_observations,
            consolidation_llm_batch_size=mkt.consolidation_llm_batch_size,
            consolidation_source_facts_max_tokens=mkt.consolidation_source_facts_max_tokens,
            consolidation_source_facts_max_tokens_per_observation=mkt.consolidation_source_facts_max_tokens_per_observation,
            disposition_skepticism=mkt.disposition_skepticism,
            disposition_literalism=mkt.disposition_literalism,
            disposition_empathy=mkt.disposition_empathy,
            directive_seeds=[s.model_dump() for s in mkt.directive_seeds],
            mental_model_seeds=[s.model_dump() for s in mkt.mental_model_seeds],
            created_at="2026-03-29T00:00:00Z",
            updated_at="2026-03-29T00:00:00Z",
        )

    @staticmethod
    def _make_memory():
        memory = AsyncMock()
        memory.get_bank_profile = AsyncMock(return_value={"bank_id": "test-bank"})
        memory.update_bank = AsyncMock(return_value={"bank_id": "test-bank"})
        memory._config_resolver = AsyncMock()
        memory._config_resolver.update_bank_config = AsyncMock()
        memory.create_directive = AsyncMock(return_value={"id": "dir-001"})
        memory.create_mental_model = AsyncMock(return_value={"id": "mm-001"})
        memory.submit_async_refresh_mental_model = AsyncMock(
            return_value={"operation_id": "op-001"},
        )
        return memory

    @pytest.mark.asyncio
    async def test_backend_python_all_config_fields_applied(self):
        """Every config field from backend-python template reaches bank config."""
        template = self._load_template_as_record("backend-python")
        memory = self._make_memory()

        result = await bootstrap_bank_from_template(
            memory=memory, bank_id="my-python-bank",
            template=template, requesting_user_id="alice",
        )

        assert result.bank_created is True
        assert result.config_applied is True
        assert result.errors == []

        # Verify bank-level mission is reflect_mission
        update_call = memory.update_bank.call_args
        assert update_call.kwargs["mission"] == template.reflect_mission

        # Verify ALL config fields propagated to bank config
        config_call = memory._config_resolver.update_bank_config.call_args
        config = config_call.args[1]

        # Core missions
        assert config["retain_mission"] == template.retain_mission
        assert "backend patterns" in config["retain_mission"].lower()
        assert config["reflect_mission"] == template.reflect_mission
        assert config["observations_mission"] == template.observations_mission

        # Extraction mode
        assert config["retain_extraction_mode"] == "verbose"

        # Entity labels
        assert "entity_labels" in config
        labels = config["entity_labels"]["attributes"]
        assert len(labels) == 1
        assert labels[0]["key"] == "domain"
        values = [v["value"] for v in labels[0]["values"]]
        assert "api-design" in values
        assert "error-handling" in values
        assert "testing" in values
        assert "data-access" in values
        assert "auth" in values

        # Free form + observations
        assert config["entities_allow_free_form"] is True
        assert config["enable_observations"] is True

        # Dispositions
        assert config["disposition_skepticism"] == 3
        assert config["disposition_literalism"] == 3
        assert config["disposition_empathy"] == 3

        # Directives created
        assert len(result.directives) == 2
        directive_names = [d.name for d in result.directives]
        assert "No PII Storage" in directive_names
        assert "Cite Sources" in directive_names
        assert all(d.created for d in result.directives)

        # Mental models created
        assert len(result.mental_models) == 3
        mm_names = [m.name for m in result.mental_models]
        assert "Python Best Practices" in mm_names
        assert "API Design Patterns" in mm_names
        assert "Testing Strategies" in mm_names
        assert all(m.created for m in result.mental_models)

    @pytest.mark.asyncio
    async def test_fullstack_typescript_all_config_fields_applied(self):
        """Every config field from fullstack-typescript template reaches bank config."""
        template = self._load_template_as_record("fullstack-typescript")
        memory = self._make_memory()

        result = await bootstrap_bank_from_template(
            memory=memory, bank_id="my-ts-bank",
            template=template, requesting_user_id="alice",
        )

        assert result.bank_created is True
        assert result.config_applied is True
        assert result.errors == []

        config_call = memory._config_resolver.update_bank_config.call_args
        config = config_call.args[1]

        # Missions present
        assert config["retain_mission"]
        assert config["reflect_mission"]
        assert config["observations_mission"]

        # Two entity labels (layer + concern)
        labels = config["entity_labels"]["attributes"]
        label_keys = [l["key"] for l in labels]
        assert "layer" in label_keys
        assert "concern" in label_keys

        # Layer label has 4 values (frontend, backend, shared, infra)
        layer = next(l for l in labels if l["key"] == "layer")
        assert len(layer["values"]) == 4

        # Non-default dispositions
        assert config["disposition_skepticism"] == 4
        assert config["disposition_empathy"] == 2

        # 3 directives, 3 mental models
        assert len(result.directives) == 3
        assert len(result.mental_models) == 3
        assert all(d.created for d in result.directives)

    @pytest.mark.asyncio
    async def test_personal_scope_template_same_config(self):
        """Personal-scope installed template applies same config as server-scope."""
        template = self._load_template_as_record("backend-python")
        # Simulate personal install
        template = template.model_copy(update={"scope": "personal", "owner": "alice"})
        memory = self._make_memory()

        result = await bootstrap_bank_from_template(
            memory=memory, bank_id="alice-python-bank",
            template=template, requesting_user_id="alice",
        )

        assert result.config_applied is True
        config_call = memory._config_resolver.update_bank_config.call_args
        config = config_call.args[1]
        # Same config regardless of scope
        assert config["retain_mission"] == template.retain_mission
        assert config["retain_extraction_mode"] == "verbose"
        assert "entity_labels" in config
