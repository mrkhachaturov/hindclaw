#!/usr/bin/env python3
"""Extract OpenAPI spec from HindclawHttp extension without running a server.

FastAPI generates the OpenAPI schema from route decorators and response_model=
Pydantic types at app construction time. No HTTP request, no database, no env vars.

This works because the entire hindclaw_ext package uses lazy initialization:
- DB pool created on first get_pool() call, not at import
- JWT secret read per-decode via _get_jwt_secret(), not at import
- resolver.py only imports types

If future changes add import-time side effects, extraction will break.

Prerequisites:
    pip install -e packages/extension/
    pip install hindsight-api-slim==<UPSTREAM_HINDSIGHT_VERSION>

Usage:
    python scripts/extract-openapi.py
    # Writes to apps/docs/public/openapi.json

The spec that openapi-generator and @hey-api/openapi-ts consume is the raw
Pydantic v2 output (OpenAPI 3.1.0), with only a single ValidationError schema
patch. Upstream Hindsight uses the same openapi-generator v7.10.0 against a
3.1.0 spec with anyOf+null patterns, which proves the older pre-conversion
that hindclaw did is unnecessary. The 3.1->3.0 down-conversion needed by
progenitor (Rust client) lives in packages/clients/rust/build.rs instead,
where only the Rust client sees it.
"""
import json
from pathlib import Path

from fastapi import FastAPI

from hindclaw_ext.http import HindclawHttp


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SPEC_PATH = REPO_ROOT / "apps" / "docs" / "public" / "openapi.json"

# Root-level tag declarations. FastAPI only emits `tags` at the document root
# when `openapi_tags` is set, and Fumadocs' `per: 'tag'` page mode builds its
# pages from that list — without it the API reference generates zero pages.
# Order here is the order the API section appears in the sidebar.
API_TAGS = [
    {"name": "Users", "description": "User records, channel identities, and the current user."},
    {"name": "Groups", "description": "Groups and their membership."},
    {"name": "API Keys", "description": "Issuing and revoking API keys."},
    {
        "name": "Service Accounts",
        "description": "Service accounts and the keys that authenticate them.",
    },
    {
        "name": "Policies",
        "description": "Access policies and their attachments to principals.",
    },
    {"name": "Banks", "description": "Per-bank policy configuration."},
    {"name": "Templates", "description": "Bank templates and template sources."},
    {"name": "Admin", "description": "Administrative and debugging endpoints."},
]


def extract() -> dict:
    """Create minimal FastAPI app with HindclawHttp and return OpenAPI spec.

    Returns:
        OpenAPI specification dict with typed schemas for all /ext/hindclaw/*
        endpoints. Used by generate-clients.sh to produce Go/Python/TS clients.
    """
    app = FastAPI(
        title="Hindclaw API",
        description="Access control API for Hindsight memory server",
        version="0.1.0",
        openapi_tags=API_TAGS,
    )
    ext = HindclawHttp({})
    # memory=None is safe — get_router() stores the reference but extraction
    # doesn't call any endpoint handlers, so the pool is never accessed.
    # Type annotation says MemoryEngine but Python doesn't enforce at runtime.
    router = ext.get_router(memory=None)  # type: ignore[arg-type]
    app.include_router(router, prefix="/ext")

    # Patch ValidationError schema to match Pydantic v2 actual error format.
    # FastAPI only generates loc/msg/type, but Pydantic v2 also returns input,
    # ctx, and url. Without these, Go clients with DisallowUnknownFields break.
    schema = app.openapi()
    ve = schema.get("components", {}).get("schemas", {}).get("ValidationError")
    if ve:
        props = ve.setdefault("properties", {})
        props.setdefault("input", {"title": "Input"})
        props.setdefault("ctx", {"title": "Context", "type": "object"})
        props.setdefault("url", {"title": "URL", "type": "string"})

    return schema


if __name__ == "__main__":
    spec = extract()
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SPEC_PATH.open("w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
        f.write("\n")
    print(f"Wrote {SPEC_PATH.relative_to(REPO_ROOT)}")
