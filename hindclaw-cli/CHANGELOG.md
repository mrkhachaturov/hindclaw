# Changelog

All notable changes to `hindclaw-cli` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-03-29

### Fixed
- Switch from OpenSSL to rustls TLS backend — fixes cross-compilation failures in CI
- Fix CI runner: macos-13 (deprecated) → macos-15 for x86_64 Darwin builds

## [0.2.0] - 2026-03-29

### Added
- `hindclaw sa` top-level subcommand for self-service SA management via `/me/service-accounts`
  - `sa list/add/info/update/remove` — create and manage your own service accounts without admin access
  - `sa key add/ls/rm` — manage API keys for your service accounts
  - Update restricted to display_name only (prevents privilege escalation)
  - No disable/enable (admin-only operations)
- Short/long verb aliases across all subcommands: `ls`/`list`, `show`/`info`, `rm`/`remove`

### Changed
- Bumped hindclaw-client to 0.2.0 (adds /me/ self-service endpoint methods)

### Fixed
- Policy test fixtures updated for extension v0.3.0 schema (PolicyStatement.banks, PolicyDocument.version)
- Admin SA test creates owner user before SA (FK constraint enforced in v0.3.0)

### Improved
- Consolidated duplicated test helpers into shared `tests/common/mod.rs`

## [0.1.1] - 2026-03-28

### Fixed
- `admin sa disable/enable` no longer crashes with NOT NULL violation — sa_toggle correctly omits unchanged fields
- `admin sa update --clear-scoping-policy` now sends explicit null via raw JSON request
- `template info/export` now finds marketplace-installed templates (requires hindclaw-extension >= 0.2.6)

## [0.1.0] - 2026-03-28

### Added
- `hindclaw alias set/ls/rm` with atomic 0600 config file writes
- `hindclaw admin user` full CRUD + channels + API keys
- `hindclaw admin group` full CRUD + members
- `hindclaw admin policy` CRUD + attach/detach/entities
- `hindclaw admin sa` full CRUD + keys + disable/enable
- `hindclaw admin bank-policy` set/info/rm (JSON file input)
- `hindclaw admin resolve` debug access resolution (--user/--sa/--sender)
- `hindclaw admin source` marketplace source list/add/rm
- `hindclaw template` list/info/search/install/upgrade/create/update/remove/export/import/apply
- Output format auto-detection (pretty on TTY, JSON when piped)
- Global flags: -o (output), -v (verbose), -a (alias), -y (skip confirmation)
- Destructive operations require -y or interactive TTY confirmation
