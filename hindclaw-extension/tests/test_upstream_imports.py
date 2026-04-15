"""Drift-detection guard for the upstream Hindsight symbol surface HindClaw
imports from. Failing this test means upstream renamed, moved, or removed
a symbol that HindClaw's template layer depends on.

Single chokepoint: if this test passes, every other refactored module's
imports are guaranteed to resolve. If it fails, fix the import paths here
first, then update the rest of the codebase.
"""

from __future__ import annotations

import inspect
from dataclasses import is_dataclass

from pydantic import BaseModel


def test_bank_template_manifest_classes_are_importable_pydantic_models():
    from hindsight_api.api.http import (
        BankTemplateConfig,
        BankTemplateDirective,
        BankTemplateImportResponse,
        BankTemplateManifest,
        BankTemplateMentalModel,
        MentalModelTrigger,
    )

    for cls in (
        BankTemplateConfig,
        BankTemplateDirective,
        BankTemplateImportResponse,
        BankTemplateManifest,
        BankTemplateMentalModel,
        MentalModelTrigger,
    ):
        assert inspect.isclass(cls), f"{cls.__name__} is not a class"
        assert issubclass(cls, BaseModel), f"{cls.__name__} is not a Pydantic BaseModel subclass"


def test_bank_template_functions_are_importable_callables():
    from hindsight_api.api.http import (
        apply_bank_template_manifest,
        validate_bank_template,
    )

    assert callable(validate_bank_template), "validate_bank_template is not callable"
    assert callable(apply_bank_template_manifest), "apply_bank_template_manifest is not callable"
    assert inspect.iscoroutinefunction(apply_bank_template_manifest), (
        "apply_bank_template_manifest must be async — HindClaw awaits it"
    )


def test_bank_template_current_version_is_nonempty_string():
    from hindsight_api.api.http import BANK_TEMPLATE_CURRENT_VERSION

    assert isinstance(BANK_TEMPLATE_CURRENT_VERSION, str)
    assert BANK_TEMPLATE_CURRENT_VERSION != ""


def test_request_context_has_internal_flag():
    from hindsight_api.models import RequestContext

    assert is_dataclass(RequestContext) or issubclass(RequestContext, BaseModel), (
        "RequestContext must be a dataclass or Pydantic model (current is a dataclass in v0.5.1)"
    )
    ctx = RequestContext(internal=True)  # type: ignore[call-arg]
    assert getattr(ctx, "internal", None) is True


def test_entity_labels_symbols_are_importable():
    from hindsight_api.engine.retain.entity_labels import (
        EntityLabelsConfig,
        LabelGroup,
        LabelValue,
        parse_entity_labels,
    )

    for cls in (EntityLabelsConfig, LabelGroup, LabelValue):
        assert inspect.isclass(cls), f"{cls.__name__} is not a class"
        assert issubclass(cls, BaseModel), f"{cls.__name__} is not a Pydantic BaseModel"

    assert callable(parse_entity_labels), "parse_entity_labels is not callable"


def test_bank_template_config_has_configurable_fields_patch():
    """PR #1044's fields must be present — every subsequent refactor relies
    on these being on BankTemplateConfig. Released in upstream 0.5.2."""
    from hindsight_api.api.http import BankTemplateConfig

    required = {
        "retain_default_strategy",
        "retain_strategies",
        "retain_chunk_batch_size",
        "mcp_enabled_tools",
        "consolidation_llm_batch_size",
        "consolidation_source_facts_max_tokens",
        "consolidation_source_facts_max_tokens_per_observation",
        "max_observations_per_scope",
        "reflect_source_facts_max_tokens",
        "llm_gemini_safety_settings",
    }
    declared = set(BankTemplateConfig.model_fields.keys())
    missing = required - declared
    assert not missing, f"missing fields in BankTemplateConfig: {sorted(missing)}"
