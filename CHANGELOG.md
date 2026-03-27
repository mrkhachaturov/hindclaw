# Changelog

All notable changes to the HindClaw core repo will be documented in this file.

The core repo version line covers `hindclaw-extension`, `hindclaw-clients`, `hindclaw-docs`,
and `hindclaw-cli` — these are versioned together because they depend on each other.

Independent components have their own version lines and changelogs:
- `hindclaw-integrations/openclaw/` (hindclaw-openclaw-plugin)
- `hindclaw-integrations/claude-code/` (hindclaw-claude-plugin)
- `hindclaw-terraform/` (terraform-provider-hindclaw)
- `hindclaw-templates/` (hindclaw-templates-official)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.3] - 2026-03-28

### Changed
- Remove all database migrations (V2, V3, V4) — no production deployments exist, DB is recreated from scratch each deploy. DDL is the single source of truth.

### Fixed
- Fix asyncpg crash on startup caused by comment-only `_MIGRATION_V3` (asyncpg cannot execute SQL strings with no statements)

## [0.2.2] - 2026-03-28

### Changed
- **Bank bootstrap uses in-process engine** — replaced HTTP loopback with direct `MemoryEngine` calls using `RequestContext(internal=True)`. Bank creation from templates no longer requires auth tokens for internal API calls.
- Removed `hindsight_client.py` (HTTP client factory) and vendored `hindsight_client_api` — no longer needed
- Removed `[banks]` optional extra and vendored client dependencies (`aiohttp-retry`, `python-dateutil`, `urllib3`, `typing-extensions`)

### Fixed
- Bank creation from template no longer blocked by HindclawTenant authentication on internal HTTP calls

## [0.2.1] - 2026-03-27 [yanked]

### Fixed
- Attempted to move `hindsight-client-api` to core deps — broke PyPI installs since the package isn't published

### Added
- **Template marketplace sources** — register trusted marketplace repos, browse and search templates across sources (`POST/GET/DELETE /admin/template-sources`, `GET /marketplace/search`)
- **Template install from marketplace** — install templates from registered sources with strict validation and compatibility checking (`POST /templates/install`)
- **Template update from marketplace** — update installed templates when newer versions are available (`POST /templates/{scope}/{source}/{name}/update`)
- **Version module** — `hindclaw_ext.version` with `HINDCLAW_VERSION` (from package metadata), `SUPPORTED_SCHEMA_VERSIONS`, and `is_version_compatible()` semver comparison
- **MarketplaceTemplate model** — strict Pydantic model for parsing raw marketplace JSON (`extra="forbid"`)
- **Marketplace validation pipeline** — schema version, hindclaw version, and hindsight version compatibility checks (fail closed)
- **Template sources DB** — `template_sources` table for runtime management of trusted marketplace repos
- **`template:source` IAM action** — new action for marketplace source management, added to builtin `template:admin` policy via migration V4
- Rust client (progenitor codegen from OpenAPI spec)

## [0.2.0] - 2026-03-25

### Added
- **Bank templates entity** — `bank_templates` table, Pydantic models, CRUD API for local template management
- **Bank creation from template** — `POST /ext/hindclaw/banks` creates a Hindsight bank from an installed template (missions, config, directives, mental models)
- Template reference parser (`template_ref.py`) for `scope/source/name` strings
- Hindsight client factory (`hindsight_client.py`) for calling Hindsight API from the extension

### Changed
- Client regeneration: all 4 clients (Go, Python, TypeScript, Rust) updated with template endpoints

## [0.1.3] - 2026-03-25

### Fixed
- Serialize `update_user` response as dict (was returning Pydantic model directly)

## [0.1.2] - 2026-03-25

### Added
- Per-endpoint IAM with fine-grained action strings (`iam:users:read`, `iam:users:write`, etc.)
- `is_active` field on users for soft-disable

## [0.1.1] - 2026-03-24

### Added
- Policy-based access control — `PolicyDocument` with allow/deny statements, wildcard matching, specificity-based resolution
- Bank policies with context-scoped strategy overrides (provider/channel/topic)
- Service accounts with scoping policies and API key management
- User channel management (provider + sender_id mapping)
- Group membership and policy attachment
- Debug resolve endpoint (`GET /debug/resolve`)
- Builtin policies: `iam:admin`, `bank:admin`, `bank:readwrite`, `bank:readonly`, `bank:retain-only`
- Bootstrap admin user seeding from environment variables
