"""Runtime-identity checks that ``hindclaw_client`` re-exports upstream classes.

These assertions are the Python analogue of the TypeScript compile-time
structural checks in ``tests/wrapper_types.test.ts``. They verify that
the wrapper's public surface is the *same class object* as the upstream
Hindsight client — not a local copy, not a subclass — so that
``isinstance(x, hindclaw_client.BankTemplateManifest)`` and
``isinstance(x, hindsight_client_api.models.BankTemplateManifest)``
return the same answer.
"""
import hindsight_client_api.models as upstream

import hindclaw_client


def test_bank_template_manifest_is_upstream() -> None:
    assert hindclaw_client.BankTemplateManifest is upstream.BankTemplateManifest


def test_bank_template_config_is_upstream() -> None:
    assert hindclaw_client.BankTemplateConfig is upstream.BankTemplateConfig


def test_bank_template_directive_is_upstream() -> None:
    assert hindclaw_client.BankTemplateDirective is upstream.BankTemplateDirective


def test_bank_template_mental_model_is_upstream() -> None:
    assert hindclaw_client.BankTemplateMentalModel is upstream.BankTemplateMentalModel


def test_mental_model_trigger_input_is_upstream() -> None:
    # Upstream's Pydantic v2 schema split produces two MentalModelTrigger
    # variants because TagGroup is a recursive alias union — validation
    # (Input) and serialization (Output) schemas diverge. The wrapper
    # re-exports both variants; each must be runtime-identical to the
    # upstream class.
    assert hindclaw_client.MentalModelTriggerInput is upstream.MentalModelTriggerInput


def test_mental_model_trigger_output_is_upstream() -> None:
    assert hindclaw_client.MentalModelTriggerOutput is upstream.MentalModelTriggerOutput


def test_bank_template_import_response_is_upstream() -> None:
    assert (
        hindclaw_client.BankTemplateImportResponse is upstream.BankTemplateImportResponse
    )
