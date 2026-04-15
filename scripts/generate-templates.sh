#!/usr/bin/env bash
#
# Generate hindclaw-docs/src/data/templates.json from the hindclaw-templates
# package. Flattens the catalog by inlining each manifest file under the
# `manifest` field so the Templates Hub page can consume a single import.
#
# Run manually when templates change. The output file is committed to git
# the same way generated clients are.
#
# Usage: scripts/generate-templates.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TPL_ROOT="$REPO_ROOT/hindclaw-templates"
CATALOG="$TPL_ROOT/templates.json"
OUT="$REPO_ROOT/hindclaw-docs/src/data/templates.json"

if [ ! -f "$CATALOG" ]; then
  echo -e "\033[31m✗\033[0m Catalog not found: $CATALOG" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo -e "\033[31m✗\033[0m jq is required but not installed" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"

LEN=$(jq '.templates | length' "$CATALOG")
RESULT=$(jq '{catalog_version, name, description, templates: []}' "$CATALOG")

for i in $(seq 0 $((LEN - 1))); do
  ENTRY=$(jq ".templates[$i]" "$CATALOG")
  MANIFEST_FILE=$(echo "$ENTRY" | jq -r '.manifest_file')
  MANIFEST_PATH="$TPL_ROOT/$MANIFEST_FILE"

  if [ ! -f "$MANIFEST_PATH" ]; then
    echo -e "\033[31m✗\033[0m Manifest not found: $MANIFEST_PATH" >&2
    exit 1
  fi

  MANIFEST=$(jq '.' "$MANIFEST_PATH")
  MERGED=$(echo "$ENTRY" | jq --argjson m "$MANIFEST" '. + {manifest: $m} | del(.manifest_file)')
  RESULT=$(echo "$RESULT" | jq --argjson e "$MERGED" '.templates += [$e]')
done

echo "$RESULT" > "$OUT"
COUNT=$(echo "$RESULT" | jq '.templates | length')
NAME=$(echo "$RESULT" | jq -r '.name')
echo -e "\033[32m✓\033[0m Generated $OUT"
echo "  $COUNT templates · source: $NAME"
