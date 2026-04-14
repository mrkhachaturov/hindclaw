"""Marketplace catalog fetching + manifest resolution.

Fetches the top-level catalog (``templates.json``) from configured template
sources, resolves each catalog entry to a fully-parsed upstream
``BankTemplateManifest``, and returns it with a composite revision string.

The module keeps a small TTL cache keyed by
``(scope, owner, source_name, path)`` so catalog fetches and referenced-
manifest fetches share the same store and do not re-download on repeated
installs of the same template from the same source.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from urllib.parse import urlparse

import aiohttp
from hindsight_api.api.http import (  # type: ignore[attr-defined]
    BankTemplateManifest,
    validate_bank_template,
)

from hindclaw_ext import db
from hindclaw_ext.template_models import Catalog, CatalogEntry, TemplateScope

logger = logging.getLogger(__name__)

# Cache TTL in seconds (default: 5 minutes)
_CACHE_TTL = int(os.environ.get("HINDCLAW_MARKETPLACE_CACHE_TTL", "300"))

# Composite cache: (scope, owner, source_name, path) -> ((bytes, revision), timestamp).
# Replaces the old MarketplaceIndex cache — catalog and referenced manifests
# share the same dict, rekeyed by path.
_index_cache: dict[tuple[str, str, str, str], tuple[tuple[bytes, str], float]] = {}


def derive_source_name(url: str) -> str:
    """Derive a source name from a git URL."""
    parsed = urlparse(url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    segments = [s for s in path.split("/") if s]
    if not segments:
        raise ValueError(f"Cannot derive source name from '{url}'. Use the 'alias' field to specify a name explicitly.")
    return segments[0]


def _resolve_file_url(base_url: str, file_path: str) -> str:
    """Resolve a raw file URL from a marketplace source URL.

    Handles GitHub (github.com → raw.githubusercontent.com/.../main/),
    GitLab (/-/raw/main/), and passthrough for other hosts.
    """
    parsed = urlparse(base_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if parsed.hostname == "github.com":
        return f"https://raw.githubusercontent.com{path}/main/{file_path}"
    if parsed.hostname and "gitlab" in parsed.hostname:
        return f"{parsed.scheme}://{parsed.hostname}{path}/-/raw/main/{file_path}"
    return f"{base_url.rstrip('/')}/{file_path}"


def clear_cache() -> None:
    """Clear the marketplace cache (useful in tests)."""
    _index_cache.clear()


def _content_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()[:16]


def _cache_get(key: tuple[str, str, str, str]) -> tuple[bytes, str] | None:
    entry = _index_cache.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.time() - ts > _CACHE_TTL:
        _index_cache.pop(key, None)
        return None
    return value


def _cache_put(key: tuple[str, str, str, str], value: tuple[bytes, str]) -> None:
    _index_cache[key] = (value, time.time())


async def _fetch_raw(
    url: str,
    auth_token: str | None,
    session: aiohttp.ClientSession | None = None,
) -> tuple[bytes, str]:
    """Fetch a raw file and return ``(body_bytes, revision_string)``.

    Revision priority: ETag header → Last-Modified header → content hash.
    """
    owns_session = session is None
    if session is None:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise ValueError(f"Fetch {url} failed: HTTP {resp.status}")
            body = await resp.read()
            revision = resp.headers.get("ETag") or resp.headers.get("Last-Modified") or _content_hash(body)
            return body, revision
    finally:
        if owns_session:
            await session.close()


async def fetch_and_resolve_template(
    source_name: str,
    source_scope: TemplateScope,
    source_owner: str | None,
    template_id: str,
    *,
    session: aiohttp.ClientSession | None = None,
) -> tuple[CatalogEntry, BankTemplateManifest, str]:
    """Fetch a template from a marketplace source and resolve its manifest.

    Returns:
        - The catalog entry (presentation metadata + body slot).
        - The fully-resolved upstream BankTemplateManifest.
        - A composite revision string: catalog ETag for inline entries,
          ``f"{catalog_revision}|{manifest_revision}"`` for reference entries.

    Raises:
        ValueError: unknown source, unknown template id within source, or
            upstream validation failure.
    """
    source = await db.get_template_source(
        source_name,
        scope=source_scope.value,
        owner=source_owner,
    )
    if source is None:
        raise ValueError(f"Unknown template source: {source_scope.value}/{source_owner or '-'}/{source_name}")

    catalog_url = _resolve_file_url(source.url, "templates.json")
    catalog_key = (
        source_scope.value,
        source_owner or "",
        source_name,
        "templates.json",
    )
    cached = _cache_get(catalog_key)
    if cached is None:
        catalog_bytes, catalog_revision = await _fetch_raw(catalog_url, source.auth_token, session=session)
        _cache_put(catalog_key, (catalog_bytes, catalog_revision))
    else:
        catalog_bytes, catalog_revision = cached

    catalog = Catalog.model_validate_json(catalog_bytes)

    entry = next((e for e in catalog.templates if e.id == template_id), None)
    if entry is None:
        raise ValueError(
            f"Template '{template_id}' not in catalog '{source_scope.value}/{source_owner or '-'}/{source_name}'"
        )

    if entry.manifest is not None:
        manifest = entry.manifest
        revision = catalog_revision
    else:
        manifest_url = _resolve_file_url(source.url, entry.manifest_file)  # type: ignore[arg-type]
        manifest_key = (
            source_scope.value,
            source_owner or "",
            source_name,
            entry.manifest_file,  # type: ignore[arg-type]
        )
        cached = _cache_get(manifest_key)
        if cached is None:
            manifest_bytes, manifest_revision = await _fetch_raw(manifest_url, source.auth_token, session=session)
            _cache_put(manifest_key, (manifest_bytes, manifest_revision))
        else:
            manifest_bytes, manifest_revision = cached
        manifest = BankTemplateManifest.model_validate_json(manifest_bytes)
        revision = f"{catalog_revision}|{manifest_revision}"

    errors = validate_bank_template(manifest)
    if errors:
        raise ValueError(f"Template manifest invalid: {'; '.join(errors)}")

    return entry, manifest, revision


__all__ = [
    "Catalog",
    "CatalogEntry",
    "_resolve_file_url",
    "clear_cache",
    "derive_source_name",
    "fetch_and_resolve_template",
]
