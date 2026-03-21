# CLAUDE.md — hindclaw-openclaw

## Package

npm: `hindclaw-openclaw` — Hindsight memory plugin for OpenClaw. JWT-authenticated thin adapter — server handles access control, tags, and strategies via `hindclaw-extension`.

## Stack

TypeScript (ESM), Node.js 22+, Vitest, JSON5

## Structure

```
src/
├── index.ts              # Plugin entry: read config, create client, register hooks
├── client.ts             # HindsightClient (HTTP + subprocess), generateJwt(), HindsightHttpError
├── config.ts             # resolveAgentConfig(), loadBankConfigFiles(), $include resolution
├── types.ts              # PluginConfig, BankConfig, ResolvedConfig, API types
├── hooks/
│   ├── recall.ts         # handleRecall() — query build, single/multi-bank, reflect path, 403 handling
│   ├── retain.ts         # handleRetain() — transcript build, chunked retention, 403 handling
│   └── session-start.ts  # handleSessionStart() — mental model loading, 403 handling
├── derive-bank-id.ts     # deriveBankId() — bank ID from agent/channel/user context
├── embed-manager.ts      # HindsightEmbedManager — subprocess daemon lifecycle
├── format.ts             # formatMemories(), formatCurrentTimeForRecall()
├── utils.ts              # extractRecallQuery(), composeRecallQuery(), stripMemoryTags(), extractTopicId()
├── debug.ts              # debug() — conditional logging via HINDCLAW_DEBUG env var
└── moltbot-types.ts      # OpenClaw SDK type stubs (MoltbotPluginAPI, ServiceConfig)
```

## Commands

```bash
npm install               # install dependencies
npm run build             # tsc → dist/
npm test                  # vitest run src (176 unit tests)
npm run test:integration  # vitest with integration config (requires live server)
npm run dev               # tsc --watch
```

## Architecture

The plugin is a thin JWT-authenticated adapter. All access control decisions happen server-side via `hindclaw-extension` (Python).

**Plugin responsibilities:**
- Generate per-request HMAC-SHA256 JWT from OpenClaw hook context (sender, agent, channel, topic)
- Build recall queries from conversation context (multi-turn, metadata stripping)
- Build retain transcripts from messages (role filtering, tag stripping, chunked windows)
- Handle 403 gracefully (skip denied banks, log, continue)
- Multi-bank orchestration (parallel recall, round-robin interleave)
- Subprocess mode fallback via embed-manager

**Server responsibilities (hindclaw-extension):**
- JWT validation and sender-to-user resolution
- Permission enforcement (recall/retain allow/deny → 403)
- Tag injection (user:X, agent:X, group tags) via accept_with()
- Strategy cascade (agent→channel→topic→group→user)
- Bank config management (REST API for Terraform)

## Key Patterns

- **Two-level config**: plugin defaults + bank config file overrides (shallow merge, bank file wins)
- **Stateless client**: every method takes `bankId` first, no instance-level bank state
- **JWT per request**: `httpHeaders(ctx)` generates fresh JWT from PluginHookAgentContext
- **Graceful degradation**: all hooks catch 403 and non-fatal errors, never crash the gateway
- **In-flight dedup**: concurrent recalls for same bank+query hash reuse one promise

## Config

Plugin config is in `.openclaw/config/plugins.json5` under `hindclaw` key. Key fields:

| Field | Purpose |
|-------|---------|
| `hindsightApiUrl` | External Hindsight API URL |
| `jwtSecret` | HMAC-SHA256 secret (must match server's HINDCLAW_JWT_SECRET) |
| `clientId` | JWT client_id claim (default: "openclaw") |
| `autoRecall` / `autoRetain` | Enable/disable automatic recall/retain |
| `recallBudget` / `recallMaxTokens` | Recall effort and token limits |
| `agents` | Map of agentId → { bankConfig: "path" } for per-agent config |

Bank config files (JSON5) override plugin defaults per agent. Loaded via `loadBankConfigFiles()` with `$include` directive support.

## Testing

- Unit tests: `src/**/*.test.ts` (176 tests, mocked fetch/client)
- Integration tests: `tests/**/*.test.ts` (require live Hindsight API)
- Test helpers: `makeClient()` returns mock with vi.fn() stubs for all client methods

## Publishing

Push `v*` tag → GitHub Actions publishes to npm via token. Bump version in `package.json`, add changelog entry, commit, tag, push.
