#!/usr/bin/env bash
#MISE description="Infisical secret scan of the FULL git history (run once, or in CI)"
#MISE dir="{{config_root}}"
set -eo pipefail
exec infisical scan --verbose
