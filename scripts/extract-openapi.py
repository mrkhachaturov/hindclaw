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

    # Convert OpenAPI 3.1.0 nullable patterns to 3.0.x style.
    # FastAPI + Pydantic v2 emits {"anyOf": [{"type": "T"}, {"type": "null"}]}
    # for `T | None` fields. openapi-generator's Python codegen (v7.x) crashes
    # on the {"type": "null"} branch. Convert to {"type": "T", "nullable": true}
    # which all generators handle correctly.
    _convert_nullable_anyof(schema)

    return schema


def _convert_nullable_anyof(schema: dict) -> None:
    """Convert anyOf-null patterns to nullable style throughout the spec.

    Walks all component schemas and converts patterns like:
        {"anyOf": [{"type": "string"}, {"type": "null"}]}
    to:
        {"type": "string", "nullable": true}

    Also handles complex branches (arrays, $ref, constrained integers) by
    keeping the non-null branch and adding nullable: true.

    Args:
        schema: OpenAPI spec dict (modified in place).
    """
    for comp_schema in schema.get("components", {}).get("schemas", {}).values():
        for prop_name, prop_def in comp_schema.get("properties", {}).items():
            if "anyOf" not in prop_def:
                continue
            branches = prop_def["anyOf"]
            null_branches = [b for b in branches if b.get("type") == "null"]
            non_null_branches = [b for b in branches if b.get("type") != "null"]
            if not null_branches or not non_null_branches:
                continue
            if len(non_null_branches) == 1:
                # Simple case: one real type + null → flatten
                real = non_null_branches[0]
                del prop_def["anyOf"]
                prop_def.update(real)
                prop_def["nullable"] = True


if __name__ == "__main__":
    spec = extract()
    json.dump(spec, sys.stdout, indent=2)
    sys.stdout.write("\n")
