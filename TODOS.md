# HindClaw TODOs

Deferred follow-ups, tracked for future sessions. Items are numbered in
the order they were first filed; gaps are expected (closed items get
removed when they ship).

## Repo structure

### R1. Move `UPSTREAM_HINDSIGHT_VERSION` off the repo root

Having `UPSTREAM_HINDSIGHT_VERSION` (and historically
`UPSTREAM_HINDSIGHT_COMMIT`) visible at the repo root clutters the
top-level listing for casual readers with internal dependency-tracking
state. Move to one of:

- **(a)** `.upstream-pin/VERSION` (+ `COMMIT` when needed) — dot-prefixed
  dir, invisible to casual `ls` but still plain text files the existing
  `scripts/sync-upstream-pins.sh` can read with a one-line path change
- **(b)** `.upstream-pin.toml` single TOML file at the root with
  `version = "0.5.2"` plus optional `commit = "..."` — slightly richer
  format, `sync-upstream-pins.sh` parses TOML
- **(c)** Fold into `pyproject.toml` at repo root (there isn't one today
  — would need to add a minimal one just for this field, which is more
  invasive)

Preference: (a) for the quick win since it's a straight rename and
one-line script update. (b) is the nicer long-term shape.

Touches: `UPSTREAM_HINDSIGHT_VERSION` → new location,
`scripts/sync-upstream-pins.sh` path read, and
`.github/workflows/version-coherence.yml` which grep-verifies these
files from the repo root.

### R2. Local dev scaffold: `.local/` + `justfile.local`

Add the machine-local dev flow so a contributor (or the maintainer from
a MacBook) can work on HindClaw without leaning on astromech's
`build/hindsight/.upstream/` path. Pattern:

- `.local/` — gitignored directory for personal state (clone of
  upstream fork, scratch data, whatever)
- `justfile` — committed top-level recipes, imports `justfile.local`
  optionally via `import? 'justfile.local'`
- `justfile.local` — gitignored, user-private recipes like
  `dev-install-extension`, `setup-local-upstream`, etc.
- `.gitignore` adds `/.local/` and `/justfile.local`
- `docs/developer/local-setup.md` + a committed
  `docs/developer/justfile.local.example` template so new contributors
  know the pattern exists without having the live file

No committed code, test, or CI ever references `.local/` — it's a
parallel universe for personal dev convenience only. CI stays pinned
to released upstream from PyPI/npm.

## CLI UX

### C1. CLI brainstorm session

Have a proper design conversation about `hindclaw-cli` before layering
more fixes on top. Questions queued:

- Keep `--scope server|personal` as a routing hint (current shape after
  the post-0.5.2 refactor), or lift the admin/my split into subcommand
  groups (`hindclaw admin template …` vs `hindclaw template …`, similar
  to `kubectl` or `gh` patterns)? Trade-off: flag preserves backward
  compatibility, subcommands match the REST layout 1:1 but break any
  muscle memory and shell scripts that invoke `hindclaw template create`
- What replaces `template search` now that `marketplace_search` is gone
  from the API? Options: (a) client-side fan-out across
  `list_template_sources` + `list_*_templates` with local filtering,
  (b) new server-side search endpoint, (c) drop the concept entirely
  and lean on catalog-level discovery from the templates repo
- Should there be a dedicated `hindclaw template source …` command
  family to match the split endpoints (`/me/template-sources` vs
  `/admin/template-sources`)? Currently the CLI has only `source` at
  the top level, which maps to the admin-only endpoints
- Beyond templates: are there other command families that silently
  assume a single-endpoint pre-split API? (users, groups, policies,
  service-accounts — worth a grep)

## Content / design

### D1. Template-repo search replacement

Upstream's Plan B convergence removed `marketplace_search` without a
direct replacement. The templates repo (`hindclaw-templates-official`)
is now a flat catalog validated by Ajv against upstream's schema, but
there's no search story — if the number of templates grows, contributors
will want tag/category filtering, and users will want "show me what's
available" beyond a flat `list`. Not urgent while the catalog is small
(3 templates today), but worth designing before we hit ~20.

## CI enhancements

### CI1. CI availability probe for pinned upstream package versions

`version-coherence.yml` only verifies local manifest text matches
`UPSTREAM_HINDSIGHT_VERSION`. A secondary job that actually calls
`npm view @vectorize-io/hindsight-client@<version>`, `pip index versions
hindsight-client`, and (when relevant) `GOPROXY=direct go list -m
github.com/mrkhachaturov/hindsight/hindsight-clients/go@<version>` would
catch the "version bumped but packages not yet published" window. Only
relevant during pre-release tracking (`UPSTREAM_HINDSIGHT_COMMIT` set
alongside a version file); redundant during pure release-tracking like
the current 0.5.2 state. Nice-to-have, deferred.
