"""Tests for template Pydantic models."""

import pytest

from hindclaw_ext.template_models import (
    DirectiveSeed,
    EntityLabel,
    EntityLabelValue,
    MentalModelSeed,
    TemplateScope,
)
from hindclaw_ext.models import TemplateRecord


class TestDirectiveSeed:
    def test_minimal(self):
        seed = DirectiveSeed(name="no-pii", content="Never store PII.")
        assert seed.name == "no-pii"
        assert seed.content == "Never store PII."
        assert seed.priority == 0
        assert seed.is_active is True

    def test_full(self):
        seed = DirectiveSeed(
            name="cite", content="Always cite.", priority=5, is_active=False
        )
        assert seed.priority == 5
        assert seed.is_active is False


class TestMentalModelSeed:
    def test_valid(self):
        seed = MentalModelSeed(name="Best Practices", source_query="What patterns?")
        assert seed.name == "Best Practices"
        assert seed.source_query == "What patterns?"


class TestEntityLabel:
    def test_value_type_requires_values(self):
        with pytest.raises(ValueError):
            EntityLabel(key="domain", type="value")

    def test_value_type_with_values(self):
        label = EntityLabel(
            key="domain",
            type="value",
            values=[EntityLabelValue(value="api", description="API design")],
        )
        assert label.key == "domain"
        assert len(label.values) == 1

    def test_text_type_no_values_needed(self):
        label = EntityLabel(key="notes", type="text")
        assert label.type == "text"
        assert label.values == []

    def test_multi_values_type(self):
        label = EntityLabel(
            key="tags",
            type="multi-values",
            values=[EntityLabelValue(value="a"), EntityLabelValue(value="b")],
        )
        assert label.type == "multi-values"

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            EntityLabel(key="x", type="categorical")

    def test_tag_field(self):
        label = EntityLabel(
            key="domain", type="value", tag=True,
            values=[EntityLabelValue(value="api")],
        )
        assert label.tag is True

    def test_defaults(self):
        label = EntityLabel(
            key="x", type="value",
            values=[EntityLabelValue(value="a")],
        )
        assert label.optional is True
        assert label.tag is False


class TestTemplateScope:
    def test_valid_scopes(self):
        assert TemplateScope.SERVER == "server"
        assert TemplateScope.PERSONAL == "personal"


class TestTemplateRecord:
    def test_minimal(self):
        rec = TemplateRecord(
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
            description="Backend patterns",
            author="community",
            tags=["python", "backend"],
            retain_mission="Extract backend patterns.",
            reflect_mission="You are a backend engineer.",
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
        assert rec.id == "backend-python"
        assert rec.scope == "server"
        assert rec.owner is None
        assert rec.source_name == "hindclaw"
