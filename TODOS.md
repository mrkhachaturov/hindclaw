# HindClaw TODOs

Deferred upstream-facing follow-ups, tracked for future sessions.

## Upstream proposals

### 1. Regenerate `hindsight-docs/static/bank-template-schema.json` — MERGED

Filed as **[vectorize-io/hindsight#1065](https://github.com/vectorize-io/hindsight/pull/1065)**
`fix(docs): regenerate bank-template-schema.json and guard drift`.
**Merged 2026-04-15** at commit `16ed93b9a2709787132706128c84377f9033bfc6`.
No further action — awaits next upstream release to flow into pinned versions.

Original rationale: the static schema file in upstream Hindsight's
docs had drifted from the live Pydantic model on `entity_labels`
(static said `list[str]`, live said `list[dict[str, Any]]`). The PR
also adds a drift guard so future regressions fail CI.

### 2. Propose `manifest_file` reference to upstream `templates.json` — MERGED

Filed as **[vectorize-io/hindsight#1066](https://github.com/vectorize-io/hindsight/pull/1066)**
`feat(docs): split template manifests into per-file manifest_file references`.
**Merged 2026-04-15** at commit `6a1d5fcd30b1b24782940ac58339d6474c7aeb8d`.

Follow-up: when we rebuild the skills tree against the new upstream
format, the pre-existing test failure in
`tests/test_template_models.py::test_catalog_accepts_upstream_templates_json_verbatim`
(flagged during Plan D Task 9) should start passing again without
local changes. Verify on next upstream sync.

Original rationale: HindClaw's Plan B added a catalog format where
each entry is either an inline `manifest` or an external `manifest_file`
reference, enforced by a Pydantic `model_validator`. This PR applies
the same pattern to upstream's hub.

### 3. Upstream TypeScript re-export PR for BankTemplate types — MERGED

Filed as **[vectorize-io/hindsight#1063](https://github.com/vectorize-io/hindsight/pull/1063)**
`fix(ts-sdk): re-export BankTemplate types from package root`.
**Merged 2026-04-15** at commit `581bbf3fc6a8d801381758cd6f23c376b7d75c24`.

Local mirror patch: `build/hindsight/patches/0003-fix-ts-sdk-export-bank-template-types.patch`
(inside astromech's build tree, applies cleanly on v0.5.1 + 0001 + 0002).
Source branch: `fix/ts-sdk-export-bank-template-types` on
mrkhachaturov/hindsight fork.

**Cleanup pending — when upstream releases a version containing the merge commit, delete:**
- `hindclaw-clients/typescript/src/vendor-hindsight-client.d.ts` (ambient shim)
- The TEMPORARY marker block in `hindclaw-clients/typescript/src/index.ts`
- Patch `build/hindsight/patches/0003-fix-ts-sdk-export-bank-template-types.patch`
- The PR draft at `/tmp/pr-ts-sdk-export-bank-template-types.md`

Note: PR **#1068** (`refactor(templates): split into hindsight-bank-templates package (v2)`)
was closed without merging on 2026-04-15 — no cleanup needed, recorded here
so future sessions don't rediscover it.

## CI enhancements

### 4. CI availability check for pinned upstream package versions

Plan D's `version-coherence.yml` only verifies local manifest text matches
`UPSTREAM_HINDSIGHT_VERSION`. A secondary job that actually calls
`npm view @vectorize-io/hindsight-client@<version>`, `pip index versions
hindsight-client`, and (when relevant) `GOPROXY=direct go list -m
github.com/mrkhachaturov/hindsight/hindsight-clients/go@<version>` would
catch the "version bumped but packages not yet published" window.
Nice-to-have, deferred.

### 5. Deno runtime verification of the generated TypeScript client — DONE

Closed as of 2026-04-15. `hindclaw-clients/typescript/tests/deno_setup.ts`
mirrors upstream Hindsight's preload shim (injects `describe`/`test`/
`expect` from `jsr:@std/testing/bdd` + `jsr:@std/expect` so Jest-style
tests run unchanged under `deno test`). `package.json` adds a
`test:deno` script matching upstream's flags:

```
deno test --no-check --allow-env --allow-net \
  --unstable-sloppy-imports --preload=tests/deno_setup.ts tests/smoke.test.ts
```

`tests/smoke.test.ts` was updated to use `node:http` / `node:net`
specifiers (Node 20+ and Deno 2 both resolve these explicitly). The new
`test-typescript-client-deno` job in `.github/workflows/ci.yml` runs it
in CI alongside the Node/Jest `test-typescript-client` job.

## Release unblocking

### 6. When upstream publishes hindsight-client 0.5.2+ containing PR #1044

Current state is pre-release: `UPSTREAM_HINDSIGHT_COMMIT` at the repo root
holds `099f4c925a920009c90692760b0ec1007cf0d977` (the #1044 merge commit)
and `scripts/sync-upstream-pins.sh` produces a git-ref pin in
`hindclaw-clients/python/pyproject.toml`. When upstream cuts the next
release containing that commit:

```bash
rm UPSTREAM_HINDSIGHT_COMMIT
echo "0.5.2" > UPSTREAM_HINDSIGHT_VERSION   # or whatever the release tag is
bash scripts/sync-upstream-pins.sh
bash scripts/generate-clients.sh
# verify all four client suites pass, commit, push
```

The `TEMPORARY:` marker in `hindclaw-clients/python/pyproject.toml` and
the hatch `allow-direct-references` escape hatch disappear automatically
once the git-ref pin is replaced with a release pin.
