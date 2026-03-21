# CLAUDE.md — hindclaw

## Project

Production-grade Hindsight memory plugin for OpenClaw. Replaces the upstream `@vectorize-io/hindsight-openclaw` with per-agent bank config templates, multi-bank recall, session start context, reflect, and IaC-style bank management via `hindclaw` CLI.

## Stack

- TypeScript (ESM, `"type": "module"`)
- Node.js 22+
- Vitest for testing
- JSON5 for bank config file parsing
- OpenClaw plugin SDK (`MoltbotPluginAPI`)

## Setup

```bash
npm install
npm run build    # TypeScript → dist/
npm test         # 164 unit tests
```

## Structure

```
src/
├── index.ts              # Plugin entry: init + hook registration (~600 lines)
├── client.ts             # Stateless Hindsight HTTP client (bankId per-call)
├── types.ts              # Full type system (plugin config, bank config, API types)
├── config.ts             # resolveAgentConfig(), bank file parser, file loader
├── moltbot-types.ts      # OpenClaw SDK types (kept from upstream)
├── hooks/
│   ├── recall.ts         # before_prompt_build (single + multi-bank + reflect)
│   ├── retain.ts         # agent_end (tags, context, observation_scopes)
│   └── session-start.ts  # session_start (mental models)
├── sync/
│   ├── plan.ts           # Diff engine: file vs server state → changeset
│   ├── apply.ts          # Execute changeset against Hindsight API
│   ├── import.ts         # Pull server state into local file
│   └── bootstrap.ts      # First-run apply if bank is empty
├── cli/
│   └── index.ts          # hindclaw CLI entry point (plan/apply/import)
├── embed-manager.ts      # Local daemon lifecycle (kept from upstream)
├── derive-bank-id.ts     # Bank ID derivation from context
└── format.ts             # Memory formatting for injection
```

## Key Patterns

- **Two-level config**: Plugin config (openclaw.json) has defaults. Bank config files (JSON5) override per-agent. Resolution: shallow merge, bank file wins.
- **Stateless client**: Every client method takes `bankId` as first parameter. No instance-level bank state. Enables multi-bank operations.
- **Server-side vs behavioral**: Bank config fields are split into server-side (applied to Hindsight API via sync) and behavioral (used by hooks at runtime). Field name convention: snake_case = server-side, camelCase = behavioral.
- **Infrastructure as Code**: Bank config files are source of truth. `hindclaw plan/apply` manages server state. Directives not in file get deleted.
- **Bootstrap**: One-time apply on first run for empty banks. After that, managed via CLI.
- **Graceful degradation**: All hooks catch errors and log warnings. Never crash the gateway.

## Config Architecture

```
Plugin config (openclaw.json)         Bank config file (banks/*.json5)
├── Daemon (global only)              ├── Server-side (agent-only)
│   apiPort, embedPort, etc.          │   retain_mission, entity_labels, etc.
├── Defaults (overridable)            ├── Infrastructure overrides
│   hindsightApiUrl, recallBudget     │   hindsightApiUrl (different server)
├── bootstrap: true                   ├── Behavioral overrides
└── agents: { id: { bankConfig } }    │   recallBudget, retainTags, etc.
                                      ├── recallFrom (multi-bank)
                                      ├── sessionStartModels
                                      └── reflectOnRecall
```

## Testing

```bash
npm test                        # unit tests (vitest, 164 tests)
npm run test:integration        # integration tests (needs Hindsight API)
```

Integration tests require:
- `HINDSIGHT_API_URL` (default: `http://localhost:8888`)
- `HINDSIGHT_API_TOKEN` (optional)

## Publishing

Push a `v*` tag — GitHub Actions publishes to npm via OIDC trusted publisher.

**MANDATORY before tagging:**
1. Bump version in `package.json`
2. Add changelog entry in `CHANGELOG.md` with the **exact same version** — the workflow reads changelog by tag version and **will fail** if the entry is missing
3. Commit both files
4. Then tag and push

```bash
# Example:
# 1. Edit package.json: "version": "1.0.0-alpha.3"
# 2. Edit CHANGELOG.md: ## [1.0.0-alpha.3] - YYYY-MM-DD
# 3. git add package.json CHANGELOG.md && git commit -m "chore: bump v1.0.0-alpha.3"
# 4. git tag v1.0.0-alpha.3
# 5. git push origin main --tags
```

## CLI: hindclaw

```bash
hindclaw plan --all              # diff local files vs server
hindclaw apply --agent r4p17     # apply changes
hindclaw import --agent r4p17 --output ./banks/r4p17.json5
```

## Upstream Reference

The original plugin source is at `3rdparty-src/for Memory/hindsight/hindsight-integrations/openclaw/src/`. Kept from upstream: LLM detection, external API detection, health checks, embed manager, derive-bank-id, format-memories. Rewritten: client, types, hooks, config, sync, CLI.

## Python Style (hindclaw-extension)

The `hindclaw-extension/` package is a Python extension for the Hindsight API server. Code must follow the upstream Hindsight Python conventions (studied from `hindsight-api-slim/`) so this extension can become an official Hindsight plugin.

### Data modeling

- **Pydantic `BaseModel`** for all structured data — never raw `dict` for fields passed between functions
- All-optional fields use `T | None = None` — None means "not set by any source"
- Use `model_copy()` to produce new instances, never mutate in place
- Use `model_dump(exclude={...})` when converting to dict for iteration

### Functions and docstrings

- Google-style docstrings with `Args:`, `Returns:`, `Raises:` on all public functions
- One-liner docstrings are acceptable only for trivial private helpers (`_parse_json`)

```python
async def get_user_by_channel(provider: str, sender_id: str) -> UserRecord | None:
    """Resolve channel sender to user.

    Args:
        provider: Channel provider name (e.g., "telegram").
        sender_id: Provider-specific sender identifier.

    Returns:
        UserRecord if found, None otherwise.
    """
```

### Immutability — return new, don't mutate

Per Nicolò (upstream maintainer): "the clean way is the extension returns new contents, not modifying the passed one." Overlay functions return new objects via `model_copy()` or `dataclasses.replace()`, never mutate the input.

### Async and database

- Async throughout — all DB functions are `async def`
- Raw `asyncpg` for queries (not SQLAlchemy) — the extension manages its own pool
- Lazy pool init via `asyncio.Lock` double-check pattern
- DDL via `CREATE TABLE IF NOT EXISTS` wrapped in a transaction
- Env vars read from `os.environ` directly, not from `self.config` (extension prefix isolation)

### Testing

- `pytest` + `pytest-asyncio` with `asyncio_mode = "strict"`
- `autouse` fixtures for env var and module state cleanup (`monkeypatch.setenv`, yield-based reset)
- Mock asyncpg — no real database needed for unit tests
- Test utilities in `tests/helpers.py` (not conftest direct imports)

### Type hints

- Python 3.11+ union syntax: `str | None`, `list[str]`, not `Optional[str]` or `List[str]`
- No `from __future__ import annotations` — use native syntax

### Field sets

Use tuple constants for shared field lists iterated across models:

```python
_PERMISSION_FIELDS = (
    "recall", "retain", "retain_roles", "retain_tags", ...
)
```

### Commit style

Same as astromech — conventional commits: `feat(hindclaw-ext):`, `fix(hindclaw-ext):`, `test(hindclaw-ext):`

## Design Spec

`docs/specs/2026-03-18-hindsight-astromech-v1-design.md` in the astromech repo.
