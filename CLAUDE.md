# CLAUDE.md — hindclaw

## Project

Self-hosted [Hindsight](https://hindsight.vectorize.io) management platform. Multi-tenant access control, user/group permissions, client integrations, and infrastructure tooling for running Hindsight AI memory in production.

## Repository Structure

```
hindclaw/
├── packages/extension/          # Core Hindsight server extensions (Python)
├── packages/cli/                # CLI tool (Rust)
├── apps/docs/               # Product docs site
├── integrations/
│   ├── openclaw/                # Submodule: hindclaw-openclaw-plugin
│   └── claude-code/             # Submodule: hindclaw-claude-plugin
├── terraform/          # Submodule: terraform-provider-hindclaw
├── .github/workflows/           # Core repo workflows
├── .mise/tasks/                 # Repo-level file tasks
├── mise.toml                    # Monorepo root: tools, task DAGs
├── mise.lock                    # Pinned tools, linux-x64/arm64 + macos-arm64
├── hk.pkl                       # Git-lifecycle gate
├── flint.toml                   # Linter scope
├── CLAUDE.md
├── LICENSE
└── README.md
```

## Packages

| Package | Language | Registry | Purpose |
|---------|----------|----------|---------|
| `hindclaw-extension` | Python | [PyPI](https://pypi.org/project/packages/extension/) | Server-side access control extensions for Hindsight API |
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
- **Docs**: Astro 7 + fumadocs, Tailwind 4, static build to Cloudflare Pages
- **Toolchain**: mise (monorepo tasks), hk (git hooks), flint (linters), biome

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

### Client test suites

The four generated clients have their own smoke-test scaffolds. Run each from the HindClaw repo root.

```bash
# TypeScript (jest + ts-jest + @hey-api/openapi-ts)
cd packages/clients/typescript && npm test

# Python (pytest + pytest-asyncio with uvicorn in-process fixture)
cd packages/clients/python && .venv/bin/python -m pytest tests/ -v

# Go (httptest + httptrace)
cd packages/clients/go && go test ./...

# Rust (mockito + serde_json round-trip)
cd packages/clients/rust && cargo test
```

## Scripts

Repo-level automation under `scripts/`. Each script is idempotent and runnable from the HindClaw repo root.

| Script | Purpose |
|---|---|
| `scripts/extract-openapi.py` | Extract FastAPI/Pydantic OpenAPI spec to `apps/docs/public/openapi.json` (no running server needed). |
| `scripts/generate-openapi.sh` | Shell wrapper around `extract-openapi.py`. Pass `--build-docs` to also build the docs site. |
| `scripts/generate-clients.sh` | Regenerate Go/Python/TypeScript clients against the OpenAPI spec. Copies the spec to `packages/clients/rust/openapi.json` for the crates.io publish path. |
| `scripts/generate-docs-skill.sh` | Regenerate `skills/hindclaw-docs/references/` from `apps/docs/docs/`. Converts `.mdx` to `.md`, copies openapi.json, preserves the hand-written `SKILL.md`. |
| `scripts/sync-upstream-pins.sh` | Rewrite Python and TypeScript upstream hindsight pins. Reads `UPSTREAM_HINDSIGHT_VERSION` and optional `UPSTREAM_HINDSIGHT_COMMIT`. See "Upstream version tracking" below. |

## Toolchain

Tools are pinned in `mise.toml` and locked in `mise.lock` for linux-x64, linux-arm64 and
macos-arm64, so CI installs the same binaries by checksum without hitting any registry API.

```bash
mise install            # tools; also installs the hk hooks via postinstall
mise tasks --all        # every task in the monorepo
```

The repo is a mise monorepo. `hindclaw-docs` and `hindclaw-extension` are config roots with
their own `mise.toml`, so their tasks are addressed by path:

```bash
mise run //apps/docs:dev          # docs dev server on :4321
mise run //apps/docs:build        # static build into apps/docs/dist
mise run //apps/docs:check        # lint, typecheck, test, build
mise run //apps/docs:sync-search  # push the search index to Typesense
mise run //packages/extension:check   # ruff, ty, pytest
mise run lint                         # flint across the whole tree
mise run check                        # everything that gates a push
```

From inside a config root the prefix collapses to `:` — `mise run :build`.

`hk.pkl` is the git gate. `pre-commit` runs hygiene, the secret scan and the fast linters
through flint; `pre-push` runs the two subproject `check` tasks, which need `node_modules`
and a synced `.venv`. `hk check` is the manual and CI entrypoint. Bypass one command with
`HK=0 git commit …`.

`flint.toml` scopes the linters. Generated clients, submodules and vendored UI components
are excluded — flint hands each path to its linter explicitly, and a run whose every path
was ignored is an error rather than a no-op.

`.infisicalignore` holds fingerprints of reviewed findings: base64 blobs in the deleted
Docusaurus `.api.mdx` pages and API-key fixtures in the extension tests.

## Upstream version tracking

HindClaw depends on upstream Hindsight and often tracks features that are merged upstream but not yet released. The repo root has two files that express the current state:

- `UPSTREAM_HINDSIGHT_VERSION` — always present. Latest released upstream semver (bare, no `v` prefix).
- `UPSTREAM_HINDSIGHT_COMMIT` — optional. When present, holds a commit SHA that HindClaw depends on but which predates the next upstream release.

**Two states:**

| State | `UPSTREAM_HINDSIGHT_COMMIT` | Python pin | TypeScript pin |
|---|---|---|---|
| Released | missing/empty | `"hindsight-client==X.Y.Z"` | `"@vectorize-io/hindsight-client": "X.Y.Z"` |
| Pre-release | set to a merge SHA | git-ref install at the SHA | still released version + vendor shim |

Go and Rust are intentionally skipped: Go uses fork+replace directive in `terraform-provider-hindclaw`, Rust has a `PERMANENT WORKAROUND` in `packages/clients/rust/build.rs` (no upstream Rust crate).

**Flow when upstream merges a PR HindClaw needs:**

```bash
echo "<merge_sha>" > UPSTREAM_HINDSIGHT_COMMIT
bash scripts/sync-upstream-pins.sh
bash scripts/generate-clients.sh  # regenerate against the pinned upstream
git add -A && git commit -m "chore(deps): track upstream PR #<N> at <sha>"
```

**Flow when upstream publishes a release containing your commit:**

```bash
rm UPSTREAM_HINDSIGHT_COMMIT
echo "X.Y.Z" > UPSTREAM_HINDSIGHT_VERSION
bash scripts/sync-upstream-pins.sh
git add -A && git commit -m "chore(deps): bump upstream to X.Y.Z (released)"
```

The `.github/workflows/version-coherence.yml` CI job enforces that the declared state (files at repo root) matches the actual pins in `packages/clients/python/pyproject.toml` and `packages/clients/typescript/package.json` on every PR and push to main. The `.github/workflows/rust-spec-coherence.yml` job enforces `apps/docs/public/openapi.json == packages/clients/rust/openapi.json` so the crates.io fallback stays byte-for-byte identical.

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

## Release flow

HindClaw's core repo releases on tag push. The full sequence when cutting a new version:

1. **Bump the pin file** — if tracking a released upstream:
   ```bash
   echo "X.Y.Z" > UPSTREAM_HINDSIGHT_VERSION
   rm -f UPSTREAM_HINDSIGHT_COMMIT  # if it was set
   ```
2. **Sync the downstream manifests:**
   ```bash
   bash scripts/sync-upstream-pins.sh
   ```
3. **Regenerate the OpenAPI spec and clients:**
   ```bash
   bash scripts/generate-openapi.sh
   bash scripts/generate-clients.sh
   ```
4. **Regenerate the docs skill (optional but recommended when docs changed):**
   ```bash
   bash scripts/generate-docs-skill.sh
   ```
5. **Run all client test suites + extension regression:**
   ```bash
   cd packages/clients/typescript && npm test && cd ../..
   cd packages/clients/python && .venv/bin/python -m pytest tests/ -v && cd ../..
   cd packages/clients/go && go test ./... && cd ../..
   cd packages/clients/rust && cargo test && cd ../..
   cd hindclaw-extension && .venv/bin/python -m pytest tests/ -v && cd ..
   ```
6. **Bump the version in `packages/extension/pyproject.toml`** and update `CHANGELOG.md`.
7. **Commit everything in one release commit**, push to main.
8. **Tag and push**: `git tag -a ext-v<version> -m "..."` then `git push origin ext-v<version>`. GitHub Actions publishes to PyPI via the `ext-v*` trigger on `.github/workflows/publish-extension.yml`.

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
# Replace with: the steady-state line above, once UPSTREAM_HINDSIGHT_VERSION
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

**packages/clients/rust forced duplication of upstream types:**
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
