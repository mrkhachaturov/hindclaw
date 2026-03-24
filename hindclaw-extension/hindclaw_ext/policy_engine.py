"""Policy evaluation engine — gather, match, merge, deny, SA intersection.

Implements the MinIO-style access model from spec Section 5. Replaces
the 4-step boolean merge in resolver.py.
"""

from __future__ import annotations

from pydantic import BaseModel

from hindclaw_ext.models import AttachedPolicyRecord
from hindclaw_ext.policy_models import PolicyDocument, PolicyStatement

# Budget ordering for merge rules
_BUDGET_ORDER = {"low": 0, "mid": 1, "high": 2}

# Core action → implicit extended actions
_CORE_ACTION_GRANTS = {
    "bank:recall": {"bank:memories:list", "bank:memories:get"},
}

# Principal type specificity (user > group)
_PRINCIPAL_SPECIFICITY = {"user": 2, "group": 1}


class AccessResult(BaseModel):
    """Result of policy evaluation for a single action + bank.

    Contains the access decision and merged behavioral parameters.
    """

    allowed: bool = False
    resolved_user_id: str | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    retain_strategy: str | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None


def bank_matches(bank_id: str, pattern: str) -> bool:
    """Check if a bank ID matches a policy statement's bank pattern.

    Matching rules:
      - ``*`` matches all banks
      - ``"yoda"`` matches exactly ``"yoda"``
      - ``"yoda::*"`` matches banks starting with ``"yoda::"`` (children only,
        not the base bank ``"yoda"`` itself)

    Args:
        bank_id: Actual bank ID from the request.
        pattern: Bank pattern from a policy statement.

    Returns:
        True if the bank ID matches the pattern.
    """
    if pattern == "*":
        return True
    if pattern.endswith("::*"):
        prefix = pattern[:-1]  # "yoda::*" -> "yoda::"
        return bank_id.startswith(prefix)
    return bank_id == pattern


def bank_specificity(pattern: str) -> int:
    """Return specificity rank of a bank pattern.

    Higher value = more specific. Used for tie-breaking when multiple
    statements match the same bank.

    Args:
        pattern: Bank pattern from a policy statement.

    Returns:
        Integer specificity rank (exact=3, prefix=2, wildcard=1).
    """
    if pattern == "*":
        return 1
    if pattern.endswith("::*"):
        return 2
    return 3


def _action_matches(requested: str, granted: str) -> bool:
    """Check if a requested action is covered by a granted action.

    Args:
        requested: The action being checked (e.g., "bank:recall").
        granted: The action in the policy statement (e.g., "bank:*").

    Returns:
        True if the granted action covers the requested action.
    """
    if granted == requested:
        return True
    # Wildcard: bank:* matches any bank:... action
    if granted.endswith(":*") and requested.startswith(granted[:-1]):
        return True
    # Core action grants: bank:recall -> bank:memories:list, etc.
    if granted in _CORE_ACTION_GRANTS and requested in _CORE_ACTION_GRANTS[granted]:
        return True
    return False


def evaluate_access(
    policies: list[AttachedPolicyRecord],
    action: str,
    bank_id: str,
) -> AccessResult:
    """Evaluate access policies for a specific action on a specific bank.

    Gathers matching allow/deny statements from all policies, applies
    merge rules for behavioral parameters, and applies deny-overrides-allow.

    Args:
        policies: List of AttachedPolicyRecord from db.get_policies_for_user().
        action: The action being checked (e.g., "bank:recall").
        bank_id: The target bank ID.

    Returns:
        AccessResult with allowed flag and merged behavioral parameters.
    """
    # Collect all matching statements with their metadata
    allows: list[tuple[PolicyStatement, int, int, int, str]] = []
    has_deny = False

    for policy_data in policies:
        doc = PolicyDocument(**policy_data.document_json)
        principal_type = policy_data.principal_type
        priority = policy_data.priority
        principal_spec = _PRINCIPAL_SPECIFICITY.get(principal_type, 0)

        for stmt in doc.statements:
            # Check if statement matches action + bank
            action_match = any(_action_matches(action, a) for a in stmt.actions)
            bank_match = any(bank_matches(bank_id, b) for b in stmt.banks)

            if not action_match or not bank_match:
                continue

            if stmt.effect == "deny":
                has_deny = True
                break
            elif stmt.effect == "allow":
                matching_specs = [bank_specificity(b) for b in stmt.banks if bank_matches(bank_id, b)]
                best_bank_spec = max(matching_specs) if matching_specs else 0
                allows.append((stmt, principal_spec, best_bank_spec, priority, policy_data.id))

        if has_deny:
            break

    if has_deny or not allows:
        return AccessResult(allowed=False)

    # Merge behavioral parameters from all matching allow statements
    result = AccessResult(allowed=True)

    # Additive fields: merge from ALL matching statements
    all_tag_groups: list[dict] = []
    all_retain_roles: set[str] = set()
    all_retain_tags: set[str] = set()
    all_exclude_providers: set[str] = set()
    best_budget: str | None = None
    best_max_tokens: int | None = None
    best_every_n: int | None = None

    # Single-value fields: track best source by (principal_spec, bank_spec, priority, policy_id)
    best_llm_model: tuple[tuple[int, int, int, str], str | None] = ((-1, -1, -1, ""), None)
    best_llm_provider: tuple[tuple[int, int, int, str], str | None] = ((-1, -1, -1, ""), None)
    best_strategy: tuple[tuple[int, int, int, str], str | None] = ((-1, -1, -1, ""), None)

    for stmt, principal_spec, best_bank_spec, priority, policy_id in allows:
        specificity_key = (principal_spec, best_bank_spec, priority, policy_id)

        # Additive: recall_budget — most permissive
        if stmt.recall_budget is not None:
            if best_budget is None or _BUDGET_ORDER.get(stmt.recall_budget, 0) > _BUDGET_ORDER.get(best_budget, 0):
                best_budget = stmt.recall_budget

        # Additive: recall_max_tokens — highest
        if stmt.recall_max_tokens is not None:
            best_max_tokens = max(best_max_tokens or 0, stmt.recall_max_tokens)

        # Additive: recall_tag_groups — collected
        if stmt.recall_tag_groups is not None:
            all_tag_groups.extend(stmt.recall_tag_groups)

        # Additive: retain_roles — union
        if stmt.retain_roles is not None:
            all_retain_roles.update(stmt.retain_roles)

        # Additive: retain_tags — union
        if stmt.retain_tags is not None:
            all_retain_tags.update(stmt.retain_tags)

        # Additive: exclude_providers — union
        if stmt.exclude_providers is not None:
            all_exclude_providers.update(stmt.exclude_providers)

        # Additive: retain_every_n_turns — lowest (most frequent)
        if stmt.retain_every_n_turns is not None:
            if best_every_n is None or stmt.retain_every_n_turns < best_every_n:
                best_every_n = stmt.retain_every_n_turns

        # Single-value: llm_model — most specific wins
        if stmt.llm_model is not None and specificity_key > best_llm_model[0]:
            best_llm_model = (specificity_key, stmt.llm_model)

        # Single-value: llm_provider — most specific wins
        if stmt.llm_provider is not None and specificity_key > best_llm_provider[0]:
            best_llm_provider = (specificity_key, stmt.llm_provider)

        # Single-value: retain_strategy — most specific wins
        if stmt.retain_strategy is not None and specificity_key > best_strategy[0]:
            best_strategy = (specificity_key, stmt.retain_strategy)

    result.recall_budget = best_budget
    result.recall_max_tokens = best_max_tokens
    result.recall_tag_groups = all_tag_groups if all_tag_groups else None
    result.retain_roles = sorted(all_retain_roles) if all_retain_roles else None
    result.retain_tags = sorted(all_retain_tags) if all_retain_tags else None
    result.exclude_providers = sorted(all_exclude_providers) if all_exclude_providers else None
    result.retain_every_n_turns = best_every_n
    result.llm_model = best_llm_model[1]
    result.llm_provider = best_llm_provider[1]
    result.retain_strategy = best_strategy[1]

    return result
