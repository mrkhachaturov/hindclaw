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

## Workaround Lifecycle Discipline

HindClaw is a layer on top of upstream Hindsight. Sometimes we need code paths
that exist only because upstream has not caught up with a feature, fix, or
publishing change yet. Those code paths must be marked clearly so the next
person who touches the file knows whether they are looking at the long-term
shape of the project or at a temporary bridge.

**Rationale**: Without this discipline, temporary workarounds calcify into
accidental architecture. Six months later nobody remembers which code is the
"right" shape and which is a bridge waiting to be removed, so the bridge
stays forever and the project drifts away from upstream. This rule was
established during the 2026-04 client-generator alignment work after we found
a Dockerfile `sdk-builder` stage that existed only because upstream had not
yet published `@vectorize-io/hindsight-client` to npm — by the time we noticed,
upstream had published it months earlier and the workaround had become invisible.

### Three categories

Every code path tied to an upstream limitation falls into exactly one of these:

**1. STEADY STATE** — the target shape. No workaround. Written as if upstream
already supports what we need. No special marker required.

**2. TEMPORARY** — exists because of a specific upstream gap that we are
actively closing (filed PR, filed issue, or pinned to a known release). Must
carry a marker comment in this exact format:

```
# TEMPORARY: <one-line reason>
# Tracked: <link to upstream PR or issue, or "no PR yet — see <design-doc>">
# Replace with: <exact code or pattern that should run once upstream merges>
```

The "Replace with" line is non-negotiable. If you cannot describe the
post-merge code path, you do not understand the workaround well enough to
mark it temporary — clarify the design first.

**3. PERMANENT WORKAROUND** — exists because of an upstream limitation that
is unlikely to change soon (missing tooling feature, deliberate upstream
design choice we disagree with, infrastructure gap with no fix in sight).
Must carry:

```
# PERMANENT WORKAROUND: <one-line reason>
# Long-term resolution: <link to issue/discussion, or "none — accepted limitation">
```

### Anti-patterns

- **Commenting out obsolete workarounds.** When the upstream condition that
  necessitated a workaround changes (e.g., upstream starts publishing the
  package we used to build locally), DELETE the workaround. Do not leave it
  commented out "in case we need it later" — git history is the archive.
- **TEMPORARY marker without a tracked PR/issue.** If there is genuinely no
  upstream tracker yet, the marker must say so explicitly and link to a
  HindClaw-side design doc that explains why we are blocked. "TEMPORARY,
  TODO file PR later" is not acceptable — file the PR or escalate.
- **Letting steady-state code reference the temporary path.** Steady-state
  code must be readable in isolation. If a steady-state function only works
  because some other module is using a temporary workaround, that coupling
  itself is a workaround and needs its own marker.

### Examples

**Dockerfile `api-builder` stage, transitional state (2026-04):**
```dockerfile
# === STEADY STATE (uncomment when Plan A patch lands upstream) ============
# RUN uv pip install hindsight-api-slim==0.5.2  # release containing the patch
# ==========================================================================

# TEMPORARY: editable install of patched hindsight-api-slim
# Tracked: build/hindsight/patches/0001-fix-bank-template-align-with-configurable-fields.patch
#          (filed as upstream PR — link when opened)
# Replace with: the steady-state line above, once build/hindsight/UPSTREAM_VERSION
#               points to a release containing the merged patch.
COPY hindsight-api-slim/pyproject.toml ./api/
COPY hindsight-api-slim/hindsight_api ./hindsight_api
RUN uv pip install -e .
```

**Terraform provider `go.mod` (permanent for now):**
```
// PERMANENT WORKAROUND: upstream Hindsight does not tag Go modules,
// so we publish hindsight-clients/go from our fork mrkhachaturov/hindsight
// and consume it through a `replace` directive.
// Long-term resolution: none — upstream considers Go module tagging out of scope.
replace github.com/vectorize-io/hindsight/hindsight-clients/go => github.com/mrkhachaturov/hindsight/hindsight-clients/go v0.4.20
```

**hindclaw-clients/rust forced duplication of upstream types:**
```rust
// PERMANENT WORKAROUND: progenitor generates all types inline into a single
// .rs file in OUT_DIR, so HindClaw's Rust client cannot import upstream
// types from a separate crate the way the TS/Python/Go clients do.
// Long-term resolution: none — would require an upstream feature in
// progenitor for cross-crate type imports.
```

### When upstream catches up

When a tracked PR is merged or a tracked issue is closed, the cleanup is
exactly two steps:

1. Find every TEMPORARY marker that references the now-resolved tracker.
2. Replace the temporary block with the "Replace with" pattern, then DELETE
   the marker comment entirely.

The cleanup commit message should reference the upstream PR number and list
every file touched, so the trace is permanent in git history.

## Design Specs

In the astromech repo, under `docs/rkstack/specs/hindclaw/`:

- `2026-03-21-hindclaw-server-extension-design.md` — original server extension architecture
- `2026-04-13-template-upstream-convergence-design.md` — Plan B template convergence (extension v0.5.0+, templates v2.0.0+)
