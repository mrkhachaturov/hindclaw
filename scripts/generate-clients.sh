#!/usr/bin/env bash
set -e

# Generate Go, Python, and TypeScript clients from OpenAPI spec.
# Same pipeline as upstream Hindsight (build/hindsight/.upstream/scripts/generate-clients.sh).
#
# Prerequisites:
#   - Docker (for OpenAPI Generator)
#   - Go 1.18+ (for go mod tidy && go build)
#   - Node.js + npm (for TypeScript @hey-api/openapi-ts)
#   - openapi.json already extracted (run extract-openapi.py first)
#
# Usage:
#   cd build/hindclaw
#   python scripts/extract-openapi.py > hindclaw-clients/openapi.json
#   bash scripts/generate-clients.sh

# Pin OpenAPI Generator version for reproducible builds (matches upstream)
OPENAPI_GENERATOR_VERSION="v7.10.0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENTS_DIR="$PROJECT_ROOT/hindclaw-clients"
OPENAPI_SPEC="$CLIENTS_DIR/openapi.json"
CONFIG_DIR="$CLIENTS_DIR/openapi-generator-config"

echo "=================================================="
echo "Hindclaw API Client Generator"
echo "=================================================="
echo "Project root: $PROJECT_ROOT"
echo "Clients directory: $CLIENTS_DIR"
echo "OpenAPI spec: $OPENAPI_SPEC"
echo ""

# Check prerequisites
if [ ! -f "$OPENAPI_SPEC" ]; then
    echo "Error: OpenAPI spec not found at $OPENAPI_SPEC"
    echo "Run: python scripts/extract-openapi.py > hindclaw-clients/openapi.json"
    exit 1
fi
echo "OpenAPI spec found"

if ! command -v docker &> /dev/null; then
    echo "Error: Docker not found. Required for OpenAPI Generator."
    exit 1
fi
echo "Docker available"
echo "Using openapi-generator ${OPENAPI_GENERATOR_VERSION}"
echo ""

# ==========================================
# Go client
# ==========================================
echo "=================================================="
echo "Generating Go client..."
echo "=================================================="

GO_CLIENT_DIR="$CLIENTS_DIR/go"

if ! command -v go &> /dev/null; then
    echo "Go not found, skipping Go client generation"
else
    # Save maintained files
    TEMP_DIR=$(mktemp -d)
    echo "Preserving maintained files..."
    [ -f "$GO_CLIENT_DIR/hindclaw_client.go" ] && cp "$GO_CLIENT_DIR/hindclaw_client.go" "$TEMP_DIR/"
    [ -f "$GO_CLIENT_DIR/README.md" ] && cp "$GO_CLIENT_DIR/README.md" "$TEMP_DIR/"

    # Remove old generated files
    echo "Removing old generated code..."
    rm -f "$GO_CLIENT_DIR"/api_*.go "$GO_CLIENT_DIR"/model_*.go
    rm -f "$GO_CLIENT_DIR"/client.go "$GO_CLIENT_DIR"/configuration.go "$GO_CLIENT_DIR"/response.go "$GO_CLIENT_DIR"/utils.go
    rm -rf "$GO_CLIENT_DIR"/docs/ "$GO_CLIENT_DIR"/.openapi-generator/
    rm -f "$GO_CLIENT_DIR"/go.mod "$GO_CLIENT_DIR"/go.sum

    # Generate via Docker (--platform linux/amd64 for reproducible output)
    echo "Generating client from OpenAPI spec..."
    docker run --rm \
        --platform linux/amd64 \
        --user "$(id -u):$(id -g)" \
        -v "$OPENAPI_SPEC:/local/openapi.json" \
        -v "$GO_CLIENT_DIR:/local/out" \
        -v "$CONFIG_DIR/go.yaml:/local/config.yaml" \
        "openapitools/openapi-generator-cli:${OPENAPI_GENERATOR_VERSION}" generate \
        -i /local/openapi.json \
        -g go \
        -o /local/out \
        -c /local/config.yaml \
        --global-property apiDocs=false,apiTests=false,modelDocs=false,modelTests=false

    # Remove boilerplate
    echo "Removing boilerplate files..."
    rm -rf "$GO_CLIENT_DIR"/docs/ "$GO_CLIENT_DIR"/git_push.sh
    rm -rf "$GO_CLIENT_DIR"/.travis.yml "$GO_CLIENT_DIR"/.gitlab-ci.yml
    rm -rf "$GO_CLIENT_DIR"/.openapi-generator-ignore "$GO_CLIENT_DIR"/.openapi-generator/

    # Restore maintained files
    echo "Restoring maintained files..."
    [ -f "$TEMP_DIR/hindclaw_client.go" ] && mv "$TEMP_DIR/hindclaw_client.go" "$GO_CLIENT_DIR/"
    [ -f "$TEMP_DIR/README.md" ] && mv "$TEMP_DIR/README.md" "$GO_CLIENT_DIR/"
    rm -rf "$TEMP_DIR"

    # Build
    echo "Building Go client..."
    cd "$GO_CLIENT_DIR"
    go mod tidy
    go build ./...

    echo "Go client generated at $GO_CLIENT_DIR"
fi
echo ""

# ==========================================
# Python client
# ==========================================
echo "=================================================="
echo "Generating Python client..."
echo "=================================================="

PYTHON_CLIENT_DIR="$CLIENTS_DIR/python"

# Save maintained files
TEMP_DIR=$(mktemp -d)
echo "Preserving maintained files..."
[ -f "$PYTHON_CLIENT_DIR/hindclaw_client.py" ] && cp "$PYTHON_CLIENT_DIR/hindclaw_client.py" "$TEMP_DIR/"
[ -f "$PYTHON_CLIENT_DIR/pyproject.toml" ] && cp "$PYTHON_CLIENT_DIR/pyproject.toml" "$TEMP_DIR/"
[ -f "$PYTHON_CLIENT_DIR/README.md" ] && cp "$PYTHON_CLIENT_DIR/README.md" "$TEMP_DIR/"

# Remove old generated code
if [ -d "$PYTHON_CLIENT_DIR/hindclaw_client_api" ]; then
    echo "Removing old generated code..."
    rm -rf "$PYTHON_CLIENT_DIR/hindclaw_client_api"
fi

# Remove generator boilerplate
for file in setup.py setup.cfg requirements.txt test-requirements.txt tox.ini git_push.sh .travis.yml .gitlab-ci.yml .gitignore README.md; do
    rm -f "$PYTHON_CLIENT_DIR/$file"
done

# Generate via Docker
echo "Generating client from OpenAPI spec..."
docker run --rm \
    --platform linux/amd64 \
    --user "$(id -u):$(id -g)" \
    -v "$OPENAPI_SPEC:/local/openapi.json" \
    -v "$PYTHON_CLIENT_DIR:/local/out" \
    -v "$CONFIG_DIR/python.yaml:/local/config.yaml" \
    "openapitools/openapi-generator-cli:${OPENAPI_GENERATOR_VERSION}" generate \
    -i /local/openapi.json \
    -g python \
    -o /local/out \
    -c /local/config.yaml

# Restore maintained files
echo "Restoring maintained files..."
[ -f "$TEMP_DIR/hindclaw_client.py" ] && mv "$TEMP_DIR/hindclaw_client.py" "$PYTHON_CLIENT_DIR/"
[ -f "$TEMP_DIR/pyproject.toml" ] && mv "$TEMP_DIR/pyproject.toml" "$PYTHON_CLIENT_DIR/"
[ -f "$TEMP_DIR/README.md" ] && mv "$TEMP_DIR/README.md" "$PYTHON_CLIENT_DIR/"
rm -rf "$TEMP_DIR"

# Patch rest.py for deferred aiohttp initialization if needed
# The generated code creates aiohttp.TCPConnector in __init__ which requires
# a running event loop. See upstream generate-clients.sh lines 153-306.
REST_FILE="$PYTHON_CLIENT_DIR/hindclaw_client_api/rest.py"
if [ -f "$REST_FILE" ] && grep -q 'aiohttp.TCPConnector' "$REST_FILE"; then
    echo "Checking if rest.py needs aiohttp deferred init patch..."
    if grep -q 'def __init__.*configuration' "$REST_FILE" && ! grep -q '_ensure_session' "$REST_FILE"; then
        echo "ERROR: rest.py needs aiohttp deferred init patch but auto-patching is not implemented."
        echo "Apply the upstream pattern manually: build/hindsight/.upstream/scripts/generate-clients.sh lines 153-306"
        echo "The fix: move aiohttp.TCPConnector creation from __init__ to a lazy _ensure_session() method."
        exit 1
    fi
fi

echo "Python client generated at $PYTHON_CLIENT_DIR"
echo ""

# ==========================================
# TypeScript client
# ==========================================
echo "=================================================="
echo "Generating TypeScript client..."
echo "=================================================="

TYPESCRIPT_CLIENT_DIR="$CLIENTS_DIR/typescript"

# Remove old generated client
echo "Removing old TypeScript generated code..."
rm -rf "$TYPESCRIPT_CLIENT_DIR/generated"

# Generate using @hey-api/openapi-ts (pinned in package.json)
echo "Generating from $OPENAPI_SPEC..."
cd "$TYPESCRIPT_CLIENT_DIR"
npm install
npm run generate

echo "TypeScript client generated at $TYPESCRIPT_CLIENT_DIR"
echo ""

# ==========================================
# Done
# ==========================================
echo "=================================================="
echo "Client generation complete!"
echo "=================================================="
echo ""
echo "Go client:         $GO_CLIENT_DIR"
echo "Python client:     $PYTHON_CLIENT_DIR"
echo "TypeScript client: $TYPESCRIPT_CLIENT_DIR"
echo ""
echo "Next steps:"
echo "  1. Review the generated clients"
echo "  2. Test the clients"
echo "  3. Commit the generated code"
