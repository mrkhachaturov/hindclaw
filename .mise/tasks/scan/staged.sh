#!/usr/bin/env bash
#MISE description="Infisical secret scan of STAGED changes — used by the hk pre-commit hook"
#MISE dir="{{config_root}}"
set -eo pipefail
exec infisical scan git-changes --staged --verbose
