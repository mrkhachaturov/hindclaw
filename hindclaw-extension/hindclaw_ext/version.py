"""Version constants and compatibility checking for hindclaw-extension.

Provides the current hindclaw version (read from package metadata at import
time) and semver comparison for template compatibility validation.
"""

import importlib.metadata

# Read version from installed package metadata (matches pyproject.toml)
HINDCLAW_VERSION: str = importlib.metadata.version("hindclaw-extension")

# Template schema versions this release can parse
SUPPORTED_SCHEMA_VERSIONS: set[int] = {1}


def is_version_compatible(
    installed: str,
    required: str | None,
) -> bool:
    """Check if the installed version satisfies the minimum required version.

    Compares version strings as tuples of integers. Supports 2-segment
    (major.minor) and 3-segment (major.minor.patch) versions.

    Args:
        installed: The version currently installed (e.g., "0.2.0").
        required: The minimum required version (e.g., "0.2.0"), or None
            if no minimum is required.

    Returns:
        True if installed >= required, or if required is None.
    """
    if required is None:
        return True

    def _parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    return _parse(installed) >= _parse(required)
