#!/bin/bash
set -e

# Extract OpenAPI specification from HindclawHttp without a running server.
# Runs extract-openapi.py via the hindclaw-extension venv and optionally
# rebuilds the docs site.

cd "$(dirname "$0")/.."
ROOT_DIR=$(pwd)

BUILD_DOCS=false
for arg in "$@"; do
    case "$arg" in
        --build-docs) BUILD_DOCS=true ;;
    esac
done

echo "Extracting OpenAPI specification..."
hindclaw-extension/.venv/bin/python scripts/extract-openapi.py

SPEC_PATH="$ROOT_DIR/hindclaw-docs/static/openapi.json"
if [ -f "$SPEC_PATH" ]; then
    SIZE=$(du -h "$SPEC_PATH" | cut -f1)
    echo "  wrote $SPEC_PATH ($SIZE)"
fi

if [ "$BUILD_DOCS" = "true" ]; then
    echo ""
    echo "Building hindclaw-docs..."
    cd "$ROOT_DIR/hindclaw-docs"
    npm run build
fi

echo ""
echo "Done."
