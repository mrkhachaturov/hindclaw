#!/usr/bin/env bash
set -euo pipefail

# Sync HindClaw's upstream hindsight pins to the state declared at the
# repo root. Reads:
#   UPSTREAM_HINDSIGHT_VERSION  — latest released semver (always present)
#   UPSTREAM_HINDSIGHT_COMMIT   — commit SHA override (optional)
#
# Two states:
#   Released    — UPSTREAM_HINDSIGHT_COMMIT missing/empty
#     → Python and TypeScript pinned to the released version (==X.Y.Z)
#   Pre-release — UPSTREAM_HINDSIGHT_COMMIT set
#     → Python pinned to a git-ref at that commit
#     → TypeScript stays at the released version (npm subpath git-refs
#       don't round-trip cleanly; the vendor shim at
#       hindclaw-clients/typescript/src/vendor-hindsight-client.d.ts
#       carries the TEMPORARY marker for the upstream export gap)
#
# Go and Rust are intentionally NOT touched — Go uses fork+replace
# directive in terraform-provider-hindclaw, Rust has no upstream
# client crate (PERMANENT WORKAROUND in hindclaw-clients/rust/build.rs).
#
# Usage: bash scripts/sync-upstream-pins.sh
#   Run after editing UPSTREAM_HINDSIGHT_VERSION or UPSTREAM_HINDSIGHT_COMMIT,
#   then review the diff and commit.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$REPO_ROOT/UPSTREAM_HINDSIGHT_VERSION"
COMMIT_FILE="$REPO_ROOT/UPSTREAM_HINDSIGHT_COMMIT"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: $VERSION_FILE not found" >&2
    exit 1
fi

VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [ -z "$VERSION" ]; then
    echo "Error: $VERSION_FILE is empty" >&2
    exit 1
fi
if [[ "$VERSION" == v* ]]; then
    echo "Error: $VERSION_FILE should contain bare semver (no 'v' prefix), got '$VERSION'" >&2
    exit 1
fi

COMMIT=""
if [ -f "$COMMIT_FILE" ]; then
    COMMIT="$(tr -d '[:space:]' < "$COMMIT_FILE")"
fi

TS_MANIFEST="$REPO_ROOT/hindclaw-clients/typescript/package.json"
PY_MANIFEST="$REPO_ROOT/hindclaw-clients/python/pyproject.toml"

if [ -n "$COMMIT" ]; then
    echo "Mode: PRE-RELEASE (commit $COMMIT tracking on top of v$VERSION)"
else
    echo "Mode: RELEASED (v$VERSION)"
fi

# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------
if [ -f "$PY_MANIFEST" ]; then
    PY_MANIFEST="$PY_MANIFEST" VERSION="$VERSION" COMMIT="$COMMIT" python3 <<'PY'
import os, re, pathlib, sys
p = pathlib.Path(os.environ["PY_MANIFEST"])
text = p.read_text()
commit = os.environ["COMMIT"]
version = os.environ["VERSION"]
if commit:
    new_line = f'    "hindsight-client @ git+https://github.com/vectorize-io/hindsight.git@{commit}#subdirectory=hindsight-clients/python",'
    mode = "git-ref pin"
else:
    new_line = f'    "hindsight-client=={version}",'
    mode = "release pin"
pattern = re.compile(r'    "hindsight-client[^"\n]*(?:"[^\n]*)?",')
new_text, n = pattern.subn(new_line, text, count=1)
if n == 0:
    print(f"WARN: hindsight-client pin line not found in {p}", file=sys.stderr)
else:
    p.write_text(new_text)
    print(f"  rewrote {p} ({mode})")
PY
else
    echo "  WARN: $PY_MANIFEST not found, skipping" >&2
fi

# ---------------------------------------------------------------------------
# TypeScript — always tracks the released version; subpath git-refs are
# awkward in npm so the vendor shim handles the gap.
# ---------------------------------------------------------------------------
if [ -f "$TS_MANIFEST" ]; then
    TS_MANIFEST="$TS_MANIFEST" VERSION="$VERSION" python3 <<'PY'
import os, json, pathlib
p = pathlib.Path(os.environ["TS_MANIFEST"])
data = json.loads(p.read_text())
version = os.environ["VERSION"]
for key in ("dependencies", "devDependencies"):
    deps = data.get(key) or {}
    if "@vectorize-io/hindsight-client" in deps:
        deps["@vectorize-io/hindsight-client"] = version
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"  rewrote {p}")
PY
else
    echo "  WARN: $TS_MANIFEST not found, skipping" >&2
fi

echo ""
if [ -n "$COMMIT" ]; then
    echo "Done. Go and Rust clients are intentionally skipped (forced duplication)."
    echo ""
    echo "NEXT STEPS:"
    echo "  1. Review the diff: git diff hindclaw-clients/"
    echo "  2. Re-run extract-openapi.py + generate-clients.sh to regenerate"
    echo "     clients against the pinned upstream commit."
    echo "  3. Commit with a message referencing the upstream commit."
    echo ""
    echo "When upstream publishes a release containing commit $COMMIT:"
    echo "  1. Delete UPSTREAM_HINDSIGHT_COMMIT"
    echo "  2. Bump UPSTREAM_HINDSIGHT_VERSION to the release tag (bare semver)"
    echo "  3. Re-run this script to stamp release pins"
else
    echo "Done. All manifests on v$VERSION."
fi
