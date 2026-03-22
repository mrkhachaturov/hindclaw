# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-21

### Added
- **JWT authentication** — per-request HMAC-SHA256 JWTs from OpenClaw hook context (replaces static API token)
- **`HindsightHttpError`** — structured HTTP error class with `.status` property for graceful 403 handling
- **`generateJwt()`** — exported function for JWT generation from `PluginHookAgentContext`
- `jwtSecret` and `clientId` in plugin config and client options

### Changed
- **Package renamed** from `hindclaw` to `hindclaw-openclaw` — reflects that hindclaw is now a multi-package ecosystem
- **Server-side access control** — permission resolution, tag injection, and strategy routing moved to `hindclaw-extension` (Python server extension). Plugin is now a thin JWT-authenticated adapter.
- All hooks (recall, retain, session-start) thread `ctx` to client methods for per-request JWT auth
- All hooks handle 403 gracefully — skip denied banks, log warning, continue
- Multi-bank recall skips denied banks and returns results from allowed banks
- `resolveAgentConfig()` simplified — no more server config extraction or topic index building
- Plugin entry point simplified — no discovery scanning, bootstrap, or sync service

### Removed
- **`src/permissions/`** module (10 files) — 4-step client-side permission algorithm, discovery scanner, merge logic
- **`src/sync/`** module (8 files) — bank config CRUD, bootstrap, plan/apply/import (replaced by Terraform)
- **9 dead client methods** — `getBankConfig`, `updateBankConfig`, `resetBankConfig`, `ensureBank`, `listDirectives`, `createDirective`, `updateDirective`, `deleteDirective`, `listTags`
- **11 type interfaces** — `ServerConfig`, `Directive`, `CreateDirectiveRequest`, `BankConfigResponse`, `CreateBankRequest`, `CreateBankResponse`, `TopicIndexEntry`, `MemoryRouting`, `RetainRouting`, `MemoryScope`, `BankConfigDirective`, `EntityLabel`, `EntityLabelValue`
- `apiToken` / `hindsightApiToken` from client and config (replaced by `jwtSecret`)
- `bankMission`, `configPath`, `bootstrap` from plugin config
- `retainTags`, `recallTags`, `recallTagsMatch` from plugin config (server-side via hindclaw-extension)
- `_serverConfig`, `_topicIndex`, `_defaultMode` from resolved config
- `resolveRecallFilter()` function
- `HINDSIGHT_EMBED_API_TOKEN` env var fallback
- `DEFAULT_BANK_MISSION` constant

## [0.1.0] - 2026-03-19

### Added
- `$include` directives — modular bank config files with recursive file resolution
- `extractTopicId()` — extracts topic ID from DM and group forum session keys

### Changed
- `extractTopicId` moved from `retain.ts` to `utils.ts` (shared by both hooks)

## [1.0.2] - 2026-03-18

### Fixed
- `loadBankConfigFiles` no longer crashes all agents on missing/malformed bank config — skips with warning
- `service.stop()` clears stale state (`turnCountBySession`, `inflightRecalls`) preventing misattributed memory after reinit
- `service.start()` logs errors instead of silently swallowing init failures
- HTTP recall timeout changed from 10s to 15s (matches `DEFAULT_TIMEOUT_MS`)

### Added
- 20+ debug logging calls across startup, init, config resolution, and bank ID derivation

### Changed
- `recallTagsMatch` and `TagGroup.match` extended with `any_strict` and `all_strict` variants
- `retainObservationScopes` type corrected to `string | string[][]`

## [1.0.1] - 2026-03-18

### Fixed
- Guard `initPromise` against re-entry — gateway loads plugin multiple times during startup/hot-reload

## [1.0.0] - 2026-03-18

### Fixed
- Bank config paths resolve relative to OpenClaw state dir
- Plugin config reads from `hindclaw` entry (was `hindsight-openclaw`)
- Inject `claude-agent-sdk` into uvx when using `claude-code` LLM provider

## [1.0.0-alpha.1] - 2026-03-18

### Added
- Per-agent bank config templates — declarative JSON5 files
- Two-level config resolution: plugin defaults → bank config file (shallow merge)
- Per-agent infrastructure overrides — different agents can connect to different Hindsight servers
- Full stateless Hindsight HTTP client — bankId per-call, no instance state
  - Retain with context, observation_scopes (items[] batch format)
  - Recall with tag_groups
  - Reflect for disposition-aware reasoning
  - Mental models (get/list)
- Multi-bank recall — `recallFrom` field for parallel recall from multiple banks
- Session start hook — load mental models at session start, inject as `<hindsight_context>`
- Reflect on recall — use Hindsight reflect API instead of raw recall per agent
- Extracted hooks into separate modules (recall, retain, session-start)

### Changed
- Rewritten from `@vectorize-io/hindsight-openclaw` (upstream reference, not a patch)
- Plugin ID: `hindclaw` (later renamed to `hindclaw-openclaw`)
- Client is stateless per-call
- Retain uses native `items[]` batch format
