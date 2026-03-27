"""Tests for MarketplaceTemplate model (raw marketplace JSON parsing)."""

import pytest
from pydantic import ValidationError

from hindclaw_ext.template_models import MarketplaceTemplate


def _valid_template(**overrides) -> dict:
    """Build a valid marketplace template JSON dict."""
    defaults = {
        "schema_version": 1,
        "min_hindclaw_version": "0.2.0",
        "min_hindsight_version": "0.4.20",
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
    defaults.update(overrides)
    return defaults


class TestMarketplaceTemplateValid:
    def test_minimal(self):
        t = MarketplaceTemplate(**_valid_template())
        assert t.name == "backend-python"
        assert t.version == "2.1.0"
        assert t.schema_version == 1

    def test_with_entity_labels(self):
        t = MarketplaceTemplate(**_valid_template(
            entity_labels=[{
                "key": "domain",
                "type": "value",
                "values": [{"value": "api", "description": "API patterns"}],
            }],
        ))
        assert len(t.entity_labels) == 1
        assert t.entity_labels[0].key == "domain"

    def test_with_directive_seeds(self):
        t = MarketplaceTemplate(**_valid_template(
            directive_seeds=[
                {"name": "No PII", "content": "Never store PII."},
            ],
        ))
        assert len(t.directive_seeds) == 1
        assert t.directive_seeds[0].name == "No PII"

    def test_with_mental_model_seeds(self):
        t = MarketplaceTemplate(**_valid_template(
            mental_model_seeds=[
                {"name": "Patterns", "source_query": "What patterns exist?"},
            ],
        ))
        assert len(t.mental_model_seeds) == 1

    def test_custom_extraction_mode_with_instructions(self):
        t = MarketplaceTemplate(**_valid_template(
            retain_extraction_mode="custom",
            retain_custom_instructions="Extract only architecture decisions.",
        ))
        assert t.retain_extraction_mode == "custom"


class TestMarketplaceTemplateInvalid:
    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**_valid_template(unknown_field="bad"))

    def test_missing_name(self):
        data = _valid_template()
        del data["name"]
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**data)

    def test_missing_version(self):
        data = _valid_template()
        del data["version"]
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**data)

    def test_invalid_extraction_mode(self):
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**_valid_template(retain_extraction_mode="invalid"))

    def test_disposition_out_of_range(self):
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**_valid_template(disposition_skepticism=6))

    def test_custom_mode_without_instructions(self):
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**_valid_template(
                retain_extraction_mode="custom",
                retain_custom_instructions=None,
            ))

    def test_instructions_without_custom_mode(self):
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**_valid_template(
                retain_extraction_mode="verbose",
                retain_custom_instructions="Some instructions",
            ))

    def test_invalid_schema_version(self):
        # schema_version must be a positive integer
        with pytest.raises(ValidationError):
            MarketplaceTemplate(**_valid_template(schema_version=0))
