"""HindclawValidator — policy-based access control.

Replaces the 4-step boolean resolver with policy engine evaluation.
Reads request_context.tenant_id (set by HindclawTenant) and JWT claims
to evaluate access policies and enrich operations.

See spec Sections 5, 6, 9.
"""

import logging

from pydantic import TypeAdapter

from hindsight_api.engine.search.tags import TagGroup
from hindsight_api.extensions import (
    OperationValidatorExtension,
    RecallContext,
    ReflectContext,
    RetainContext,
    ValidationResult,
)

from hindclaw_ext import db
from hindclaw_ext.policy_engine import (
    AccessResult,
    evaluate_access,
    intersect_sa_policy,
    resolve_bank_strategy,
)
from hindclaw_ext.policy_models import BankPolicyDocument
from hindclaw_ext.tenant import _jwt_claims

_tag_group_adapter = TypeAdapter(list[TagGroup])

logger = logging.getLogger(__name__)


async def _resolve_user_access(user_id: str, action: str, bank_id: str) -> AccessResult:
    """Resolve a user's effective access for an action on a bank.

    Gathers the user's groups, fetches all attached policies, and evaluates.

    Args:
        user_id: Canonical user ID.
        action: The action to check (e.g., "bank:recall").
        bank_id: Target bank ID.

    Returns:
        AccessResult with allowed flag and behavioral parameters.
    """
    groups = await db.get_user_groups(user_id)
    group_ids = [g.id for g in groups]
    policies = await db.get_policies_for_user(user_id, group_ids)
    result = evaluate_access(policies, action=action, bank_id=bank_id)
    result.resolved_user_id = user_id
    return result


async def _resolve_sa_access(sa_id: str, action: str, bank_id: str) -> AccessResult:
    """Resolve a service account's effective access for an action on a bank.

    Computes parent user's effective policy, then intersects with SA's scoping
    policy if present.

    Args:
        sa_id: Service account ID (without sa: prefix).
        action: The action to check.
        bank_id: Target bank ID.

    Returns:
        AccessResult with allowed flag and behavioral parameters.
    """
    sa = await db.get_service_account(sa_id)
    if not sa or not sa.is_active:
        return AccessResult(allowed=False)

    # Check parent user is active
    parent = await db.get_user(sa.owner_user_id)
    if not parent or not parent.is_active:
        return AccessResult(allowed=False)

    # Parent's effective policy
    parent_access = await _resolve_user_access(sa.owner_user_id, action, bank_id)

    # SA scoping intersection
    if sa.scoping_policy_id:
        scoping_policy = await db.get_policy(sa.scoping_policy_id)
        if scoping_policy:
            from hindclaw_ext.models import AttachedPolicyRecord
            scoping_attached = AttachedPolicyRecord(
                id=scoping_policy.id, display_name=scoping_policy.display_name,
                document_json=scoping_policy.document_json,
                is_builtin=scoping_policy.is_builtin,
                principal_type="user", principal_id=sa.id, priority=0,
            )
            scoping_access = evaluate_access([scoping_attached], action=action, bank_id=bank_id)
            result = intersect_sa_policy(parent_access, scoping_access)
            result.resolved_user_id = sa.owner_user_id
            return result

    parent_access.resolved_user_id = sa.owner_user_id
    return parent_access


async def _resolve_public_access(bank_id: str, action: str) -> AccessResult:
    """Resolve public access for an unmapped sender on a bank.

    Checks the bank policy's public_access section for matching context.

    Args:
        bank_id: Target bank ID.
        action: The action to check.

    Returns:
        AccessResult — allowed if bank policy grants public access for this action.
    """
    claims = _jwt_claims.get({})
    bank_policy_record = await db.get_bank_policy(bank_id)
    if not bank_policy_record:
        return AccessResult(allowed=False)

    doc = BankPolicyDocument(**bank_policy_record.document_json)
    if not doc.public_access:
        return AccessResult(allowed=False)

    provider = claims.get("channel")
    channel = claims.get("channel")
    topic = claims.get("topic")

    # Match overrides (most specific wins: topic > channel > provider)
    context = {"provider": provider, "channel": channel, "topic": topic}
    scope_priority = {"provider": 1, "channel": 1, "topic": 2}

    best_match = None
    best_priority = -1

    for override in doc.public_access.overrides:
        ctx_value = context.get(override.scope)
        priority = scope_priority.get(override.scope, 0)
        if ctx_value is not None and ctx_value == override.value and priority > best_priority:
            best_match = override
            best_priority = priority

    if best_match and action in best_match.actions:
        return AccessResult(
            allowed=True,
            recall_budget=best_match.recall_budget,
            recall_max_tokens=best_match.recall_max_tokens,
        )

    if doc.public_access.default and action in doc.public_access.default.actions:
        return AccessResult(
            allowed=True,
            recall_budget=doc.public_access.default.recall_budget,
            recall_max_tokens=doc.public_access.default.recall_max_tokens,
        )

    return AccessResult(allowed=False)


class HindclawValidator(OperationValidatorExtension):
    """Enforce policy-based access control on recall/retain/reflect operations.

    Uses the policy engine from policy_engine.py. Enriches accepted operations
    with tag_groups (recall) or tags + strategy (retain) via accept_with().

    See spec Sections 5, 6, 9.
    """

    def _is_internal_server_call(self, request_context) -> bool:
        """Return True for trusted server-internal worker operations.

        Internal background jobs have no API key, no JWT claims, and tenant_id
        is None. _unmapped has a JWT (sender context) so it is NOT internal.
        """
        api_key = getattr(request_context, "api_key", None)
        tenant_id = getattr(request_context, "tenant_id", None)
        claims = _jwt_claims.get({})
        return not api_key and not claims and tenant_id is None

    async def _resolve_access(self, tenant_id: str, action: str, bank_id: str) -> AccessResult:
        """Route to the correct access resolver based on tenant_id.

        Args:
            tenant_id: From request_context (user ID, sa:XX, or _unmapped).
            action: The action to check.
            bank_id: Target bank ID.

        Returns:
            AccessResult with allowed flag and behavioral parameters.
        """
        if tenant_id == "_unmapped":
            return await _resolve_public_access(bank_id, action)
        elif tenant_id.startswith("sa:"):
            sa_id = tenant_id[3:]  # strip "sa:" prefix
            return await _resolve_sa_access(sa_id, action, bank_id)
        else:
            return await _resolve_user_access(tenant_id, action, bank_id)

    async def validate_recall(self, ctx: RecallContext) -> ValidationResult:
        """Validate a recall operation using policy evaluation.

        Args:
            ctx: RecallContext with bank_id and request_context.tenant_id.

        Returns:
            ValidationResult — accept (with optional tag_groups) or reject.
        """
        if self._is_internal_server_call(ctx.request_context):
            return ValidationResult.accept()

        tenant_id = ctx.request_context.tenant_id
        access = await self._resolve_access(tenant_id, "bank:recall", ctx.bank_id)

        if not access.allowed:
            return ValidationResult.reject(f"recall denied for {tenant_id} on {ctx.bank_id}")

        if access.recall_tag_groups is not None:
            tag_groups = _tag_group_adapter.validate_python(access.recall_tag_groups)
            return ValidationResult.accept_with(tag_groups=tag_groups)

        return ValidationResult.accept()

    async def validate_retain(self, ctx: RetainContext) -> ValidationResult:
        """Validate a retain operation using policy evaluation.

        Args:
            ctx: RetainContext with bank_id, contents, and request_context.tenant_id.

        Returns:
            ValidationResult — accept_with(contents=enriched) or reject.
        """
        if self._is_internal_server_call(ctx.request_context):
            return ValidationResult.accept()

        tenant_id = ctx.request_context.tenant_id
        access = await self._resolve_access(tenant_id, "bank:retain", ctx.bank_id)

        if not access.allowed:
            return ValidationResult.reject(f"retain denied for {tenant_id} on {ctx.bank_id}")

        # Resolve strategy: principal-level first, then bank policy
        claims = _jwt_claims.get({})
        strategy = access.retain_strategy
        if not strategy:
            bank_policy_record = await db.get_bank_policy(ctx.bank_id)
            if bank_policy_record:
                doc = BankPolicyDocument(**bank_policy_record.document_json)
                strategy = resolve_bank_strategy(
                    doc,
                    provider=claims.get("channel"),
                    channel=claims.get("channel"),
                    topic=claims.get("topic"),
                )

        # Build retain tags: policy tags + auto-injected user/agent tags
        retain_tags = list(access.retain_tags or [])
        if access.resolved_user_id:
            retain_tags.append(f"user:{access.resolved_user_id}")
        agent = claims.get("agent")
        if agent:
            retain_tags.append(f"agent:{agent}")

        # Enrich contents
        enriched = []
        for item in ctx.contents:
            enriched_item = dict(item)
            existing_tags = enriched_item.get("tags") or []
            enriched_item["tags"] = existing_tags + retain_tags
            if strategy:
                enriched_item["strategy"] = strategy
            enriched.append(enriched_item)

        return ValidationResult.accept_with(contents=enriched)

    async def validate_reflect(self, ctx: ReflectContext) -> ValidationResult:
        """Validate a reflect operation — independent of recall.

        Args:
            ctx: ReflectContext with bank_id and request_context.tenant_id.

        Returns:
            ValidationResult — accept or reject.
        """
        if self._is_internal_server_call(ctx.request_context):
            return ValidationResult.accept()

        tenant_id = ctx.request_context.tenant_id
        access = await self._resolve_access(tenant_id, "bank:reflect", ctx.bank_id)

        if not access.allowed:
            return ValidationResult.reject(f"reflect denied for {tenant_id} on {ctx.bank_id}")

        return ValidationResult.accept()
