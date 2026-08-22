"""Tests for policy document models."""

import pytest
from pydantic import ValidationError


def test_policy_statement_allow():
    """Allow statement with behavioral params."""
    from hindclaw_ext.policy_models import PolicyStatement

    stmt = PolicyStatement(
        effect="allow",
        actions=["bank:recall", "bank:reflect"],
        banks=["yoda", "r2d2"],
        recall_budget="high",
        recall_max_tokens=2048,
    )
    assert stmt.effect == "allow"
    assert stmt.actions == ["bank:recall", "bank:reflect"]
    assert stmt.banks == ["yoda", "r2d2"]
    assert stmt.recall_budget == "high"
    assert stmt.recall_max_tokens == 2048
    assert stmt.retain_roles is None  # not set


def test_policy_statement_deny():
    """Deny statement — no behavioral params."""
    from hindclaw_ext.policy_models import PolicyStatement

    stmt = PolicyStatement(
        effect="deny",
        actions=["bank:retain"],
        banks=["bb9e"],
    )
    assert stmt.effect == "deny"
    assert stmt.recall_budget is None


def test_policy_statement_invalid_effect():
    """Effect must be 'allow' or 'deny'."""
    from hindclaw_ext.policy_models import PolicyStatement

    with pytest.raises(ValidationError):
        PolicyStatement(effect="maybe", actions=["bank:recall"], banks=["*"])


def test_policy_statement_invalid_budget():
    """Budget must be low/mid/high."""
    from hindclaw_ext.policy_models import PolicyStatement

    with pytest.raises(ValidationError):
        PolicyStatement(
            effect="allow",
            actions=["bank:recall"],
            banks=["*"],
            recall_budget="ultra",
        )


def test_policy_document_valid():
    """Full policy document with version and statements."""
    from hindclaw_ext.policy_models import PolicyDocument

    doc = PolicyDocument(
        version="2026-03-24",
        statements=[
            {"effect": "allow", "actions": ["bank:recall"], "banks": ["*"]},
            {"effect": "deny", "actions": ["bank:retain"], "banks": ["bb9e"]},
        ],
    )
    assert len(doc.statements) == 2
    assert doc.statements[0].effect == "allow"


def test_policy_document_rejects_unknown_version():
    """Unknown version is rejected."""
    from hindclaw_ext.policy_models import PolicyDocument

    with pytest.raises(ValidationError):
        PolicyDocument(
            version="1999-01-01",
            statements=[{"effect": "allow", "actions": ["bank:recall"], "banks": ["*"]}],
        )


def test_policy_document_empty_statements():
    """Empty statements list is valid (grants nothing)."""
    from hindclaw_ext.policy_models import PolicyDocument

    doc = PolicyDocument(version="2026-03-24", statements=[])
    assert doc.statements == []


def test_bank_policy_minimal():
    """Minimal bank policy with just default strategy."""
    from hindclaw_ext.policy_models import BankPolicyDocument

    doc = BankPolicyDocument(version="2026-03-24", default_strategy="yoda-default")
    assert doc.default_strategy == "yoda-default"
    assert doc.strategy_overrides == []
    assert doc.public_access is None


def test_bank_policy_with_overrides():
    """Bank policy with strategy overrides and public access."""
    from hindclaw_ext.policy_models import BankPolicyDocument

    doc = BankPolicyDocument(
        version="2026-03-24",
        default_strategy="yoda-default",
        strategy_overrides=[
            {"scope": "channel", "value": "telegram", "strategy": "yoda-telegram"},
        ],
        public_access={
            "default": None,
            "overrides": [
                {
                    "scope": "provider",
                    "value": "telegram",
                    "actions": ["bank:recall"],
                    "recall_budget": "low",
                },
            ],
        },
    )
    assert len(doc.strategy_overrides) == 1
    assert doc.public_access is not None
    assert len(doc.public_access.overrides) == 1
    assert doc.public_access.default is None


def test_bank_policy_public_access_default():
    """Bank policy with non-null public access default."""
    from hindclaw_ext.policy_models import BankPolicyDocument

    doc = BankPolicyDocument(
        version="2026-03-24",
        public_access={
            "default": {
                "actions": ["bank:recall"],
                "recall_budget": "low",
                "recall_max_tokens": 256,
            },
            "overrides": [],
        },
    )
    assert doc.public_access.default is not None
    assert doc.public_access.default.actions == ["bank:recall"]
    assert doc.public_access.default.recall_budget == "low"


class TestTemplateActions:
    """Template actions should be accepted in policy statements."""

    def test_template_actions_valid_in_policy(self):
        from hindclaw_ext.policy_models import PolicyDocument, PolicyStatement

        doc = PolicyDocument(
            version="2026-03-24",
            statements=[
                PolicyStatement(
                    effect="allow",
                    actions=[
                        "template:list",
                        "template:create",
                        "template:install",
                        "template:manage",
                    ],
                    banks=["*"],
                )
            ],
        )
        assert len(doc.statements[0].actions) == 4

    def test_template_wildcard_in_policy(self):
        from hindclaw_ext.policy_models import PolicyDocument, PolicyStatement

        doc = PolicyDocument(
            version="2026-03-24",
            statements=[
                PolicyStatement(
                    effect="allow",
                    actions=["template:*"],
                    banks=["*"],
                )
            ],
        )
        assert doc.statements[0].actions == ["template:*"]
