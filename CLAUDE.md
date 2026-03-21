# CLAUDE.md — hindclaw

## Project

Self-hosted [Hindsight](https://hindsight.vectorize.io) management platform. Multi-tenant access control, user/group permissions, client integrations, and infrastructure tooling for running Hindsight AI memory in production.

## Repository Structure

```
hindclaw/
├── hindclaw-extension/          # pip: hindclaw-extension — Hindsight server extensions (Python)
│   ├── hindclaw_ext/            #   TenantExtension, OperationValidatorExtension, HttpExtension
│   └── tests/                   #   71 tests (pytest, mocked asyncpg)
├── hindclaw-integrations/
│   └── openclaw/                # npm: hindclaw — OpenClaw plugin (TypeScript)
│       ├── src/                 #   hooks (recall, retain, session-start), config, client, sync
│       └── tests/               #   164 unit tests (vitest) + integration tests
├── hindclaw-cli/src/            # CLI tool (TypeScript, being extracted)
├── hindclaw-docs/               # hindclaw.pro — Docusaurus documentation site
├── .github/workflows/           # publish-plugin.yml, publish-extension.yml, deploy-docs.yml
├── CLAUDE.md
├── LICENSE
└── README.md
```

## Packages

| Package | Language | Registry | Purpose |
|---------|----------|----------|---------|
| `hindclaw-extension` | Python | [PyPI](https://pypi.org/project/hindclaw-extension/) | Server-side access control extensions for Hindsight API |
| `hindclaw` | TypeScript | [npm](https://www.npmjs.com/package/hindclaw) | OpenClaw integration plugin |
| `hindclaw-cli` | TypeScript | — | CLI for bank/permission management |

## Stack

- **Server extension**: Python 3.12, asyncpg, PyJWT, Pydantic, FastAPI
- **OpenClaw plugin**: TypeScript (ESM), Node.js 22+, Vitest, JSON5
- **Docs**: Docusaurus, Cloudflare Pages

## hindclaw-extension (Python)

Server-side access control via three Hindsight extensions:

- **HindclawTenant** — JWT / API key auth, sender-to-user resolution
- **HindclawValidator** — recall/retain/reflect enforcement with tag/strategy enrichment
- **HindclawHttp** — REST API at `/ext/hindclaw/` for users, groups, permissions, strategies

```bash
cd hindclaw-extension
pip install -e ".[dev]"
pytest tests/ -v              # 71 tests
```

### Python Style

Code follows upstream Hindsight conventions (studied from `hindsight-api-slim/`):

- **Pydantic `BaseModel`** for all structured data — never raw `dict`
- **Google-style docstrings** with `Args:`, `Returns:`, `Raises:`
- **Immutability** — `model_copy()`, never mutate arguments
- **Async throughout** — raw `asyncpg`, lazy pool init via `asyncio.Lock`
- **Type hints** — `str | None` syntax, no `Optional`
- **Testing** — `pytest-asyncio` strict mode, `autouse` fixtures, mocked asyncpg

## hindclaw-integrations/openclaw (TypeScript)

OpenClaw plugin — hooks into recall/retain/session-start lifecycle:

```bash
cd hindclaw-integrations/openclaw
npm install && npm run build
npm test                      # 164 unit tests
```

### Key Patterns

- **Two-level config**: Plugin defaults + bank config file overrides (shallow merge, bank file wins)
- **Stateless client**: Every method takes `bankId` first. No instance-level bank state.
- **Graceful degradation**: All hooks catch errors and log. Never crash the gateway.

## Publishing

**PyPI** (extension): push `ext-v*` tag — GitHub Actions publishes via OIDC trusted publisher

**npm** (plugin): push `v*` tag — GitHub Actions publishes via npm token
- Bump version in `hindclaw-integrations/openclaw/package.json`
- Add changelog entry in `CHANGELOG.md` with the same version
- Commit, tag, push

## Commit Style

Conventional commits: `feat(hindclaw-ext):`, `fix(openclaw):`, `chore:`, `docs:`

## Design Specs

In the astromech repo: `docs/specs/2026-03-21-hindclaw-server-extension-design.md`
