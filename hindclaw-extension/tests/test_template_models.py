"""Tests for hindclaw_ext.template_models — Catalog, CatalogEntry, TemplateScope.

The parallel Pydantic hierarchy (MarketplaceTemplate, DirectiveSeed,
MentalModelSeed, EntityLabel, EntityLabelValue, _VALID_EXTRACTION_MODES)
has been deleted. Template content validation is now performed by
upstream's BankTemplateManifest, which is exercised inline through
CatalogEntry's `manifest` field (a `BankTemplateManifest | None` typed
slot).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hindclaw_ext.template_models import Catalog, CatalogEntry, TemplateScope

# --------------------------------------------------------------------------- #
# TemplateScope
# --------------------------------------------------------------------------- #


def test_template_scope_values():
    assert TemplateScope.SERVER.value == "server"
    assert TemplateScope.PERSONAL.value == "personal"


def test_template_scope_round_trip_through_str():
    assert TemplateScope("server") is TemplateScope.SERVER
    assert TemplateScope("personal") is TemplateScope.PERSONAL


# --------------------------------------------------------------------------- #
# CatalogEntry — inline body
# --------------------------------------------------------------------------- #


def _minimal_manifest_dict() -> dict:
    return {
        "version": "1",
        "bank": {"reflect_mission": "test mission"},
    }


def test_catalog_entry_inline_parses_upstream_format():
    entry = CatalogEntry.model_validate(
        {
            "id": "starter",
            "name": "Starter",
            "description": "A starter template",
            "category": "coding",
            "integrations": ["claude-code"],
            "tags": ["python"],
            "manifest": _minimal_manifest_dict(),
        }
    )
    assert entry.id == "starter"
    assert entry.manifest is not None
    assert entry.manifest_file is None


def test_catalog_entry_reference_parses_our_format():
    entry = CatalogEntry.model_validate(
        {
            "id": "backend-python",
            "name": "Backend Python",
            "manifest_file": "templates/backend-python.json",
        }
    )
    assert entry.manifest is None
    assert entry.manifest_file == "templates/backend-python.json"


def test_catalog_entry_rejects_both_manifest_and_file():
    with pytest.raises(ValidationError) as exc:
        CatalogEntry.model_validate(
            {
                "id": "bad",
                "name": "Bad",
                "manifest": _minimal_manifest_dict(),
                "manifest_file": "templates/bad.json",
            }
        )
    assert "both 'manifest' and 'manifest_file'" in str(exc.value)


def test_catalog_entry_rejects_neither():
    with pytest.raises(ValidationError) as exc:
        CatalogEntry.model_validate({"id": "bad", "name": "Bad"})
    assert "neither 'manifest' nor 'manifest_file'" in str(exc.value)


def test_catalog_entry_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        CatalogEntry.model_validate(
            {
                "id": "bad",
                "name": "Bad",
                "manifest_file": "templates/bad.json",
                "unknown_field": "nope",
            }
        )


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #


def test_catalog_top_level_shape():
    catalog = Catalog.model_validate(
        {
            "catalog_version": "1",
            "name": "hindclaw-official",
            "description": "Official templates",
            "templates": [
                {
                    "id": "a",
                    "name": "A",
                    "manifest_file": "templates/a.json",
                },
                {
                    "id": "b",
                    "name": "B",
                    "manifest": _minimal_manifest_dict(),
                },
            ],
        }
    )
    assert catalog.catalog_version == "1"
    assert [e.id for e in catalog.templates] == ["a", "b"]


def test_catalog_rejects_unknown_top_level_fields():
    with pytest.raises(ValidationError):
        Catalog.model_validate(
            {
                "catalog_version": "1",
                "templates": [],
                "extra_field": "nope",
            }
        )


def test_catalog_accepts_minimal_shape_matching_upstream_hub():
    """Upstream hindsight-docs/src/data/templates.json carries only a top-level
    `templates` array. HindClaw's Catalog Pydantic must accept that minimal
    shape verbatim, which proves the 'zero adapter code' compatibility claim."""
    catalog = Catalog.model_validate(
        {
            "templates": [
                {
                    "id": "conversation",
                    "name": "Conversation",
                    "manifest": _minimal_manifest_dict(),
                }
            ]
        }
    )
    assert catalog.name is None
    assert len(catalog.templates) == 1


def test_catalog_accepts_upstream_templates_json_verbatim():
    """Parse the literal byte content of
    build/hindsight/.upstream/hindsight-docs/src/data/templates.json via
    Catalog.model_validate_json() with no transformation.

    Load-bearing test for the spec's 'zero adapter code' claim. Skips if
    the upstream data file is not present in the current checkout
    (e.g. shallow-submodule environments) so the test doesn't break a
    minimal clone.

    Each entry must carry EXACTLY ONE of inline manifest or manifest_file —
    upstream's PR #1066 converted their catalog to manifest_file references,
    but the assertion is framed as the invariant either side of the line.
    """
    upstream_catalog = (
        Path(__file__).resolve().parents[3]
        / "hindsight"
        / ".upstream"
        / "hindsight-docs"
        / "src"
        / "data"
        / "templates.json"
    )
    if not upstream_catalog.exists():
        pytest.skip(f"upstream catalog not present at {upstream_catalog}")
    catalog = Catalog.model_validate_json(upstream_catalog.read_text())
    assert len(catalog.templates) >= 1
    for entry in catalog.templates:
        has_inline = entry.manifest is not None
        has_ref = entry.manifest_file is not None
        assert has_inline != has_ref, (
            f"upstream catalog entry {entry.id!r} must carry exactly one of "
            f"'manifest' or 'manifest_file' (inline={has_inline}, ref={has_ref})"
        )


def test_mental_model_id_regex_matches_upstream():
    """Upstream's BankTemplateMentalModel enforces id ~= ^[a-z0-9][a-z0-9-]*$.
    Parse valid and invalid ids through upstream's own Pydantic to prove
    the HindClaw manifest wrapper inherits that constraint."""
    from hindsight_api.api.http import BankTemplateMentalModel

    good_ids = [
        "python-best-practices",
        "x",
        "a1",
        "with-many-hyphens",
        "0-starts-with-digit",
    ]
    for good in good_ids:
        BankTemplateMentalModel.model_validate({"id": good, "name": "n", "source_query": "q"})

    bad_ids = [
        "",
        "-leading-hyphen",
        "Upper",
        "with space",
        "with_underscore",
        "with/slash",
    ]
    for bad in bad_ids:
        with pytest.raises(ValidationError):
            BankTemplateMentalModel.model_validate({"id": bad, "name": "n", "source_query": "q"})


# --------------------------------------------------------------------------- #
# Regression: no reference to deleted identifiers
# --------------------------------------------------------------------------- #


def test_no_legacy_identifiers_in_template_models_module():
    import hindclaw_ext.template_models as mod

    deleted = {
        "MarketplaceTemplate",
        "DirectiveSeed",
        "MentalModelSeed",
        "EntityLabel",
        "EntityLabelValue",
        "_VALID_EXTRACTION_MODES",
    }
    assert deleted.isdisjoint(vars(mod)), (
        f"template_models still exports legacy identifiers: {deleted & vars(mod).keys()}"
    )


# --------------------------------------------------------------------------- #
# Bundled templates — drop-zone regression guards
# --------------------------------------------------------------------------- #

BUNDLED_TEMPLATE_ROOT = Path(__file__).parent.parent.parent / "hindclaw-templates" / "templates"


@pytest.mark.parametrize(
    "name",
    ["backend-python", "fullstack-typescript", "astromech-test"],
)
def test_bundled_template_parses_via_upstream_pydantic(name: str):
    from hindsight_api.api.http import BankTemplateManifest, validate_bank_template

    data = json.loads((BUNDLED_TEMPLATE_ROOT / f"{name}.json").read_text())
    manifest = BankTemplateManifest.model_validate(data)
    errors = validate_bank_template(manifest)
    assert not errors, f"{name}: {errors}"


def test_no_bundled_template_uses_verbatim_extraction_mode():
    """Regression guard — `verbatim` was dropped from HindClaw in the
    convergence refactor because upstream's validator only accepts
    concise/verbose/custom/chunks."""
    for name in ("backend-python", "fullstack-typescript", "astromech-test"):
        data = json.loads((BUNDLED_TEMPLATE_ROOT / f"{name}.json").read_text())
        mode = data.get("bank", {}).get("retain_extraction_mode")
        assert mode != "verbatim", f"{name} still uses verbatim extraction mode"
