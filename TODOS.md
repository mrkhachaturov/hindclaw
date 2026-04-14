# HindClaw TODOs

Deferred upstream-facing follow-ups, tracked for future sessions.

## Upstream proposals

### 1. Regenerate `hindsight-docs/static/bank-template-schema.json`

The static schema file in upstream Hindsight's docs has drifted from the
live Pydantic model on `entity_labels` (static says `list[str]`, live says
`list[dict[str, Any]]`). Discovered during the Plan D audit. Should be a
small upstream PR or an upstream CI job that regenerates the file on every
release. Tracked separately from PR #1044 to avoid scope expansion.

### 2. Propose `manifest_file` reference to upstream `templates.json`

HindClaw's Plan B added a catalog format where each entry is either an
inline `manifest` or an external `manifest_file` reference, enforced by a
Pydantic `model_validator`. The same pattern would benefit upstream's hub.
File after Plan C Tier 2 lands so HindClaw's `templates.json` can serve
as the worked example.

### 3. Upstream TypeScript re-export PR for BankTemplate types

Filed as a follow-up PR to vectorize-io/hindsight from branch
`fix/ts-sdk-export-bank-template-types` on the mrkhachaturov/hindsight
fork. See local patch at
`build/hindsight/patches/0003-fix-ts-sdk-export-bank-template-types.patch`
(inside astromech's build tree) and the PR body draft at
`/tmp/pr-ts-sdk-export-bank-template-types.md`. When merged and released,
delete:
- `hindclaw-clients/typescript/src/vendor-hindsight-client.d.ts` (ambient shim)
- The TEMPORARY marker in `hindclaw-clients/typescript/src/index.ts`
- Patch `0003-fix-ts-sdk-export-bank-template-types.patch`

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
