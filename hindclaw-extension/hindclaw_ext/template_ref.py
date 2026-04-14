"""Template reference parsing — reusable by HTTP endpoints and CLI.

A template reference is a string like "server/hindclaw/backend-python" that
identifies a template by scope, optional source, and name.

Format:
    scope/source/name   — sourced template (installed from marketplace)
    scope/name          — custom template (created locally, no source)

Valid scopes: "server", "personal".
"""

from pydantic import BaseModel

_VALID_SCOPES = frozenset({"server", "personal"})


class TemplateRef(BaseModel):
    """Parsed template reference.

    Attributes:
        scope: Template visibility scope ("server" or "personal").
        source: Marketplace source name (None for custom templates).
        name: Template name within the scope/source.
    """

    scope: str
    source: str | None
    name: str

    def __str__(self) -> str:
        """Format as a template reference string.

        Returns:
            "scope/source/name" for sourced, "scope/name" for custom.
        """
        if self.source:
            return f"{self.scope}/{self.source}/{self.name}"
        return f"{self.scope}/{self.name}"


def parse_template_ref(ref: str) -> TemplateRef:
    """Parse a template reference string into its components.

    Args:
        ref: Template reference (e.g., "server/hindclaw/backend-python").

    Returns:
        Parsed TemplateRef with scope, source, and name.

    Raises:
        ValueError: If the reference format is invalid.
    """
    if not ref:
        raise ValueError("Template reference must not be empty")

    parts = ref.split("/")

    if len(parts) < 2:
        raise ValueError(
            f"Invalid template reference {ref!r}: must include scope (e.g., 'server/name' or 'server/source/name')"
        )

    if len(parts) > 3:
        raise ValueError(f"Invalid template reference format {ref!r}: expected 'scope/name' or 'scope/source/name'")

    scope = parts[0]
    if scope not in _VALID_SCOPES:
        raise ValueError(f"Invalid scope {scope!r}: must be one of {sorted(_VALID_SCOPES)}")

    if len(parts) == 3:
        source = parts[1]
        name = parts[2]
        if not source:
            raise ValueError(f"Invalid template reference {ref!r}: source must not be empty")
    else:
        source = None
        name = parts[1]

    if not name:
        raise ValueError(f"Invalid template reference {ref!r}: name must not be empty")

    return TemplateRef(scope=scope, source=source, name=name)
