# Changelog

All notable changes to `hindclaw-cli` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
