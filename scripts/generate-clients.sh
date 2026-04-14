#!/usr/bin/env bash
set -e

# Script to generate Python, TypeScript, and Go clients from OpenAPI spec
# Note: Rust client is auto-generated at build time via build.rs (uses progenitor)
# Usage: ./scripts/generate-clients.sh
#
# Re-forked from upstream Hindsight scripts/generate-clients.sh
# (https://raw.githubusercontent.com/vectorize-io/hindsight/main/scripts/generate-clients.sh).
# HindClaw-specific substitutions:
#   - Spec source: hindclaw-docs/static/openapi.json
#   - Go package: --package-name hindclaw via co-located openapi-generator-config.yaml
#     (HindClaw keeps enumClassPrefix / structPrefix / generateInterfaces set)
#   - Python package: hindclaw_client_api (co-located openapi-generator-config.yaml)
#   - Go git-user-id: mrkhachaturov, git-repo-id: hindclaw/hindclaw-clients/go
#   - TypeScript: generated via @hey-api/openapi-ts, configured via
#     hindclaw-clients/typescript/openapi-ts.config.ts (no inline CLI args)
#   - Python wrapper: hindclaw-clients/python/hindclaw_client.py is a sibling
#     file (HindClaw's Python package is flat, not the hindsight_client/ subpackage
#     upstream uses)
#   - Final step: spec is copied to hindclaw-clients/rust/openapi.json so the
#     crates.io publish tarball retains a byte-for-byte fallback the Rust build.rs
#     can consume when the top-level hindclaw-docs/static/openapi.json is absent.

# Pin openapi-generator version for reproducible builds across local and CI
OPENAPI_GENERATOR_VERSION="v7.10.0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENTS_DIR="$PROJECT_ROOT/hindclaw-clients"
OPENAPI_SPEC="$PROJECT_ROOT/hindclaw-docs/static/openapi.json"

echo "=================================================="
echo "Hindclaw API Client Generator"
echo "=================================================="
echo "Project root: $PROJECT_ROOT"
echo "Clients directory: $CLIENTS_DIR"
echo "OpenAPI spec: $OPENAPI_SPEC"
echo ""
echo "This script generates clients for:"
echo "  - Rust (via progenitor in build.rs)"
echo "  - Python (via openapi-generator)"
echo "  - TypeScript (via @hey-api/openapi-ts)"
echo "  - Go (via openapi-generator)"
echo ""

# Check if OpenAPI spec exists
if [ ! -f "$OPENAPI_SPEC" ]; then
    echo "Error: OpenAPI spec not found at $OPENAPI_SPEC"
    echo "Run: python scripts/extract-openapi.py > hindclaw-docs/static/openapi.json"
    exit 1
fi
echo "OpenAPI spec found"
echo ""

# Check for Docker (we'll use Docker to run openapi-generator)
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not found. Please install Docker"
    echo "  https://docs.docker.com/get-docker/"
    exit 1
fi
echo "Docker available"
echo "Using openapi-generator ${OPENAPI_GENERATOR_VERSION}"
echo ""

# Generate Rust client
echo "=================================================="
echo "Generating Rust client..."
echo "=================================================="

RUST_CLIENT_DIR="$CLIENTS_DIR/rust"

if ! command -v cargo &> /dev/null; then
    echo "Cargo not found, skipping Rust client regeneration"
else
    # Clean old generated files (keep Cargo.lock for reproducible builds)
    echo "Cleaning old Rust generated code..."
    rm -rf "$RUST_CLIENT_DIR/target"

    # Trigger regeneration by building
    # Use --locked to ensure reproducible builds from committed Cargo.lock
    echo "Regenerating Rust client (via build.rs)..."
    cd "$RUST_CLIENT_DIR"
    cargo clean
    cargo build --release --locked

    echo "Rust client generated at $RUST_CLIENT_DIR"
fi
echo ""

# Generate Python client
echo "=================================================="
echo "Generating Python client..."
echo "=================================================="

PYTHON_CLIENT_DIR="$CLIENTS_DIR/python"

# Backup maintained files
# HindClaw's Python client uses a flat layout: hindclaw_client.py is a
# sibling file next to the generated hindclaw_client_api/ package, not a
# subpackage the way upstream Hindsight structures its wrapper.
TEMP_DIR=$(mktemp -d)
echo "Preserving maintained files..."
[ -f "$PYTHON_CLIENT_DIR/hindclaw_client.py" ] && cp "$PYTHON_CLIENT_DIR/hindclaw_client.py" "$TEMP_DIR/"
[ -f "$PYTHON_CLIENT_DIR/pyproject.toml" ] && cp "$PYTHON_CLIENT_DIR/pyproject.toml" "$TEMP_DIR/"
[ -f "$PYTHON_CLIENT_DIR/README.md" ] && cp "$PYTHON_CLIENT_DIR/README.md" "$TEMP_DIR/"

# Remove old generated code (but keep config and maintained files)
if [ -d "$PYTHON_CLIENT_DIR/hindclaw_client_api" ]; then
    echo "Removing old generated code..."
    rm -rf "$PYTHON_CLIENT_DIR/hindclaw_client_api"
fi

# Remove other generated files but keep pyproject.toml and config
for file in setup.py setup.cfg requirements.txt test-requirements.txt tox.ini git_push.sh .travis.yml .gitlab-ci.yml .gitignore README.md; do
    if [ -f "$PYTHON_CLIENT_DIR/$file" ]; then
        rm "$PYTHON_CLIENT_DIR/$file"
    fi
done

echo "Generating new client with openapi-generator..."
cd "$PYTHON_CLIENT_DIR"

# Run openapi-generator via Docker (pinned version for reproducibility)
# Use --platform linux/amd64 to ensure identical output on both macOS (arm64) and Linux CI (amd64)
# Use --user to match current user's UID/GID so generated files are writable
# Note: the generator may exit non-zero due to a known bug writing
# README_onlypackage.mustache, but all API/model files are generated
# before that step, so we allow the failure and verify files below.
docker run --rm \
    --platform linux/amd64 \
    --user "$(id -u):$(id -g)" \
    -v "$OPENAPI_SPEC:/local/openapi.json" \
    -v "$PYTHON_CLIENT_DIR:/local/out" \
    -v "$PYTHON_CLIENT_DIR/openapi-generator-config.yaml:/local/config.yaml" \
    "openapitools/openapi-generator-cli:${OPENAPI_GENERATOR_VERSION}" generate \
    -i /local/openapi.json \
    -g python \
    -o /local/out \
    -c /local/config.yaml || true

# Verify critical generated files exist
if [ ! -f "$PYTHON_CLIENT_DIR/hindclaw_client_api/api_client.py" ]; then
    echo "Error: Python client generation failed - api_client.py not found"
    exit 1
fi

echo "Organizing generated files..."

# Restore maintained files
if [ -f "$TEMP_DIR/hindclaw_client.py" ]; then
    echo "Restoring maintained wrapper: hindclaw_client.py"
    mv "$TEMP_DIR/hindclaw_client.py" "$PYTHON_CLIENT_DIR/"
fi
if [ -f "$TEMP_DIR/pyproject.toml" ]; then
    echo "Restoring maintained pyproject.toml"
    mv "$TEMP_DIR/pyproject.toml" "$PYTHON_CLIENT_DIR/"
fi
if [ -f "$TEMP_DIR/README.md" ]; then
    echo "Restoring maintained README.md"
    mv "$TEMP_DIR/README.md" "$PYTHON_CLIENT_DIR/"
fi
rm -rf "$TEMP_DIR"

# Create PEP 561 py.typed marker for type checker support.
# HindClaw's Python layout is flat (no hindclaw_client/ subpackage), so the
# marker only lives inside the generated hindclaw_client_api/ package.
echo "Creating PEP 561 py.typed marker file..."
touch "$PYTHON_CLIENT_DIR/hindclaw_client_api/py.typed"

# Remove the auto-generated README (we have our own)
if [ -f "$PYTHON_CLIENT_DIR/hindclaw_client_api_README.md" ]; then
    echo "Removing auto-generated README..."
    rm "$PYTHON_CLIENT_DIR/hindclaw_client_api_README.md"
fi

# Patch rest.py to defer aiohttp initialization (fixes "no running event loop" error)
# The generated code creates aiohttp.TCPConnector in __init__ which requires a running event loop.
# We patch it to defer initialization until the first request (which runs in async context).
# -------------------------------------------------------------------------
# HINDCLAW-PRESERVED BLOCK: this rest.py aiohttp patch is load-bearing for the
# hindclaw-extension tests and OpenClaw plugin runtime — it is the same patch
# upstream Hindsight applies. Keep it in lockstep with upstream's version.
# -------------------------------------------------------------------------
echo "Patching rest.py for deferred aiohttp initialization..."
REST_FILE="$PYTHON_CLIENT_DIR/hindclaw_client_api/rest.py"
if [ -f "$REST_FILE" ]; then
    cd "$PROJECT_ROOT"
    python3 << PATCH_SCRIPT
import re

rest_file = "$PYTHON_CLIENT_DIR/hindclaw_client_api/rest.py"

with open(rest_file, 'r') as f:
    content = f.read()

# Replace the __init__ method to defer initialization
old_init = '''class RESTClientObject:

    def __init__(self, configuration) -> None:

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

new_init = '''class RESTClientObject:

    def __init__(self, configuration) -> None:
        # Store configuration for deferred initialization
        # aiohttp.TCPConnector requires a running event loop, so we defer
        # creation until the first request (which runs in async context)
        self._configuration = configuration
        self._pool_manager: Optional[aiohttp.ClientSession] = None
        self._retry_client: Optional[aiohttp_retry.RetryClient] = None

        self.proxy = configuration.proxy
        self.proxy_headers = configuration.proxy_headers

    def _ensure_session(self) -> None:
        """Create aiohttp session lazily (must be called from async context)."""
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
        """Get the pool manager, initializing if needed."""
        self._ensure_session()
        return self._pool_manager

    @property
    def retry_client(self) -> Optional[aiohttp_retry.RetryClient]:
        """Get the retry client, initializing if needed."""
        self._ensure_session()
        return self._retry_client'''

if old_init in content:
    content = content.replace(old_init, new_init)

    # Also update the close method to handle None pool_manager
    old_close = '''    async def close(self):
        await self.pool_manager.close()
        if self.retry_client is not None:
            await self.retry_client.close()'''

    new_close = '''    async def close(self):
        if self._pool_manager is not None:
            await self._pool_manager.close()
        if self._retry_client is not None:
            await self._retry_client.close()'''

    content = content.replace(old_close, new_close)

    with open(rest_file, 'w') as f:
        f.write(content)
    print("  rest.py patched successfully")
else:
    print("  WARNING: Could not find expected pattern in rest.py - skipping patch")
PATCH_SCRIPT
fi

echo "Python client generated at $PYTHON_CLIENT_DIR"
echo ""

# Generate TypeScript client
echo "=================================================="
echo "Generating TypeScript client..."
echo "=================================================="

TYPESCRIPT_CLIENT_DIR="$CLIENTS_DIR/typescript"

# Remove old generated client (keep package.json, tsconfig.json, tests, src/, and config)
echo "Removing old TypeScript generated code..."
rm -rf "$TYPESCRIPT_CLIENT_DIR/generated"

# Also remove legacy structure from old generator if it exists
rm -rf "$TYPESCRIPT_CLIENT_DIR/core"
rm -rf "$TYPESCRIPT_CLIENT_DIR/models"
rm -rf "$TYPESCRIPT_CLIENT_DIR/services"
rm -f "$TYPESCRIPT_CLIENT_DIR/index.ts"

# Generate new client using @hey-api/openapi-ts
# The openapi-ts config lives at hindclaw-clients/typescript/openapi-ts.config.ts
# and is discovered automatically when we run `npm run generate` from that dir
# (the package.json script invokes @hey-api/openapi-ts with no CLI args so the
# config file drives input/output/plugins).
echo "Generating from $OPENAPI_SPEC..."
cd "$TYPESCRIPT_CLIENT_DIR"
npm install
npm run generate

# Patch client.gen.ts for Deno compatibility.
# Deno's Request constructor rejects a 'client' field in RequestInit because
# 'client' is a reserved Deno.HttpClient option name, causing a TypeError.
# We destructure it out before spreading opts into RequestInit.
# -------------------------------------------------------------------------
# HINDCLAW-PRESERVED BLOCK: mirrors upstream Hindsight's Deno-compat patch.
# Keep in lockstep with upstream's version.
# -------------------------------------------------------------------------
echo "Patching client.gen.ts for Deno compatibility..."
cd "$PROJECT_ROOT"
export TYPESCRIPT_CLIENT_DIR
python3 << 'PATCH_SCRIPT'
import os
import re

CLIENT_GEN = os.environ["TYPESCRIPT_CLIENT_DIR"] + "/generated/client/client.gen.ts"
with open(CLIENT_GEN) as f:
    content = f.read()

# Match either single- or double-quoted "follow" (prettier quote style varies
# between upstream Hindsight and HindClaw).
pattern = re.compile(
    r'(    const requestInit: ReqInit = \{\n'
    r'      redirect: ["\']follow["\'],\n)'
    r'(      \.\.\.opts,\n'
    r'      body: getValidRequestBody\(opts\),\n'
    r'    \};)'
)
replacement = (
    r"    // Exclude hey-api internal fields that conflict with Deno's RequestInit.client\n"
    r"    const { client: _client, ...optsForRequest } = opts as typeof opts & { client?: unknown };\n"
    r"\1"
    r"      ...optsForRequest,\n"
    r"      body: getValidRequestBody(opts),\n"
    r"    };"
)

# Skip if already patched (idempotent).
if "optsForRequest" in content:
    print("  client.gen.ts already patched (optsForRequest present) - skipping")
elif pattern.search(content):
    content = pattern.sub(replacement, content)
    with open(CLIENT_GEN, "w") as f:
        f.write(content)
    print("  client.gen.ts patched successfully")
else:
    print("  WARNING: Could not find expected pattern in client.gen.ts - skipping patch")
PATCH_SCRIPT

echo "TypeScript client generated at $TYPESCRIPT_CLIENT_DIR"
echo ""

# Generate Go client
echo "=================================================="
echo "Generating Go client..."
echo "=================================================="

GO_CLIENT_DIR="$CLIENTS_DIR/go"

if ! command -v go &> /dev/null; then
    echo "WARNING: Go not found, skipping Go client generation"
    echo "  Install Go 1.25+ from https://go.dev/dl/"
else
    echo "Regenerating Go client (via OpenAPI Generator Docker)..."
    echo "  Using co-located config: $GO_CLIENT_DIR/openapi-generator-config.yaml"
    echo "  Reading spec from:       $OPENAPI_SPEC"
    cd "$GO_CLIENT_DIR"

    # Save maintained files to temp.
    # HindClaw's Go client has one maintained wrapper (hindclaw_client.go)
    # and a README.md. Unlike upstream Hindsight, HindClaw does not keep
    # *_test.go files in this directory.
    TEMP_DIR=$(mktemp -d)
    echo "Preserving maintained files..."
    [ -f "README.md" ] && cp README.md "$TEMP_DIR/"
    [ -f "hindclaw_client.go" ] && cp hindclaw_client.go "$TEMP_DIR/"

    # Remove old generated files
    echo "Removing old generated code..."
    rm -f api_*.go model_*.go client.go configuration.go response.go utils.go
    rm -rf docs/ .openapi-generator/
    rm -f go.mod go.sum

    # Generate new client via Docker (--platform linux/amd64 ensures identical output on macOS and Linux CI)
    # HindClaw uses a co-located openapi-generator-config.yaml with packageName,
    # gitUserId, gitRepoId, enumClassPrefix, structPrefix, and generateInterfaces
    # set — the config file supersedes inline --package-name / --git-user-id args.
    echo "Generating client from OpenAPI spec..."
    docker run --rm \
        --platform linux/amd64 \
        --user "$(id -u):$(id -g)" \
        -v "$OPENAPI_SPEC:/local/openapi.json" \
        -v "$GO_CLIENT_DIR:/local/out" \
        -v "$GO_CLIENT_DIR/openapi-generator-config.yaml:/local/config.yaml" \
        "openapitools/openapi-generator-cli:${OPENAPI_GENERATOR_VERSION}" generate \
        -i /local/openapi.json \
        -g go \
        -o /local/out \
        -c /local/config.yaml \
        --global-property apiDocs=false,apiTests=false,modelDocs=false,modelTests=false

    # Remove OpenAPI Generator boilerplate files
    echo "Removing boilerplate files..."
    rm -rf docs/ git_push.sh .travis.yml .gitlab-ci.yml .openapi-generator-ignore .openapi-generator/

    # Restore maintained files from temp
    echo "Restoring maintained files..."
    [ -f "$TEMP_DIR/README.md" ] && mv "$TEMP_DIR/README.md" .
    [ -f "$TEMP_DIR/hindclaw_client.go" ] && mv "$TEMP_DIR/hindclaw_client.go" .
    rm -rf "$TEMP_DIR"

    # Fix known generator issue: api_files.go uses os.File but generator omits "os" import.
    # -------------------------------------------------------------------------
    # HINDCLAW-PRESERVED BLOCK: mirrors upstream's api_files.go os-import patch.
    # Only runs if the generator actually produces an api_files.go file, so it's
    # safe to leave in place even when the HindClaw OpenAPI spec doesn't yet
    # declare any multipart/file routes.
    # -------------------------------------------------------------------------
    if [ -f "api_files.go" ] && grep -q 'os\.File' api_files.go && ! grep -q '"os"' api_files.go; then
        echo "Patching api_files.go: adding missing 'os' import..."
        sed -i.bak 's|"net/url"|"net/url"\n\t"os"|' api_files.go
        rm -f api_files.go.bak
    fi

    # Initialize module and build
    echo "Building Go client..."
    go mod tidy
    go build ./...

    echo "Go client generated at $GO_CLIENT_DIR"
fi
echo ""

# Copy the OpenAPI spec into the Rust crate directory so the crates.io publish
# tarball includes a byte-for-byte fallback copy that build.rs can consume when
# the top-level hindclaw-docs/static/openapi.json is absent (e.g. when the
# crate is being built from a downloaded tarball rather than from the monorepo).
# -------------------------------------------------------------------------
# HINDCLAW-PRESERVED STEP: not present upstream. The Rust build.rs in Task 1
# relies on this file as a fallback; removing this step breaks crates.io builds.
# -------------------------------------------------------------------------
echo "Copying OpenAPI spec into Rust crate for publish-tarball fallback..."
cp "$OPENAPI_SPEC" "$RUST_CLIENT_DIR/openapi.json"
echo "  -> $RUST_CLIENT_DIR/openapi.json"
echo ""

echo "=================================================="
echo "Client generation complete!"
echo "=================================================="
echo ""
echo "Rust client:       $RUST_CLIENT_DIR"
echo "Python client:     $PYTHON_CLIENT_DIR"
echo "TypeScript client: $TYPESCRIPT_CLIENT_DIR"
echo "Go client:         $GO_CLIENT_DIR"
echo ""
echo "Important: maintained wrappers (hindclaw_client.py, hindclaw_client.go,"
echo "src/index.ts) and README.md files were preserved."
echo ""
echo "Next steps:"
echo "  1. Review the generated clients"
echo "  2. Update package versions if needed"
echo "  3. Test the clients"
echo "  4. Run 'cargo build' in hindclaw-cli to rebuild with new Rust client"
echo ""
