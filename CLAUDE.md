# CLAUDE.md — hindclaw

## Project

Self-hosted [Hindsight](https://hindsight.vectorize.io) management platform. Multi-tenant access control, user/group permissions, client integrations, and infrastructure tooling for running Hindsight AI memory in production.

## Repository Structure

```
hindclaw/
├── hindclaw-extension/          # Core Hindsight server extensions (Python)
├── hindclaw-cli/                # CLI tool (TypeScript, still part of core repo)
├── hindclaw-docs/               # Product docs site
├── hindclaw-integrations/
│   ├── openclaw/                # Submodule: hindclaw-openclaw-plugin
│   └── claude-code/             # Submodule: hindclaw-claude-plugin
├── hindclaw-terraform/          # Submodule: terraform-provider-hindclaw
├── .github/workflows/           # Core repo workflows
├── CLAUDE.md
├── LICENSE
└── README.md
```

## Packages

| Package | Language | Registry | Purpose |
|---------|----------|----------|---------|
| `hindclaw-extension` | Python | [PyPI](https://pypi.org/project/hindclaw-extension/) | Server-side access control extensions for Hindsight API |
| `hindclaw-cli` | TypeScript | — | CLI for bank/permission management |

## Repository Model

Hindclaw is now split between a core product repo and independently versioned component repos.

**Core repo version line:**
- `hindclaw-extension`
- `hindclaw-docs`
- `hindclaw-cli` (until extracted later)

**Independent repo version lines:**
- `hindclaw-openclaw-plugin`
- `hindclaw-claude-plugin`
- `terraform-provider-hindclaw`

The core repo pins those independent components as submodules. Their changelogs, release cadence,
and publish flows are owned in their own repositories.

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

## Publishing

**Core repo / extension**: push `ext-v*` tag — GitHub Actions publishes the Python extension via OIDC trusted publisher

**Independent components**: publish from their own repositories and changelogs, not from this repo.

## Commit Style

Conventional commits in the core repo: `feat(hindclaw-ext):`, `fix(hindclaw-cli):`, `chore:`, `docs:`

## Design Specs

In the astromech repo: `docs/superpowers/specs/hindclaw/2026-03-21-hindclaw-server-extension-design.md`
