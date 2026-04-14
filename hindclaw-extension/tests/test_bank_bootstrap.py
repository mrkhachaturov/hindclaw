"""Tests for the post-convergence bank_bootstrap module.

The module delegates all template-apply work to upstream's
apply_bank_template_manifest() via RequestContext(internal=True).
HindClaw's only responsibility is:
  1. Parse the stored JSONB as BankTemplateManifest
  2. Run validate_bank_template() for semantic checks
  3. Touch the bank via get_bank_profile + update_bank
  4. Delegate to apply_bank_template_manifest()
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hindsight_api.models import RequestContext

from hindclaw_ext.bank_bootstrap import bootstrap_bank_from_template
from hindclaw_ext.models import TemplateRecord
from hindclaw_ext.template_models import TemplateScope

pytestmark = pytest.mark.asyncio


def _record(manifest: dict | None = None) -> TemplateRecord:
    now = datetime.now(timezone.utc)
    return TemplateRecord(
        id="backend-python",
        scope=TemplateScope.PERSONAL,
        owner="user-1",
        source_name="hindclaw-official",
        source_scope=TemplateScope.SERVER,
        source_owner=None,
        source_template_id="backend-python",
        source_url="https://example.com/raw",
        source_revision="etag-1",
        name="Backend Python",
        description="d",
        category="coding",
        integrations=["claude-code"],
        tags=["python"],
        manifest=manifest
        or {
            "version": "1",
            "bank": {
                "reflect_mission": "m",
                "retain_mission": "r",
                "retain_extraction_mode": "verbose",
            },
            "directives": [],
            "mental_models": [],
        },
        installed_at=now,
        updated_at=now,
    )


async def test_bootstrap_parses_manifest_and_touches_bank():
    memory = MagicMock()
    memory.get_bank_profile = AsyncMock(return_value={"bank_id": "my-bank"})
    memory.update_bank = AsyncMock(return_value={"bank_id": "my-bank"})

    ctx = RequestContext(internal=True)  # type: ignore[call-arg]

    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value={"updated": True}),
    ) as apply_mock:
        result = await bootstrap_bank_from_template(
            memory,
            bank_id="my-bank",
            template=_record(),
            request_context=ctx,
        )

    assert result == {"updated": True}
    memory.get_bank_profile.assert_awaited_once()
    # No bank_name override → update_bank must NOT be called. Touching
    # the existing bank's name with a derived default would clobber the
    # user's chosen name (Plan B convergence finding #3 fix).
    memory.update_bank.assert_not_called()
    apply_mock.assert_awaited_once()


async def test_bootstrap_passes_internal_context_to_apply():
    memory = MagicMock()
    memory.get_bank_profile = AsyncMock()
    memory.update_bank = AsyncMock()

    ctx = RequestContext(internal=True)  # type: ignore[call-arg]

    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value=None),
    ) as apply_mock:
        await bootstrap_bank_from_template(
            memory,
            bank_id="my-bank",
            template=_record(),
            request_context=ctx,
        )

    _, kwargs = apply_mock.call_args
    assert kwargs["request_context"] is ctx
    assert kwargs["request_context"].internal is True


async def test_bootstrap_raises_on_semantic_validation_failure():
    bad = {
        "version": "1",
        "mental_models": [
            {"id": "x", "name": "X", "source_query": "q"},
            {"id": "x", "name": "Y", "source_query": "q"},
        ],
    }
    memory = MagicMock()
    memory.get_bank_profile = AsyncMock()
    memory.update_bank = AsyncMock()

    ctx = RequestContext(internal=True)  # type: ignore[call-arg]

    with pytest.raises(ValueError) as exc:
        await bootstrap_bank_from_template(
            memory,
            bank_id="my-bank",
            template=_record(manifest=bad),
            request_context=ctx,
        )
    assert "backend-python" in str(exc.value)


async def test_bootstrap_passes_caller_supplied_bank_name_to_update_bank():
    memory = MagicMock()
    memory.get_bank_profile = AsyncMock()
    memory.update_bank = AsyncMock()

    ctx = RequestContext(internal=True)  # type: ignore[call-arg]

    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value=None),
    ):
        await bootstrap_bank_from_template(
            memory,
            bank_id="my-bank",
            template=_record(),
            request_context=ctx,
            bank_name="Custom Name",
        )

    update_args = memory.update_bank.call_args
    assert update_args.kwargs["name"] == "Custom Name"
    # mission must NOT be set directly — apply_bank_template_manifest
    # routes manifest.bank.reflect_mission through the config layer.
    assert "mission" not in update_args.kwargs


async def test_bootstrap_does_not_touch_name_when_bank_name_is_omitted():
    memory = MagicMock()
    memory.get_bank_profile = AsyncMock()
    memory.update_bank = AsyncMock()

    ctx = RequestContext(internal=True)  # type: ignore[call-arg]

    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value=None),
    ):
        await bootstrap_bank_from_template(
            memory,
            bank_id="my-bank",
            template=_record(),
            request_context=ctx,
        )

    memory.update_bank.assert_not_called()
