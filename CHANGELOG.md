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

## [0.5.0] - 2026-04-14

### Changed (BREAKING)

- **Template layer converged onto upstream Hindsight `BankTemplateManifest`.** Replaces the parallel Pydantic hierarchy (`MarketplaceTemplate`, `DirectiveSeed`, `MentalModelSeed`, `EntityLabel`, `EntityLabelValue`) with direct imports from `hindsight_api.api.http`. Templates are now opaque upstream JSONB; HindClaw only owns the governance wrapper (catalog metadata, scope, owner, source attribution, IAM gating). Net delta −395 lines across `template_models.py`, `models.py`, `db.py`, `http_models.py`, `bank_bootstrap.py`, `marketplace.py`, `http.py`. Spec at `docs/rkstack/specs/hindclaw/2026-04-13-template-upstream-convergence-design.md`.
- **`bank_templates` and `template_sources` DDL rewritten** with surrogate `row_id BIGSERIAL` primary key, `NULLS NOT DISTINCT` unique index on the natural key, GIN index on `tags JSONB`, and CHECK constraint on `(scope, owner)`. The natural key is now `(id, scope, owner)` for `bank_templates` and `(name, scope, owner)` for `template_sources`. Per project rule "no DB migrations until production," the tables are recreated from scratch on first deploy.
- **`TemplateRecord` collapsed to 16 fields** with manifest stored as opaque `dict`. Source attribution moves into five dedicated columns (`source_name`, `source_scope`, `source_template_id`, `source_url`, `source_revision`). The previous 40-field shape is gone.
- **`/ext/hindclaw/me/templates` and `/ext/hindclaw/admin/templates` route set rebuilt** around the `(id, scope, owner)` identity tuple. New endpoints: `POST /…/templates/{id}/install`, `POST /…/templates/{id}/update` (re-fetch from source), `GET /…/templates/{id}/check-update`, `PATCH /…/templates/{id}` (hand-edit), `POST /…/templates` (create from inline manifest). Server-scope routes are gated on `template:admin`, personal routes on `template:list`/`template:create`/`template:install`/`template:manage`. Shared install/update/check-update logic factored into private helpers.
- **`POST /ext/hindclaw/banks` rebuilt** to delegate to upstream's `apply_bank_template_manifest()` via `RequestContext(internal=True)`. Body now takes `template: "{scope}/{id}"` instead of a per-field selector. Dual IAM check: `bank:create` + `template:list`.
- **`bank_bootstrap.py` reduced from 207 to 97 lines.** Single function (`bootstrap_bank_from_template`) parses the stored manifest, runs upstream's `validate_bank_template`, touches the bank via `get_bank_profile` + `update_bank`, and delegates to `apply_bank_template_manifest()`.
- **`marketplace.py` rewritten around `fetch_and_resolve_template()`** returning `(CatalogEntry, BankTemplateManifest, revision)` with composite revision strings for templates that use `manifest_file` references. Preserves the existing `_resolve_file_url` GitHub/GitLab URL munging. Old `MarketplaceIndex`, `fetch_template`, `validate_template`, `search_marketplace`, and `MarketplaceTemplate` parsing helpers removed.
- **`db.create_template_source` accepts a `description` kwarg** and `TemplateSourceRecord` now carries `description` and `updated_at`. Required for the Plan C default-source registration hook.
- **Tier 1 test suite rewritten:** `test_template_models`, `test_db_templates`, `test_http_models`, `test_bank_bootstrap`, `test_marketplace_template`, `test_models`. New `tests/test_upstream_imports.py` is the single drift-detection chokepoint for upstream symbol surface — fails fast if Hindsight renames any of `BankTemplateManifest`, `validate_bank_template`, `apply_bank_template_manifest`, `RequestContext.internal`, `parse_entity_labels`, or the `BankTemplateConfig` configurable-field set patched in by `hindsight-api-slim` v0.5.1+patch.

### Added

- **`hindclaw_ext.template_models.Catalog` + `CatalogEntry`** Pydantic models that parse upstream's `hindsight-docs/src/data/templates.json` byte-for-byte AND HindClaw's own catalog format (with `manifest_file` references). The exclusive-or invariant between inline `manifest` and `manifest_file` is enforced by a `model_validator`.
- **`fetch_installed_template_for_apply(pool, *, template, current_user)`** in `db.py` parses a `"{scope}/{id}"` string and returns the matching installed `TemplateRecord` (server scope owner=NULL, personal scope owner=current_user). Used by `POST /banks` to resolve the template ref.
- **`pyproject.toml` aligned with upstream Hindsight tooling** — same ruff config, same ty rules block, `[dependency-groups]` (PEP 735), `pytest-rerunfailures`, `pytest-xdist`, `pytest-timeout`, `asyncio_mode = "auto"`, `asyncio_default_fixture_loop_scope = "function"`. ty type checker now passes clean across `hindclaw_ext/` (was 14 errors before cleanup).
- **OpenAPI metadata on every template route** (`operation_id`, `summary`, `tags`) so the generated client SDKs and Swagger UI render readable documentation.

### Removed

- `MarketplaceTemplate`, `DirectiveSeed`, `MentalModelSeed`, `EntityLabel`, `EntityLabelValue`, `_VALID_EXTRACTION_MODES` from `hindclaw_ext.template_models`.
- `upsert_template_from_marketplace`, `_row_to_template` (legacy), and the 25-parameter `create_template` signature from `hindclaw_ext.db`.
- `parse_template_ref` and the entire `template_ref.py` module — replaced by `db.fetch_installed_template_for_apply`.
- `MarketplaceIndex`, `fetch_template`, `validate_template`, `search_marketplace`, `_get_hindsight_version`, and version-gating logic from `hindclaw_ext.marketplace`. The `/ext/hindclaw/marketplace/search` route is also removed — search now flows through `fetch_and_resolve_template`.
- Legacy template HTTP routes: `POST /ext/hindclaw/me/templates/install` (no `{id}` in path), `PUT /ext/hindclaw/me/templates/{name}`, `PUT /ext/hindclaw/templates/{scope}/{name}`, `POST /ext/hindclaw/templates/install`, `POST /ext/hindclaw/templates/{scope}/{source}/{name}/update`, `GET /ext/hindclaw/marketplace/search`.
- Legacy template request/response models: `TemplateSummaryResponse`, `TemplateUpdateResponse`, `DirectiveSeedResult`, `MentalModelSeedResult`, `MarketplaceTemplateEntry`, `MarketplaceSearchResult`, `MarketplaceSearchResponse` from `http_models.py`.

### Fixed

- Pre-existing `Optional[PolicyRecord]` and `Optional[UserRecord]` dereferences in `update_policy_endpoint` (`http.py:717`) and `get_my_profile` (`http.py:928`) now raise explicit `HTTPException` when the row vanishes between fetch and use. Surfaced by `ty check` after the upstream-aligned tooling landed.
- **`bank_bootstrap` no longer clobbers existing bank name/mission** when the target bank already exists. Previous behavior synthesized defaults for missing manifest fields and wrote them even when the current values were set, which could overwrite operator edits. The new path only writes fields the manifest explicitly provides.
- **`POST /ext/hindclaw/banks` returns a `BankCreationResponse` envelope** with `bank_id`, `template`, `bank_created`, and `import_result` instead of the bare upstream response. The previous shape leaked upstream's raw import result directly and made the wrapper clients assume a flat structure; the envelope makes the wrapper-owned fields (bank_id, template, bank_created) first-class and the nested import_result typed. Breaking for anyone consuming the old flat response.
- **`update_policy` returns HTTP 404 instead of 500** when the target policy is deleted between fetch and use. Previously the second `get_policy` call raised an uncaught `AttributeError` on `None`.
- **`_apply_patch` switched to `model_dump(exclude_unset=True)`** so PATCH semantics correctly distinguish "field omitted" from "field explicitly null". Before this fix, sending any PATCH body with a `manifest: null` field (or a default-valued kwarg in a client wrapper) would clobber the stored manifest.

### Added (post-review)

- **`force=true` query parameter** on `POST /me/templates/{id}/update` and `POST /admin/templates/{id}/update` to override the preflight check that blocks an update when the target already has local edits. Without `force`, the endpoint returns `409 Conflict` with the divergent field list.
- **Preflight `409 Conflict` on `/update` routes** when local `updated_at` is newer than the recorded `source_revision`. Prevents silent clobber of hand-edited templates during source refresh.
- **`source_owner` column** on `bank_templates` and the corresponding `source_owner` field on `TemplateRecord` / `TemplateResponse`. Required to distinguish "installed from my own marketplace source" from "installed from a server-wide source" when the same template id exists in both scopes.
- **33 new tests in `tests/test_http_templates.py`** covering `/me/templates`, `/admin/templates`, and `POST /banks` end-to-end — scope gating, ambiguity detection, force-update flow, BankCreationResponse envelope shape, policy collision semantics.

### Changed (post-review)

- **`db.create_template` is now a pure `INSERT`** instead of `INSERT ... ON CONFLICT DO UPDATE`. The ambiguity check moves into the route handler (`_create_template_impl`) where it returns a proper HTTP 409 on collision. Makes the DB layer less surprising and matches how upstream's install/update paths are structured.
- **Removed `UpdateTemplateRequest`** from `http_models.py` — no route uses it; `PatchTemplateRequest` covers every update path. Dropping it keeps the generated client surface minimal.

### Dependencies

- Bumps the minimum supported Hindsight to `hindsight-api-slim` v0.5.1 with the `BankTemplateConfig` configurable-fields patch applied (committed at `build/hindsight/patches/0001-fix-bank-template-align-with-configurable-fields.patch` in the consuming repo, filed upstream as a follow-up PR).

### Breaking changes for downstream consumers

These are tracked as separate follow-up tasks per the spec's "Out of scope for Spec 1" list:
- `hindclaw-cli` Rust commands (`template install`, `template upgrade`, `template list`) — old route paths and request shapes are gone. Needs a regen against the new OpenAPI spec.
- Generated TypeScript/Rust SDK clients in `hindclaw-clients/` — regenerate from the new OpenAPI spec.
- `hindclaw-openclaw-plugin` — imports of the deleted `MarketplaceTemplate`, `DirectiveSeed`, `MentalModelSeed`, `EntityLabel`, `EntityLabelValue` symbols will fail at extension startup. Needs a separate refactor.

## [0.4.0] - 2026-03-29

### Added
- **Self-service template endpoints** at `/me/templates` — CRUD for personal templates with ambiguity detection via `?source=` query param, plus `POST /me/templates/install` using `resolve_source()` with 409 on ambiguity
- **Self-service template source endpoints** at `/me/template-sources` — register, list, and delete personal marketplace sources (scope hardcoded to personal, owner from caller)
- **Self-service API key endpoints** at `/me/api-keys` — create, list, delete own API keys with SA credential rejection
- **Profile endpoint** `GET /me` — returns caller's user record and channels, user-only auth (no IAM check), rejects SA credentials
- **Server scope gates** on admin template write endpoints — `POST/PUT/DELETE /templates` with `scope=server` now requires `template:admin` in addition to the base action
- `_require_action` helper for second-pass policy checks after authentication
- `_require_iam_user_only` dependency combining SA credential rejection with IAM check
- `_authenticate_user` dependency for user-only auth without IAM action requirement
- `_resolve_my_template` helper with ambiguity detection — returns 404 on no match, 409 on multiple matches with disambiguation hint
- `template:user` built-in policy — regular user template operations (list, create, install, manage, source, bank:create)
- `iam:self-service` built-in policy — self-management of API keys and service accounts
- Scoped template sources with `scope` + `owner` columns, surrogate PK, partial unique indexes
- `resolve_source()` DB function — explicit scope fields with ambiguity errors
- Composite marketplace cache key `(name, scope, owner)` for scoped sources
- `source_scope` and `installed_in` fields on `MarketplaceSearchResult` (replaces `installed` boolean)
- `MeProfileResponse` model
- `InstallTemplateRequest` backward compat — accepts deprecated `source` field as alias for `source_name`
- 80 new tests including marketplace integration tests with real template data from hindclaw-templates-official
- Bank bootstrap tests verifying all config fields (retain_mission, entity_labels, dispositions, etc.) propagate from marketplace templates

### Changed
- **Admin source endpoints tightened** from `template:source` to `template:admin` — prevents regular users with `template:user` from managing server-scope sources
- **`template:admin` policy uses `template:*` wildcard** — consistent with `iam:admin` (`iam:*`) and `bank:admin` (`bank:*`), fixes lockout where `template:admin` action wasn't grantable by any policy
- **Template sources table recreated** with `scope`, `owner`, surrogate PK — migration detect drops old schema on upgrade

### Security
- **SA credential rejection on /me/api-keys and GET /me** — prevents service accounts from minting user API keys or reading user profiles, which would bypass SA scoping
- **Server scope write gate** — non-admin users can no longer create, update, or delete server-scope templates even if they have the base action (template:create, etc.)

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
