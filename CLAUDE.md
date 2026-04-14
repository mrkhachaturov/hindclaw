# CLAUDE.md — hindclaw

## Project

Self-hosted [Hindsight](https://hindsight.vectorize.io) management platform. Multi-tenant access control, user/group permissions, client integrations, and infrastructure tooling for running Hindsight AI memory in production.

## Repository Structure

```
hindclaw/
├── hindclaw-extension/          # Core Hindsight server extensions (Python)
├── hindclaw-cli/                # CLI tool (Rust)
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
| `hindclaw-cli` | Rust | — | CLI for managing HindClaw access control |

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
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -v          # 294 tests
.venv/bin/python -m ruff check hindclaw_ext/  # lint
.venv/bin/python -m ruff format --check hindclaw_ext/ tests/
.venv/bin/python -m ty check hindclaw_ext/    # type check
```

### Python Style

Code follows upstream Hindsight conventions (studied from `hindsight-api-slim/`).
The `pyproject.toml` ruff + ty + pytest config is kept in lockstep with upstream.

- **Pydantic `BaseModel`** for all structured data — never raw `dict`. Template
  content is the only exception: it lives as opaque JSONB and parses through
  upstream's `BankTemplateManifest` on the way in/out.
- **Google-style docstrings** with `Args:`, `Returns:`, `Raises:`
- **Immutability** — `model_copy()`, never mutate arguments. `TemplateRecord`
  is a `@dataclass` (not Pydantic) because it's a thin DB row, not validated input.
- **Async throughout** — raw `asyncpg`, lazy pool init via `asyncio.Lock`
- **Type hints** — `str | None` syntax, no `Optional`. ty type-checks
  `hindclaw_ext/` clean.
- **Testing** — `pytest-asyncio` `auto` mode (mirrors upstream),
  `autouse` fixtures, mocked asyncpg, `pytest-rerunfailures` for flaky integration
  paths, `pytest-xdist` available for parallel runs. `tests/test_upstream_imports.py`
  is the single drift-detection chokepoint for the upstream symbol surface
  HindClaw imports — fails fast if Hindsight renames anything HindClaw depends on.
- **Helpers over duplication** — when two routes share construction logic
  (e.g. `/me/templates/install` and `/admin/templates/install`), extract a
  shared `_do_*` helper rather than copy-pasting the body.

## Publishing

**Core repo / extension**: push `ext-v*` tag — GitHub Actions publishes the Python extension via OIDC trusted publisher

**Independent components**: publish from their own repositories and changelogs, not from this repo.

## Commit Style

Conventional commits in the core repo: `feat(hindclaw-ext):`, `fix(hindclaw-cli):`, `chore:`, `docs:`

## Design Specs

In the astromech repo, under `docs/rkstack/specs/hindclaw/`:

- `2026-03-21-hindclaw-server-extension-design.md` — original server extension architecture
- `2026-04-13-template-upstream-convergence-design.md` — Plan B template convergence (extension v0.5.0+, templates v2.0.0+)
