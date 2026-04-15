# HindClaw TODOs

Deferred upstream-facing follow-ups, tracked for future sessions.

## Upstream proposals

### 1. Regenerate `hindsight-docs/static/bank-template-schema.json` — FILED

Filed as **[vectorize-io/hindsight#1065](https://github.com/vectorize-io/hindsight/pull/1065)**
`fix(docs): regenerate bank-template-schema.json and guard drift`.
Status as of 2026-04-15: OPEN, MERGEABLE, CLEAN — all CI checks passing
(build-api across Python 3.11-3.14, build-typescript-client,
build-hindsight-all-npm, build-control-plane, build-docs,
check-openapi-compatibility, check-cli-coverage,
smoke-openclaw-install, every integration test). Awaiting Nicolò's
review.

Original rationale: the static schema file in upstream Hindsight's
docs had drifted from the live Pydantic model on `entity_labels`
(static said `list[str]`, live said `list[dict[str, Any]]`). The PR
also adds a drift guard so future regressions fail CI.

### 2. Propose `manifest_file` reference to upstream `templates.json` — FILED

Filed as **[vectorize-io/hindsight#1066](https://github.com/vectorize-io/hindsight/pull/1066)**
`feat(docs): split template manifests into per-file manifest_file references`.
Status as of 2026-04-15: OPEN, MERGEABLE, CLEAN — detect-changes +
verify-generated-files + build-docs all passing. Awaiting review.

Original rationale: HindClaw's Plan B added a catalog format where
each entry is either an inline `manifest` or an external `manifest_file`
reference, enforced by a Pydantic `model_validator`. This PR applies
the same pattern to upstream's hub. **Side effect:** resolves the
pre-existing test failure in `tests/test_template_models.py::
test_catalog_accepts_upstream_templates_json_verbatim` flagged during
Plan D Task 9 — when #1066 merges and we rebuild the skills tree
against the new upstream format, the test will start passing again
without local changes.

### 3. Upstream TypeScript re-export PR for BankTemplate types — FILED

Filed as **[vectorize-io/hindsight#1063](https://github.com/vectorize-io/hindsight/pull/1063)**
`fix(ts-sdk): re-export BankTemplate types from package root`.
Status as of 2026-04-15: OPEN, MERGEABLE, CLEAN — detect-changes,
verify-generated-files, build-typescript-client, build-openclaw-integration,
build-control-plane, smoke-openclaw-install all SUCCESS. Awaiting review.

Local mirror patch: `build/hindsight/patches/0003-fix-ts-sdk-export-bank-template-types.patch`
(inside astromech's build tree, applies cleanly on v0.5.1 + 0001 + 0002).
Source branch: `fix/ts-sdk-export-bank-template-types` on
mrkhachaturov/hindsight fork. PR body draft still at
`/tmp/pr-ts-sdk-export-bank-template-types.md` (ephemeral — delete
after merge).

**When #1063 merges and upstream releases a version containing it, delete:**
- `hindclaw-clients/typescript/src/vendor-hindsight-client.d.ts` (ambient shim)
- The TEMPORARY marker block in `hindclaw-clients/typescript/src/index.ts`
- Patch `build/hindsight/patches/0003-fix-ts-sdk-export-bank-template-types.patch`
- The PR draft at `/tmp/pr-ts-sdk-export-bank-template-types.md`

## CI enhancements

### 4. CI availability check for pinned upstream package versions

Plan D's `version-coherence.yml` only verifies local manifest text matches
`UPSTREAM_HINDSIGHT_VERSION`. A secondary job that actually calls
`npm view @vectorize-io/hindsight-client@<version>`, `pip index versions
hindsight-client`, and (when relevant) `GOPROXY=direct go list -m
github.com/mrkhachaturov/hindsight/hindsight-clients/go@<version>` would
catch the "version bumped but packages not yet published" window.
Nice-to-have, deferred.

### 5. Deno runtime verification of the generated TypeScript client

Task 3 of Plan D re-forked `generate-clients.sh` from upstream and
preserves upstream's Deno-compat patch (destructures `client` out of
`RequestInit` because Deno reserves that field name). The patch is
applied at regen time, but Plan D does not exercise it — the TypeScript
test suite runs under Node (Jest), not Deno. Adding a `tests/deno_setup.ts`
smoke test plus a `test:deno` script and wiring a Deno runtime into CI
would close the parity gap with upstream Hindsight's test suite.
Nice-to-have, deferred.

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
