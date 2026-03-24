"""Policy evaluation engine — gather, match, merge, deny, SA intersection.

Implements the MinIO-style access model from spec Section 5. Replaces
the 4-step boolean merge in resolver.py.
"""


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
