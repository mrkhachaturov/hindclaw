"""Marketplace index fetching, caching, and search.

Handles remote operations for template marketplace sources:
- Fetching index.json from configured source URLs
- In-memory LRU cache with configurable TTL
- Full-text search across templates by name, description, and tags
"""

import importlib.metadata
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError as PydanticValidationError

from hindclaw_ext.http_models import MarketplaceSearchResult
from hindclaw_ext.models import TemplateSourceRecord
from hindclaw_ext.template_models import MarketplaceTemplate
from hindclaw_ext.version import HINDCLAW_VERSION, SUPPORTED_SCHEMA_VERSIONS, is_version_compatible

logger = logging.getLogger(__name__)

# Cache TTL in seconds (default: 5 minutes)
_CACHE_TTL = int(os.environ.get("HINDCLAW_MARKETPLACE_CACHE_TTL", "300"))

# In-memory cache: source_name -> (MarketplaceIndex, timestamp)
_index_cache: dict[str, tuple["MarketplaceIndex", float]] = {}


@dataclass
class MarketplaceIndex:
    """Parsed marketplace index with template entries."""

    templates: list[dict] = field(default_factory=list)


def derive_source_name(url: str) -> str:
    """Derive a source name from a git URL.

    Extracts the org/user segment from the URL path. For GitHub, GitLab,
    and self-hosted Git, this is the first path segment after the host.

    Args:
        url: Repository URL (e.g., "https://github.com/hindclaw/templates").

    Returns:
        Derived source name (e.g., "hindclaw").

    Raises:
        ValueError: If no source name can be derived from the URL.
    """
    parsed = urlparse(url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    segments = [s for s in path.split("/") if s]
    if not segments:
        raise ValueError(
            f"Cannot derive source name from '{url}'. "
            "Use the 'alias' field to specify a name explicitly."
        )
    return segments[0]


def _resolve_file_url(base_url: str, file_path: str) -> str:
    """Resolve a raw file URL from a marketplace source URL.

    For GitHub URLs, translates to raw.githubusercontent.com automatically.
    For GitLab URLs, translates to the raw API path.
    For other hosts, the source URL must already point to a raw-content
    endpoint (not a web UI page). The file path is appended directly.

    Args:
        base_url: Marketplace source URL (registered via admin endpoint).
        file_path: Path to the file within the repo (e.g., "index.json").

    Returns:
        URL to fetch the raw file content.
    """
    parsed = urlparse(base_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if parsed.hostname == "github.com":
        return f"https://raw.githubusercontent.com{path}/main/{file_path}"
    if parsed.hostname and "gitlab" in parsed.hostname:
        # GitLab raw API: /{namespace}/{project}/-/raw/main/{file}
        return f"{parsed.scheme}://{parsed.hostname}{path}/-/raw/main/{file_path}"
    # Other hosts: source URL must be a raw-content base URL.
    # E.g., "https://templates.mycompany.com/repo" -> appends "/index.json".
    return f"{base_url.rstrip('/')}/{file_path}"


def clear_cache() -> None:
    """Clear the marketplace index cache."""
    _index_cache.clear()


# Content types accepted from marketplace sources. GitHub raw serves JSON
# as text/plain; other hosts may use application/json or octet-stream.
_ACCEPTED_JSON_TYPES = {"application/json", "text/plain", "application/octet-stream"}


async def _parse_json_response(resp, *, context: str) -> dict[str, Any] | None:
    """Parse a JSON response body after validating the content type.

    Accepts application/json, text/plain (GitHub raw), and
    application/octet-stream. Rejects other types (e.g., text/html from
    error pages) with a warning instead of attempting to parse garbage.

    Args:
        resp: The aiohttp response object.
        context: Description for log messages (e.g., "index from hindclaw").

    Returns:
        Parsed dict, or None if the content type is unexpected.
    """
    content_type = resp.content_type or ""
    if content_type not in _ACCEPTED_JSON_TYPES:
        text = await resp.text()
        logger.warning(
            "Unexpected content type '%s' for %s — expected JSON. Body: %s",
            content_type, context, text[:200],
        )
        return None
    text = await resp.text()
    return json.loads(text)


async def fetch_index(
    source: TemplateSourceRecord,
    *,
    session=None,
) -> "MarketplaceIndex | None":
    """Fetch and cache a marketplace index from a source.

    Checks the in-memory cache first. If the cache is fresh (within TTL),
    returns the cached index. If expired or missing, fetches from the remote
    source. On fetch failure with an expired cache, returns the stale data
    with a warning log.

    Args:
        source: The marketplace source to fetch from.
        session: Optional aiohttp.ClientSession (created if not provided).

    Returns:
        MarketplaceIndex with template entries, or None on failure with no cache.
    """
    now = time.time()
    cached = _index_cache.get(source.name)
    if cached:
        index, ts = cached
        if now - ts < _CACHE_TTL:
            return index

    url = _resolve_file_url(source.url, "index.json")
    headers = {}
    if source.auth_token:
        headers["Authorization"] = f"Bearer {source.auth_token}"

    owns_session = session is None
    if owns_session:
        import aiohttp
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(
                    "Failed to fetch index from %s: HTTP %d — %s",
                    source.name, resp.status, text[:200],
                )
                if cached:
                    logger.warning("Returning stale cache for %s", source.name)
                    return cached[0]
                return None

            data = await _parse_json_response(resp, context=f"index from {source.name}")
            if data is None:
                if cached:
                    logger.warning("Returning stale cache for %s", source.name)
                    return cached[0]
                return None
            index = MarketplaceIndex(templates=data.get("templates", []))
            _index_cache[source.name] = (index, now)
            return index
    except Exception:
        logger.exception("Error fetching index from %s", source.name)
        if cached:
            logger.warning("Returning stale cache for %s", source.name)
            return cached[0]
        return None
    finally:
        if owns_session:
            await session.close()


def search_marketplace(
    index: MarketplaceIndex,
    *,
    source_name: str,
    query: str | None = None,
    tag: str | None = None,
) -> list[MarketplaceSearchResult]:
    """Search a marketplace index for matching templates.

    Matches against name, description, and tags (case-insensitive).
    Filters are ANDed: if both query and tag are provided, both must match.

    Args:
        index: The marketplace index to search.
        source_name: Source name to include in results.
        query: Free-text search (matches name, description, tags).
        tag: Filter by exact tag match.

    Returns:
        List of MarketplaceSearchResult entries.
    """
    results = []
    q = query.lower() if query else None

    for entry in index.templates:
        name = entry.get("name", "")
        description = entry.get("description", "")
        tags = entry.get("tags", [])
        version = entry.get("version", "")
        author = entry.get("author", "")

        if tag and tag.lower() not in [t.lower() for t in tags]:
            continue

        if q:
            searchable = f"{name} {description} {' '.join(tags)}".lower()
            if q not in searchable:
                continue

        results.append(MarketplaceSearchResult(
            source=source_name,
            name=name,
            version=version,
            description=description,
            author=author,
            tags=tags,
        ))

    return results


def _get_hindsight_version() -> str | None:
    """Read the running Hindsight server version from package metadata.

    Returns:
        Version string (e.g., "0.4.20"), or None if not installed
        (e.g., in test environments without hindsight-api).
    """
    try:
        return importlib.metadata.version("hindsight-api")
    except importlib.metadata.PackageNotFoundError:
        try:
            return importlib.metadata.version("hindsight-api-slim")
        except importlib.metadata.PackageNotFoundError:
            return None


async def fetch_template(
    source: TemplateSourceRecord,
    name: str,
    *,
    session=None,
) -> "MarketplaceTemplate | None":
    """Fetch and validate an individual template from a marketplace source.

    Downloads the template JSON file from the source, parses it into a
    MarketplaceTemplate model, and returns the validated instance. Does
    not check compatibility — call validate_template() separately.

    Args:
        source: The marketplace source to fetch from.
        name: Template name (used to construct the file path).
        session: Optional aiohttp.ClientSession (created if not provided).

    Returns:
        MarketplaceTemplate if fetch and parse succeed, None on failure.
    """
    url = _resolve_file_url(source.url, f"templates/{name}.json")
    headers = {}
    if source.auth_token:
        headers["Authorization"] = f"Bearer {source.auth_token}"

    owns_session = session is None
    if owns_session:
        import aiohttp
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(
                    "Failed to fetch template '%s' from %s: HTTP %d — %s",
                    name, source.name, resp.status, text[:200],
                )
                return None

            data = await _parse_json_response(
                resp, context=f"template '{name}' from {source.name}",
            )
            if data is None:
                return None
            return MarketplaceTemplate(**data)
    except PydanticValidationError as e:
        logger.warning(
            "Template '%s' from %s failed validation: %s",
            name, source.name, str(e)[:500],
        )
        return None
    except Exception:
        logger.exception("Error fetching template '%s' from %s", name, source.name)
        return None
    finally:
        if owns_session:
            await session.close()


def validate_template(template: "MarketplaceTemplate") -> list[str]:
    """Validate a marketplace template for compatibility with this server.

    Checks (fail closed — all must pass):
    1. schema_version is in SUPPORTED_SCHEMA_VERSIONS
    2. min_hindclaw_version <= HINDCLAW_VERSION
    3. min_hindsight_version <= running Hindsight version (if specified)

    Args:
        template: The parsed marketplace template.

    Returns:
        List of error strings. Empty list means compatible.
    """
    errors = []
    if template.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            f"Unsupported schema_version {template.schema_version}. "
            f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
        )
    if not is_version_compatible(HINDCLAW_VERSION, template.min_hindclaw_version):
        errors.append(
            f"Requires hindclaw >= {template.min_hindclaw_version}, "
            f"but this server runs {HINDCLAW_VERSION}"
        )
    if template.min_hindsight_version:
        hs_version = _get_hindsight_version()
        if hs_version is None:
            errors.append(
                f"Template requires hindsight >= {template.min_hindsight_version}, "
                "but hindsight version could not be determined"
            )
        elif not is_version_compatible(hs_version, template.min_hindsight_version):
            errors.append(
                f"Requires hindsight >= {template.min_hindsight_version}, "
                f"but this server runs {hs_version}"
            )
    return errors
