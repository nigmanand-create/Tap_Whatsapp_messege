#!/usr/bin/env bash
# Runner script: loads .env.local and executes the bench call to run the Glific test
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="$ROOT_DIR/.env.local"

if [[ -f "$ENV_FILE" ]]; then
  export $(grep -v '^#' "$ENV_FILE" | xargs)
else
  echo ".env.local not found in $ROOT_DIR. Copy .env.sample to .env.local and populate it." >&2
  exit 1
fi

echo "Running Glific send test (DRY_RUN=$DRY_RUN) against site tapbuddy.local"
bench --site tapbuddy.local execute "import tap_buddy.scripts.send_glific_test as s; s.send_from_env()"
