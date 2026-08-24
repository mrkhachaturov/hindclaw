#!/usr/bin/env bash
#MISE description="Push dist/client/search-index.json into the Typesense collection"
#MISE dir="{{config_root}}"
#MISE depends=["build"]
set -euo pipefail

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

exec node scripts/sync-typesense.ts
