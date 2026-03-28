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

## [0.3.0] - 2026-03-28

### Added
- **Self-service SA endpoints** at `/me/service-accounts` — users create, read, update, delete their own service accounts and keys without admin privileges
- `CreateSelfServiceAccountRequest` and `UpdateSelfServiceAccountRequest` models with `extra="forbid"` — owner is always the authenticated caller, unknown fields rejected with 422
- `_get_owned_sa` ownership helper — returns 404 for both "not found" and "not yours" (no information leakage)
- `list_service_accounts_by_owner` DB query for owner-filtered SA listing
- 20 new tests covering ownership enforcement, cross-user 404, extra field rejection, SA-as-caller identity

### Changed
- **Admin SA endpoints now require `iam:service_accounts:manage`** — all 8 endpoints at `/service-accounts` switched from `iam:service_accounts:{read,write}` and `iam:service_account_keys:write` to the new `iam:service_accounts:manage` action. The built-in `iam:admin` policy (`iam:*`) already covers it.

### Security
- **Fix privilege escalation in SA creation** — previously any user with `iam:service_accounts:write` could create SAs for other users by specifying an arbitrary `owner_user_id`. The self-service surface eliminates this by construction (no `owner_user_id` field). The admin surface is now gated by the separate `iam:service_accounts:manage` action.
- **Block SA self-escalation** — self-service update only allows `display_name` changes. `scoping_policy_id` and `is_active` are admin-only, preventing an SA from removing its own scoping policy.

## [0.2.7] - 2026-03-28

### Added
- **MCP tool visibility filtering** — `HindclawValidator.filter_mcp_tools()` hides MCP tools the user's policies don't allow, so the AI never sees tools it can't use
- `_TOOL_ACTION_MAP` maps 30 MCP tool names to 4 policy actions (`bank:recall`, `bank:retain`, `bank:reflect`, `bank:admin`)
- Per-action caching keeps policy evaluations to 3-4 per `tools/list` call
- Unknown tools pass through (fail-open for forward compatibility)
- 9 new tests covering all identity types (user, SA, unmapped) and edge cases

## [0.2.6] - 2026-03-28

### Fixed
- **Template get/update/delete now find marketplace-installed templates** — endpoints hardcoded `source_name=None` which only matched custom templates. Now uses `_UNSET` sentinel to match by `(id, scope, owner)` regardless of source.

## [0.2.5] - 2026-03-28

### Fixed
- **Partial updates can now clear nullable fields to NULL** — `update_service_account` (and all `Update*Request` endpoints) previously collapsed "not provided" and "set to null" into the same `None`. Added `_UNSET` sentinel in DB layer, fixed HTTP handler to pass only present fields, and fixed Rust client codegen to emit explicit `null` for `Update*Request` structs.

### Added
- `--clear-scoping-policy` flag on `hindclaw admin sa update` — sets `scoping_policy_id` to NULL
- 4 new DB tests for `update_service_account` sentinel behavior

## [0.2.4] - 2026-03-28

### Changed
- **Bank bootstrap uses in-process engine** — replaced HTTP loopback with direct `MemoryEngine` calls using `RequestContext(internal=True)`, fixing auth wall on internal API calls
- Validate marketplace JSON content type before parsing — accept `application/json`, `text/plain` (GitHub raw), `application/octet-stream`; reject unexpected types
- Remove all database migrations (V2, V3, V4) — DDL is the single source of truth
- Remove `hindsight_client.py` and vendored `hindsight_client_api` — no longer needed
- Remove extra dependencies (`aiohttp-retry`, `python-dateutil`, `urllib3`, `typing-extensions`)

## [0.2.3] - 2026-03-28 [yanked]

### Fixed
- Attempted to fix migration V3 crash but still had broken migration infrastructure

## [0.2.2] - 2026-03-28 [yanked]

### Fixed
- Attempted in-process bank bootstrap but shipped with broken migration V3

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
