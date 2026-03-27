"""Marketplace index fetching, caching, and search.

Handles remote operations for template marketplace sources:
- Fetching index.json from configured source URLs
- In-memory LRU cache with configurable TTL
- Full-text search across templates by name, description, and tags
"""

import logging
import os
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from hindclaw_ext.http_models import MarketplaceSearchResult
from hindclaw_ext.models import TemplateSourceRecord

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

            data = await resp.json()
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
