---
sidebar_position: 5
title: Development
---

# Development

## Setup

```bash
git clone git@github.com:mrkhachaturov/hindclaw.git
cd hindclaw
npm install
npm run build    # TypeScript -> dist/
npm test         # unit tests
```

## Source Structure

```
src/
├── index.ts              # Plugin entry: init + hook registration
├── client.ts             # Stateless Hindsight HTTP client (bankId per-call)
├── types.ts              # Full type system
├── config.ts             # Config resolver + bank file parser + $include
├── utils.ts              # Shared utilities
├── hooks/
│   ├── recall.ts         # before_prompt_build (single + multi-bank + reflect)
│   ├── retain.ts         # agent_end (tags, context, observation_scopes)
│   └── session-start.ts  # session_start (mental models)
├── sync/
│   ├── plan.ts           # Diff engine: file vs server state
│   ├── apply.ts          # Execute changeset against Hindsight API
│   ├── import.ts         # Pull server state into local file
│   └── bootstrap.ts      # First-run apply if bank is empty
├── permissions/
│   ├── types.ts          # User, Group, Permission types + validation
│   ├── discovery.ts      # Config directory scanner + index builder
│   ├── resolver.ts       # 4-step permission resolution algorithm
│   ├── merge.ts          # Group merge rules
│   └── index.ts          # Barrel export
├── cli/
│   ├── index.ts          # hindclaw CLI entry point
│   └── init.ts           # hindclaw init command
├── embed-manager.ts      # Local daemon lifecycle
├── derive-bank-id.ts     # Bank ID derivation
└── format.ts             # Memory formatting
```

## Key Patterns

**Two-level config.** Plugin defaults in `openclaw.json` + bank config file overrides. Shallow merge, bank file wins.

**Stateless client.** Every client method takes `bankId` as first parameter. No instance-level bank state. Enables multi-bank operations.

**Server-side vs behavioral.** `snake_case` fields = server-side (synced to Hindsight via CLI). `camelCase` fields = behavioral (used by hooks at runtime).

**Graceful degradation.** All hooks catch errors and log warnings. Never crash the gateway.

## Testing

```bash
npm test                   # unit tests (vitest)
npm run test:integration   # needs running Hindsight API
```

Integration test environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `HINDSIGHT_API_URL` | `http://localhost:8888` | Hindsight server URL |
| `HINDSIGHT_API_TOKEN` | -- | Auth token (optional) |

## Publishing

Push a `v*` tag -- GitHub Actions publishes to npm via OIDC trusted publisher.

Before tagging:

1. Bump version in `package.json`
2. Add changelog entry in `CHANGELOG.md` with the exact same version (workflow reads it by tag)
3. Commit both files
4. Tag and push

```bash
git tag v0.2.0
git push origin main --tags
```
