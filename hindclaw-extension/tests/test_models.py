"""Tests for hindclaw_ext.models."""
import pytest
from hindclaw_ext.models import ResolvedPermissions


def test_resolved_permissions_defaults():
    """Default ResolvedPermissions denies everything."""
    perms = ResolvedPermissions(user_id="test", is_anonymous=False)
    assert perms.recall is False
    assert perms.retain is False
    assert perms.retain_roles == ["user", "assistant"]
    assert perms.retain_tags == []
    assert perms.retain_every_n_turns == 1
    assert perms.retain_strategy is None
    assert perms.recall_budget == "mid"
    assert perms.recall_max_tokens == 1024
    assert perms.recall_tag_groups is None
    assert perms.llm_model is None
    assert perms.llm_provider is None
    assert perms.exclude_providers == []


def test_resolved_permissions_with_values():
    """ResolvedPermissions accepts all fields."""
    perms = ResolvedPermissions(
        user_id="alice",
        is_anonymous=False,
        recall=True,
        retain=True,
        retain_tags=["role:team-lead", "user:alice"],
        recall_budget="high",
        recall_tag_groups=[{"not": {"tags": ["restricted"], "match": "any_strict"}}],
    )
    assert perms.recall is True
    assert perms.retain_tags == ["role:team-lead", "user:alice"]
    assert perms.recall_budget == "high"


def test_resolved_permissions_anonymous():
    """Anonymous users have is_anonymous=True."""
    perms = ResolvedPermissions(user_id="_anonymous", is_anonymous=True)
    assert perms.is_anonymous is True
    assert perms.recall is False
