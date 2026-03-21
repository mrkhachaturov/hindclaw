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
    pip install -e hindclaw-extension/
    pip install hindsight-api-slim

Usage:
    python scripts/extract-openapi.py > hindclaw-clients/openapi.json
"""
import json
import sys

from fastapi import FastAPI

from hindclaw_ext.http import HindclawHttp


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
    )
    ext = HindclawHttp({})
    # memory=None is safe — get_router() stores the reference but extraction
    # doesn't call any endpoint handlers, so the pool is never accessed.
    # Type annotation says MemoryEngine but Python doesn't enforce at runtime.
    router = ext.get_router(memory=None)  # type: ignore[arg-type]
    app.include_router(router, prefix="/ext")
    return app.openapi()


if __name__ == "__main__":
    spec = extract()
    json.dump(spec, sys.stdout, indent=2)
    sys.stdout.write("\n")
