#!/bin/bash
# Parallel linting for all code (Node, Python)
# Runs all linting tasks concurrently for faster execution

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Track all background jobs
declare -a PIDS
declare -a NAMES

run_task() {
    local name="$1"
    local dir="$2"
    shift 2
    local cmd="$@"

    (
        cd "$dir"
        if OUTPUT=$($cmd 2>&1); then
            echo "OK" > "$TEMP_DIR/$name.status"
        else
            echo "FAIL" > "$TEMP_DIR/$name.status"
            echo "$OUTPUT" > "$TEMP_DIR/$name.output"
        fi
    ) &
    PIDS+=($!)
    NAMES+=("$name")
}

echo "  Syncing Python dependencies..."
# Run uv sync first to avoid race conditions when multiple uv run commands
# try to reinstall local packages in parallel (e.g., after version bump)
(cd "$REPO_ROOT/hindclaw-extension" && uv sync --quiet)

echo "  Running lints in parallel..."

# Python hindclaw-extension tasks
run_task "ruff-ext-check" "$REPO_ROOT/hindclaw-extension" "uv run ruff check --fix hindclaw_ext/ tests/"
run_task "ruff-ext-format" "$REPO_ROOT/hindclaw-extension" "uv run ruff format hindclaw_ext/ tests/"
run_task "ty-ext" "$REPO_ROOT/hindclaw-extension" "uv run ty check hindclaw_ext/"

# TypeScript hindclaw-clients/typescript tasks (eslint gated on config presence)
if [ -f "$REPO_ROOT/hindclaw-clients/typescript/.eslintrc.json" ] || [ -f "$REPO_ROOT/hindclaw-clients/typescript/eslint.config.js" ]; then
    run_task "eslint-ts-client" "$REPO_ROOT/hindclaw-clients/typescript" "npx eslint --fix src/**/*.ts"
fi
run_task "prettier-ts-client" "$REPO_ROOT/hindclaw-clients/typescript" "npx prettier --write src/**/*.ts"

# TypeScript hindclaw-docs tasks (both eslint and prettier gated on config presence)
if [ -f "$REPO_ROOT/hindclaw-docs/.eslintrc.json" ] || [ -f "$REPO_ROOT/hindclaw-docs/eslint.config.js" ]; then
    run_task "eslint-docs" "$REPO_ROOT/hindclaw-docs" "npx eslint --fix src/**/*.{ts,tsx}"
fi
if [ -f "$REPO_ROOT/hindclaw-docs/.prettierrc" ] || [ -f "$REPO_ROOT/hindclaw-docs/.prettierrc.json" ] || [ -f "$REPO_ROOT/hindclaw-docs/prettier.config.js" ]; then
    run_task "prettier-docs" "$REPO_ROOT/hindclaw-docs" "npx prettier --write src/**/*.{ts,tsx}"
fi

# Wait for all tasks to complete
for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null || true
done

# Check results
FAILED=0
for name in "${NAMES[@]}"; do
    if [ -f "$TEMP_DIR/$name.status" ]; then
        STATUS=$(cat "$TEMP_DIR/$name.status")
        if [ "$STATUS" = "FAIL" ]; then
            echo ""
            echo "  ❌ $name failed:"
            cat "$TEMP_DIR/$name.output"
            FAILED=1
        fi
    else
        echo "  ❌ $name: no status (crashed?)"
        FAILED=1
    fi
done

if [ $FAILED -eq 1 ]; then
    exit 1
fi

echo "  All lints passed ✓"
