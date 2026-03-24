"""Tests for the policy evaluation engine."""


def test_exact_match():
    """Exact bank ID match."""
    from hindclaw_ext.policy_engine import bank_matches

    assert bank_matches("yoda", "yoda") is True
    assert bank_matches("yoda", "r2d2") is False


def test_wildcard_match():
    """Star matches all banks."""
    from hindclaw_ext.policy_engine import bank_matches

    assert bank_matches("yoda", "*") is True
    assert bank_matches("r2d2", "*") is True


def test_prefix_match():
    """Prefix wildcard matches children only."""
    from hindclaw_ext.policy_engine import bank_matches

    assert bank_matches("yoda::group:-100::276", "yoda::*") is True
    assert bank_matches("yoda::dm::276", "yoda::*") is True
    assert bank_matches("yoda", "yoda::*") is False  # base bank not matched
    assert bank_matches("r2d2::group:-200", "yoda::*") is False


def test_bank_specificity():
    """Specificity ranking: exact > prefix > wildcard."""
    from hindclaw_ext.policy_engine import bank_specificity

    assert bank_specificity("yoda") > bank_specificity("yoda::*")
    assert bank_specificity("yoda::*") > bank_specificity("*")


def test_evaluate_allows_recall():
    """Allow statement grants recall on matching bank."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access
    from hindclaw_ext.policy_models import PolicyDocument

    doc = PolicyDocument(version="2026-03-24", statements=[
        {"effect": "allow", "actions": ["bank:recall"], "banks": ["yoda"]},
    ])
    policies = [AttachedPolicyRecord(id="test", display_name="Test", document_json=doc.model_dump(), principal_type="user", principal_id="alice", priority=0)]

    result = evaluate_access(policies, action="bank:recall", bank_id="yoda")
    assert result.allowed is True


def test_evaluate_deny_overrides_allow():
    """Deny overrides allow for same action+bank."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access
    from hindclaw_ext.policy_models import PolicyDocument

    doc = PolicyDocument(version="2026-03-24", statements=[
        {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"]},
        {"effect": "deny", "actions": ["bank:recall"], "banks": ["r2d2"]},
    ])
    policies = [AttachedPolicyRecord(id="test", display_name="Test", document_json=doc.model_dump(), principal_type="user", principal_id="alice", priority=0)]

    result = evaluate_access(policies, action="bank:recall", bank_id="r2d2")
    assert result.allowed is False


def test_evaluate_no_matching_statement():
    """No matching statement means denied."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access
    from hindclaw_ext.policy_models import PolicyDocument

    doc = PolicyDocument(version="2026-03-24", statements=[
        {"effect": "allow", "actions": ["bank:recall"], "banks": ["yoda"]},
    ])
    policies = [AttachedPolicyRecord(id="test", display_name="Test", document_json=doc.model_dump(), principal_type="user", principal_id="alice", priority=0)]

    result = evaluate_access(policies, action="bank:recall", bank_id="r2d2")
    assert result.allowed is False


def test_evaluate_merges_behavioral_params():
    """Behavioral params merged from multiple policies."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access

    policies = [
        AttachedPolicyRecord(
            id="default-access", display_name="Default",
            document_json={"version": "2026-03-24", "statements": [
                {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"], "recall_budget": "mid", "recall_max_tokens": 1024},
            ]},
            principal_type="group", principal_id="default", priority=0,
        ),
        AttachedPolicyRecord(
            id="executive-upgrade", display_name="Executive",
            document_json={"version": "2026-03-24", "statements": [
                {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"], "recall_budget": "high", "recall_max_tokens": 2048},
            ]},
            principal_type="group", principal_id="executive", priority=10,
        ),
    ]

    result = evaluate_access(policies, action="bank:recall", bank_id="yoda")
    assert result.allowed is True
    assert result.recall_budget == "high"  # most permissive
    assert result.recall_max_tokens == 2048  # highest


def test_evaluate_priority_breaks_tie_for_scalar():
    """Higher priority wins for single-value fields (llm_model)."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access

    policies = [
        AttachedPolicyRecord(
            id="default-access", display_name="Default",
            document_json={"version": "2026-03-24", "statements": [
                {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"], "llm_model": "gpt-4o-mini"},
            ]},
            principal_type="group", principal_id="default", priority=0,
        ),
        AttachedPolicyRecord(
            id="executive-upgrade", display_name="Executive",
            document_json={"version": "2026-03-24", "statements": [
                {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"], "llm_model": "claude-sonnet-4-6"},
            ]},
            principal_type="group", principal_id="executive", priority=10,
        ),
    ]

    result = evaluate_access(policies, action="bank:recall", bank_id="yoda")
    assert result.llm_model == "claude-sonnet-4-6"  # priority 10 > 0


def test_evaluate_user_beats_group():
    """User-attached policy beats group-attached for single-value fields."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access

    policies = [
        AttachedPolicyRecord(
            id="default-access", display_name="Default",
            document_json={"version": "2026-03-24", "statements": [
                {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"], "llm_model": "gpt-4o-mini"},
            ]},
            principal_type="group", principal_id="default", priority=100,
        ),
        AttachedPolicyRecord(
            id="alice-override", display_name="Alice Override",
            document_json={"version": "2026-03-24", "statements": [
                {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"], "llm_model": "claude-opus-4-6"},
            ]},
            principal_type="user", principal_id="alice", priority=0,
        ),
    ]

    result = evaluate_access(policies, action="bank:recall", bank_id="yoda")
    assert result.llm_model == "claude-opus-4-6"  # user > group regardless of priority


def test_evaluate_action_wildcard():
    """bank:* matches any bank action."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access

    policies = [AttachedPolicyRecord(
        id="admin", display_name="Admin",
        document_json={"version": "2026-03-24", "statements": [
            {"effect": "allow", "actions": ["bank:*"], "banks": ["*"]},
        ]},
        principal_type="user", principal_id="alice", priority=0,
    )]

    result = evaluate_access(policies, action="bank:memories:delete", bank_id="yoda")
    assert result.allowed is True


def test_evaluate_core_action_grants_extended():
    """bank:recall implicitly grants bank:memories:list and bank:memories:get."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access

    policies = [AttachedPolicyRecord(
        id="readonly", display_name="Read Only",
        document_json={"version": "2026-03-24", "statements": [
            {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"]},
        ]},
        principal_type="user", principal_id="alice", priority=0,
    )]

    assert evaluate_access(policies, action="bank:memories:list", bank_id="yoda").allowed is True
    assert evaluate_access(policies, action="bank:memories:get", bank_id="yoda").allowed is True
    assert evaluate_access(policies, action="bank:memories:delete", bank_id="yoda").allowed is False


def test_evaluate_iam_wildcard():
    """iam:* matches any iam action."""
    from hindclaw_ext.models import AttachedPolicyRecord
    from hindclaw_ext.policy_engine import evaluate_access

    policies = [AttachedPolicyRecord(
        id="iam-admin", display_name="IAM Admin",
        document_json={"version": "2026-03-24", "statements": [
            {"effect": "allow", "actions": ["iam:*"], "banks": ["*"]},
        ]},
        principal_type="user", principal_id="alice", priority=0,
    )]

    result = evaluate_access(policies, action="iam:users:read", bank_id="")
    assert result.allowed is True


def test_sa_intersect_narrows_actions():
    """SA scoping policy removes actions not in scoping policy."""
    from hindclaw_ext.policy_engine import intersect_sa_policy, AccessResult

    parent = AccessResult(allowed=True, recall_budget="high", recall_max_tokens=2048)
    scoping = AccessResult(allowed=True, recall_budget="mid", recall_max_tokens=1024)

    result = intersect_sa_policy(parent, scoping)
    assert result.allowed is True
    assert result.recall_budget == "mid"  # more restrictive
    assert result.recall_max_tokens == 1024  # lower


def test_sa_intersect_denied_parent():
    """If parent denies, SA is denied."""
    from hindclaw_ext.policy_engine import intersect_sa_policy, AccessResult

    parent = AccessResult(allowed=False)
    scoping = AccessResult(allowed=True, recall_budget="high")

    result = intersect_sa_policy(parent, scoping)
    assert result.allowed is False


def test_sa_intersect_denied_scoping():
    """If scoping denies, SA is denied."""
    from hindclaw_ext.policy_engine import intersect_sa_policy, AccessResult

    parent = AccessResult(allowed=True, recall_budget="high")
    scoping = AccessResult(allowed=False)

    result = intersect_sa_policy(parent, scoping)
    assert result.allowed is False


def test_sa_intersect_roles():
    """Retain roles are intersected (only roles in both)."""
    from hindclaw_ext.policy_engine import intersect_sa_policy, AccessResult

    parent = AccessResult(allowed=True, retain_roles=["user", "assistant", "system"])
    scoping = AccessResult(allowed=True, retain_roles=["user", "assistant"])

    result = intersect_sa_policy(parent, scoping)
    assert result.retain_roles == ["assistant", "user"]  # sorted intersection


def test_sa_intersect_scoping_strategy_wins():
    """Scoping policy's strategy wins over parent."""
    from hindclaw_ext.policy_engine import intersect_sa_policy, AccessResult

    parent = AccessResult(allowed=True, retain_strategy="deep", llm_model="claude-opus-4-6")
    scoping = AccessResult(allowed=True, retain_strategy="light", llm_model=None)

    result = intersect_sa_policy(parent, scoping)
    assert result.retain_strategy == "light"  # scoping wins
    assert result.llm_model == "claude-opus-4-6"  # scoping is None, parent inherited


def test_sa_no_scoping_inherits_parent():
    """No scoping policy = full inheritance."""
    from hindclaw_ext.policy_engine import intersect_sa_policy, AccessResult

    parent = AccessResult(allowed=True, recall_budget="high", llm_model="claude-opus-4-6")

    result = intersect_sa_policy(parent, scoping=None)
    assert result.allowed is True
    assert result.recall_budget == "high"
    assert result.llm_model == "claude-opus-4-6"


def test_resolve_bank_strategy_default():
    """Bank policy default strategy when no context match."""
    from hindclaw_ext.policy_engine import resolve_bank_strategy
    from hindclaw_ext.policy_models import BankPolicyDocument

    doc = BankPolicyDocument(
        version="2026-03-24",
        default_strategy="yoda-default",
        strategy_overrides=[
            {"scope": "channel", "value": "telegram", "strategy": "yoda-telegram"},
        ],
    )
    result = resolve_bank_strategy(doc, channel="slack")
    assert result == "yoda-default"


def test_resolve_bank_strategy_channel_match():
    """Channel override takes precedence over default."""
    from hindclaw_ext.policy_engine import resolve_bank_strategy
    from hindclaw_ext.policy_models import BankPolicyDocument

    doc = BankPolicyDocument(
        version="2026-03-24",
        default_strategy="yoda-default",
        strategy_overrides=[
            {"scope": "channel", "value": "telegram", "strategy": "yoda-telegram"},
        ],
    )
    result = resolve_bank_strategy(doc, channel="telegram")
    assert result == "yoda-telegram"


def test_resolve_bank_strategy_topic_beats_channel():
    """Topic override beats channel override."""
    from hindclaw_ext.policy_engine import resolve_bank_strategy
    from hindclaw_ext.policy_models import BankPolicyDocument

    doc = BankPolicyDocument(
        version="2026-03-24",
        default_strategy="yoda-default",
        strategy_overrides=[
            {"scope": "channel", "value": "telegram", "strategy": "yoda-telegram"},
            {"scope": "topic", "value": "12345", "strategy": "yoda-dm-ruben"},
        ],
    )
    result = resolve_bank_strategy(doc, channel="telegram", topic="12345")
    assert result == "yoda-dm-ruben"


def test_resolve_bank_strategy_none():
    """No strategy when bank policy has no default and no match."""
    from hindclaw_ext.policy_engine import resolve_bank_strategy
    from hindclaw_ext.policy_models import BankPolicyDocument

    doc = BankPolicyDocument(version="2026-03-24")
    result = resolve_bank_strategy(doc)
    assert result is None
