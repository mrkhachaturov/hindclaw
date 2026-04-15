# HindClaw TODOs

Deferred upstream-facing follow-ups, tracked for future sessions.

## CI enhancements

### 4. CI availability check for pinned upstream package versions

`version-coherence.yml` only verifies local manifest text matches
`UPSTREAM_HINDSIGHT_VERSION`. A secondary job that actually calls
`npm view @vectorize-io/hindsight-client@<version>`, `pip index versions
hindsight-client`, and (when relevant) `GOPROXY=direct go list -m
github.com/mrkhachaturov/hindsight/hindsight-clients/go@<version>` would
catch the "version bumped but packages not yet published" window.
Nice-to-have, deferred. Only relevant when we track a pre-release commit
(`UPSTREAM_HINDSIGHT_COMMIT` set); redundant during pure release-tracking.
