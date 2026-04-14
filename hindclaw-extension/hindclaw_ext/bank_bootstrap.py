"""Bank template application via upstream's in-process functions.

The HindClaw extension runs in-process inside the Hindsight server. Calling
upstream's HTTP endpoints from here hits the auth wall documented in the
2026-03-28 bank-bootstrap refactor: HindclawTenant.authenticate() rejects
token-less internal calls. We import upstream's template apply function
directly and invoke it with RequestContext(internal=True) — the same pattern
Hindsight uses for its own background workers and default-template-on-create
hook (HINDSIGHT_API_DEFAULT_BANK_TEMPLATE).

History: this module was rewritten when upstream's apply_bank_template_manifest()
became importable in v0.5.0. Prior to that, HindClaw had to call MemoryEngine
methods one at a time because upstream had no unified template apply function.
"""

from __future__ import annotations

from hindsight_api.api.http import (  # type: ignore[attr-defined]
    BankTemplateImportResponse,
    BankTemplateManifest,
    apply_bank_template_manifest,
    validate_bank_template,
)
from hindsight_api.models import RequestContext  # type: ignore[attr-defined]

from hindclaw_ext.models import TemplateRecord


async def bootstrap_bank_from_template(
    memory,
    bank_id: str,
    template: TemplateRecord,
    request_context: RequestContext,
    *,
    bank_name: str | None = None,
) -> BankTemplateImportResponse:
    """Create-or-touch a bank, set its display metadata, and apply a stored template manifest.

    Bank existence is handled with the documented upstream primitives:
    ``get_bank_profile(bank_id)`` auto-creates the row if missing;
    ``update_bank()`` then sets the caller-supplied name and an initial
    mission. There is NO ``create_or_update_bank()`` method on
    ``MemoryEngine`` — this function intentionally uses the same
    ``get_bank_profile`` + ``update_bank`` pair the pre-convergence
    ``bank_bootstrap.py`` used. After bank metadata is in place,
    upstream's ``apply_bank_template_manifest()`` handles config
    overrides, directive upserts (by name), mental model upserts
    (by id), and async refresh scheduling in one coordinated pass.

    Args:
        memory: MemoryEngine instance from get_router(self, memory).
        bank_id: ID of the bank to create or touch.
        template: The installed TemplateRecord containing the stored
            BankTemplateManifest as a dict.
        request_context: Must have internal=True so the engine bypasses
            HindclawTenant.authenticate() for this internal call.
        bank_name: Optional caller-supplied display name. Defaults to
            template.id when omitted.

    Returns:
        BankTemplateImportResponse from upstream — counts of
        created/updated entities plus operation IDs for async
        mental model refreshes.

    Raises:
        ValueError: if the stored manifest fails Pydantic parsing or
            upstream's semantic validation.
    """
    try:
        manifest = BankTemplateManifest.model_validate(template.manifest)
    except Exception as exc:
        raise ValueError(f"Template '{template.id}' has invalid manifest: {exc}") from exc

    errors = validate_bank_template(manifest)
    if errors:
        raise ValueError(f"Template '{template.id}' has invalid manifest: {'; '.join(errors)}")

    await memory.get_bank_profile(bank_id, request_context=request_context)

    name = bank_name or template.id
    initial_mission = (manifest.bank.reflect_mission if manifest.bank else None) or bank_id
    await memory.update_bank(
        bank_id,
        name=name,
        mission=initial_mission,
        request_context=request_context,
    )

    return await apply_bank_template_manifest(
        memory=memory,
        bank_id=bank_id,
        manifest=manifest,
        request_context=request_context,
    )


__all__ = ["bootstrap_bank_from_template"]
