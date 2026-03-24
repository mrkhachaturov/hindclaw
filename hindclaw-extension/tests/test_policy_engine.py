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
