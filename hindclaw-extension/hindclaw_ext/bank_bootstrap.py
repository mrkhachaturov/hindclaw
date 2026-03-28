"""In-process bank bootstrap from template using Hindsight MemoryEngine.

Calls the MemoryEngine directly instead of looping back through HTTP.
Uses RequestContext(internal=True) to bypass tenant authentication —
the HindClaw HTTP endpoint has already authenticated and authorized
the request before calling this module.

The MemoryEngine is received from get_router(self, memory) and passed
through from the HTTP endpoint.
"""

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from hindclaw_ext.http_models import DirectiveSeedResult, MentalModelSeedResult
from hindclaw_ext.models import TemplateRecord

if TYPE_CHECKING:
    from hindsight_api.engine.memory_engine import MemoryEngine

logger = logging.getLogger(__name__)


class BankBootstrapResult(BaseModel):
    """Result of bootstrapping a bank from a template."""

    bank_created: bool = False
    config_applied: bool = False
    directives: list[DirectiveSeedResult] = Field(default_factory=list)
    mental_models: list[MentalModelSeedResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _make_internal_context() -> "RequestContext":
    """Create an internal RequestContext for in-process engine calls.

    Uses internal=True with tenant_id=None so that both the Hindsight
    engine (skips tenant auth) and the HindClaw validator (_is_internal_server_call)
    treat these calls as trusted server-internal operations.

    Attribution is handled via logging in the caller, not via tenant_id.

    Returns:
        RequestContext with internal=True and tenant_id=None.
    """
    from hindsight_api.models import RequestContext

    return RequestContext(internal=True)


async def bootstrap_bank_from_template(
    *,
    memory: "MemoryEngine",
    bank_id: str,
    template: TemplateRecord,
    requesting_user_id: str,
    bank_name: str | None = None,
) -> BankBootstrapResult:
    """Bootstrap a Hindsight bank from a template using in-process engine calls.

    Performs all bank setup steps in sequence:
    1. Create/update the bank (get_bank_profile auto-creates, then update_bank)
    2. Apply config overrides (entity labels, retention settings, etc.)
    3. Create directives from seeds
    4. Create mental models from seeds

    Bank creation failure (step 1) raises the exception immediately.
    Subsequent step failures are recorded in the result but don't stop
    remaining steps.

    Args:
        memory: The in-process MemoryEngine instance.
        bank_id: Bank identifier to create.
        template: The template to bootstrap from.
        requesting_user_id: User ID for attribution (logged, not set as tenant_id).
        bank_name: Optional custom bank name (defaults to template.id).

    Returns:
        BankBootstrapResult with status of each step.

    Raises:
        Exception: If bank creation (step 1) fails.
    """
    ctx = _make_internal_context()
    result = BankBootstrapResult()
    errors: list[str] = []

    logger.info(
        "Bootstrapping bank '%s' from template '%s' (requested by %s)",
        bank_id, template.id, requesting_user_id,
    )

    # Step 1: Create/update bank — failure here is fatal
    name = bank_name or template.id
    await memory.get_bank_profile(bank_id, request_context=ctx)
    await memory.update_bank(
        bank_id,
        name=name,
        mission=template.reflect_mission or name,
        request_context=ctx,
    )
    result.bank_created = True

    # Step 2: Apply config overrides
    config_updates: dict[str, Any] = {}

    if template.retain_mission:
        config_updates["retain_mission"] = template.retain_mission
    if template.reflect_mission:
        config_updates["reflect_mission"] = template.reflect_mission
    if template.observations_mission:
        config_updates["observations_mission"] = template.observations_mission
    if template.retain_extraction_mode:
        config_updates["retain_extraction_mode"] = template.retain_extraction_mode
    if template.retain_custom_instructions:
        config_updates["retain_custom_instructions"] = template.retain_custom_instructions
    if template.retain_chunk_size is not None:
        config_updates["retain_chunk_size"] = template.retain_chunk_size
    if template.retain_default_strategy:
        config_updates["retain_default_strategy"] = template.retain_default_strategy
    if template.retain_strategies:
        config_updates["retain_strategies"] = template.retain_strategies
    if template.entity_labels:
        config_updates["entity_labels"] = {"attributes": template.entity_labels}
    config_updates["entities_allow_free_form"] = template.entities_allow_free_form
    if template.enable_observations is not None:
        config_updates["enable_observations"] = template.enable_observations
    if template.consolidation_llm_batch_size is not None:
        config_updates["consolidation_llm_batch_size"] = template.consolidation_llm_batch_size
    if template.consolidation_source_facts_max_tokens is not None:
        config_updates["consolidation_source_facts_max_tokens"] = template.consolidation_source_facts_max_tokens
    if template.consolidation_source_facts_max_tokens_per_observation is not None:
        config_updates["consolidation_source_facts_max_tokens_per_observation"] = template.consolidation_source_facts_max_tokens_per_observation
    config_updates["disposition_skepticism"] = template.disposition_skepticism
    config_updates["disposition_literalism"] = template.disposition_literalism
    config_updates["disposition_empathy"] = template.disposition_empathy

    result.config_applied = True
    if config_updates:
        try:
            await memory._config_resolver.update_bank_config(bank_id, config_updates, ctx)
        except Exception as e:
            logger.error("Config update failed for %s: %s", bank_id, e)
            errors.append(f"Config update failed: {e}")
            result.config_applied = False

    # Step 3: Create directives from seeds
    for seed in template.directive_seeds:
        try:
            dir_result = await memory.create_directive(
                bank_id,
                name=seed.get("name", ""),
                content=seed.get("content", ""),
                priority=seed.get("priority", 0),
                is_active=seed.get("is_active", True),
                request_context=ctx,
            )
            result.directives.append(DirectiveSeedResult(
                name=seed.get("name", ""),
                created=True,
                directive_id=dir_result.get("id"),
            ))
        except Exception as e:
            logger.error("Directive '%s' failed for %s: %s", seed.get("name"), bank_id, e)
            errors.append(f"Directive '{seed.get('name')}' failed: {e}")
            result.directives.append(DirectiveSeedResult(
                name=seed.get("name", ""),
                created=False,
                error=str(e),
            ))

    # Step 4: Create mental models from seeds and schedule async refresh
    for seed in template.mental_model_seeds:
        try:
            mm_result = await memory.create_mental_model(
                bank_id,
                name=seed.get("name", ""),
                source_query=seed.get("source_query", ""),
                content="Generating content...",
                request_context=ctx,
            )
            mm_id = mm_result.get("id")
            # Schedule async refresh to generate real content (matches
            # Hindsight HTTP behavior — create placeholder then queue refresh
            # as one atomic operation)
            refresh = await memory.submit_async_refresh_mental_model(
                bank_id, mm_id, request_context=ctx,
            )
            result.mental_models.append(MentalModelSeedResult(
                name=seed.get("name", ""),
                created=True,
                mental_model_id=mm_id,
                operation_id=refresh.get("operation_id"),
            ))
        except Exception as e:
            logger.error("Mental model '%s' failed for %s: %s", seed.get("name"), bank_id, e)
            errors.append(f"Mental model '{seed.get('name')}' failed: {e}")
            result.mental_models.append(MentalModelSeedResult(
                name=seed.get("name", ""),
                created=False,
                error=str(e),
            ))

    result.errors = errors
    return result
