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

# Patch rest.py for deferred aiohttp initialization.
# The generated code creates aiohttp.TCPConnector in __init__ which requires
# a running event loop. Same patch as upstream generate-clients.sh.
# Fix: move connector/session creation to a lazy _ensure_session() method.
REST_FILE="$PYTHON_CLIENT_DIR/hindclaw_client_api/rest.py"
if [ -f "$REST_FILE" ] && grep -q 'aiohttp.TCPConnector' "$REST_FILE" && ! grep -q '_ensure_session' "$REST_FILE"; then
    echo "Patching rest.py for deferred aiohttp initialization..."
    python3 -c "
import pathlib, sys

rest = pathlib.Path('$REST_FILE')
content = rest.read_text()

# --- Patch 1: Replace __init__ with deferred init + _ensure_session + properties ---
OLD_INIT = '''    def __init__(self, configuration) -> None:

        # maxsize is number of requests to host that are allowed in parallel
        maxsize = configuration.connection_pool_maxsize

        ssl_context = ssl.create_default_context(
            cafile=configuration.ssl_ca_cert
        )
        if configuration.cert_file:
            ssl_context.load_cert_chain(
                configuration.cert_file, keyfile=configuration.key_file
            )

        if not configuration.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(
            limit=maxsize,
            ssl=ssl_context
        )

        self.proxy = configuration.proxy
        self.proxy_headers = configuration.proxy_headers

        # https pool manager
        self.pool_manager = aiohttp.ClientSession(
            connector=connector,
            trust_env=True
        )

        retries = configuration.retries
        self.retry_client: Optional[aiohttp_retry.RetryClient]
        if retries is not None:
            self.retry_client = aiohttp_retry.RetryClient(
                client_session=self.pool_manager,
                retry_options=aiohttp_retry.ExponentialRetry(
                    attempts=retries,
                    factor=2.0,
                    start_timeout=0.1,
                    max_timeout=120.0
                )
            )
        else:
            self.retry_client = None'''

NEW_INIT = '''    def __init__(self, configuration) -> None:
        # Store configuration for deferred initialization.
        # aiohttp.TCPConnector requires a running event loop, so we defer
        # creation until the first request (which runs in async context).
        self._configuration = configuration
        self._pool_manager: Optional[aiohttp.ClientSession] = None
        self._retry_client: Optional[aiohttp_retry.RetryClient] = None

        self.proxy = configuration.proxy
        self.proxy_headers = configuration.proxy_headers

    def _ensure_session(self) -> None:
        \"\"\"Create aiohttp session lazily (must be called from async context).\"\"\"
        if self._pool_manager is not None:
            return

        configuration = self._configuration
        maxsize = configuration.connection_pool_maxsize

        ssl_context = ssl.create_default_context(
            cafile=configuration.ssl_ca_cert
        )
        if configuration.cert_file:
            ssl_context.load_cert_chain(
                configuration.cert_file, keyfile=configuration.key_file
            )

        if not configuration.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(
            limit=maxsize,
            ssl=ssl_context
        )

        self._pool_manager = aiohttp.ClientSession(
            connector=connector,
            trust_env=True
        )

        retries = configuration.retries
        if retries is not None:
            self._retry_client = aiohttp_retry.RetryClient(
                client_session=self._pool_manager,
                retry_options=aiohttp_retry.ExponentialRetry(
                    attempts=retries,
                    factor=2.0,
                    start_timeout=0.1,
                    max_timeout=120.0
                )
            )

    @property
    def pool_manager(self) -> aiohttp.ClientSession:
        \"\"\"Get the pool manager, initializing if needed.\"\"\"
        self._ensure_session()
        return self._pool_manager

    @property
    def retry_client(self) -> Optional[aiohttp_retry.RetryClient]:
        \"\"\"Get the retry client, initializing if needed.\"\"\"
        self._ensure_session()
        return self._retry_client'''

if OLD_INIT not in content:
    print('WARNING: __init__ pattern not found in rest.py — generator output may have changed')
    sys.exit(0)

content = content.replace(OLD_INIT, NEW_INIT)

# --- Patch 2: Replace close() with null-safe version ---
OLD_CLOSE = '''    async def close(self):
        await self.pool_manager.close()
        if self.retry_client is not None:
            await self.retry_client.close()'''

NEW_CLOSE = '''    async def close(self):
        if self._pool_manager is not None:
            await self._pool_manager.close()
        if self._retry_client is not None:
            await self._retry_client.close()'''

if OLD_CLOSE in content:
    content = content.replace(OLD_CLOSE, NEW_CLOSE)

rest.write_text(content)
print('rest.py patched successfully')
"
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
