# CLAUDE.md — hindclaw-clients

Generated typed API clients for the Hindclaw access control extension (`/ext/hindclaw/*` endpoints).

## Structure

```
hindclaw-clients/
├── openapi.json                    # OpenAPI spec (generated, committed)
├── openapi-generator-config/
│   ├── go.yaml                     # Go generator config
│   └── python.yaml                 # Python generator config
├── go/                             # Go client (OpenAPI Generator v7.10.0)
│   ├── hindclaw_client.go          # MAINTAINED: convenience constructors
│   ├── README.md                   # MAINTAINED
│   ├── api_default.go              # GENERATED
│   ├── client.go                   # GENERATED
│   ├── configuration.go            # GENERATED
│   └── model_*.go                  # GENERATED: one per request/response model
├── python/                         # Python client (OpenAPI Generator v7.10.0)
│   ├── hindclaw_client.py          # MAINTAINED: HindclawClient wrapper
│   ├── pyproject.toml              # MAINTAINED
│   ├── README.md                   # MAINTAINED
│   └── hindclaw_client_api/        # GENERATED (auto-patched for deferred aiohttp init)
├── typescript/                     # TypeScript client (@hey-api/openapi-ts 0.88.0)
│   ├── src/index.ts                # MAINTAINED: re-exports
│   ├── package.json                # MAINTAINED
│   ├── tsconfig.json               # MAINTAINED
│   ├── README.md                   # MAINTAINED
│   └── generated/                  # GENERATED
├── rust/                          # Rust client (progenitor, compile-time codegen)
│   ├── Cargo.toml                 # MAINTAINED
│   ├── build.rs                   # MAINTAINED: OpenAPI 3.1→3.0 + progenitor
│   ├── src/lib.rs                 # MAINTAINED: include!() + docs + tests
│   └── README.md                  # MAINTAINED
```

**MAINTAINED** files are hand-written and preserved across regeneration.
**GENERATED** files are overwritten by the generation pipeline — do not edit.

## Regeneration

From the hindclaw repo root:

```bash
python scripts/extract-openapi.py > hindclaw-clients/openapi.json
bash scripts/generate-clients.sh
```

This is fully automated:
- `extract-openapi.py` builds a FastAPI app from HindclawHttp and dumps the OpenAPI spec (no running server needed)
- `generate-clients.sh` runs OpenAPI Generator (Docker) for Go/Python, `@hey-api/openapi-ts` for TypeScript
- Python `rest.py` is auto-patched for deferred aiohttp initialization (same fix as upstream Hindsight)
- Maintained files are preserved via temp dir backup/restore

Prerequisites: Docker, Go 1.18+, Rust toolchain (cargo), Node.js + npm, `pip install -e hindclaw-extension/` + `hindsight-api-slim`

## When to Regenerate

Regenerate after any change to:
- Route decorators in `hindclaw-extension/hindclaw_ext/http.py` (new endpoints, changed paths)
- Response/request models in `hindclaw-extension/hindclaw_ext/http_models.py` (new fields, new models)
- `response_model=` annotations on route decorators

No regeneration needed for:
- Changes to endpoint handler logic (DB queries, business logic)
- Changes to auth, resolver, tenant, or validator extensions

## Key Details

- **OpenAPI Generator version**: v7.10.0 (pinned, matches upstream Hindsight)
- **Go module path**: `github.com/mrkhachaturov/hindclaw/hindclaw-clients/go`
- **Python package**: `hindclaw-client` (pip), wraps generated `hindclaw_client_api`
- **TypeScript package**: `@hindclaw/client`, uses `tsup` for CJS/ESM/DTS build
- **Rust crate**: `hindclaw-client`, uses progenitor (compile-time) — no generated files in git
- **API class name**: `DefaultApi` (Go: `DefaultAPI`) — all endpoints under one class since no tags are set
- **Security scheme**: `HTTPBearer` — clients use configured Bearer token, not per-method auth params
