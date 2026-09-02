#!/usr/bin/env bash
#
# Seed the demo accounts, facilities and reports against the live database.
# Run once after the first deploy:
#
#   sudo bash /opt/routesathi/deploy/seed.sh
#
# Sourcing the env file (rather than `env $(grep ... | xargs)`) keeps values
# containing spaces or '#' intact.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/routesathi}"
APP_USER="${APP_USER:-routesathi}"
ENV_FILE="${ENV_FILE:-/etc/routesathi/routesathi.env}"

[[ -f "$ENV_FILE" ]] || { echo "No env file at ${ENV_FILE}" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

cd "$APP_DIR"
sudo -u "$APP_USER" --preserve-env=DATABASE_URL,JWT_SECRET,ML_MODEL_DIR,ML_ENABLED,SEED_DEFAULT_PASSWORD \
    "${APP_DIR}/.venv/bin/python" scripts/seed_data.py "$@"

if [[ "${SEED_DEFAULT_PASSWORD:-Password123!}" == "Password123!" ]]; then
cat <<'MSG'

Seeded with the PUBLISHED default password. Sign in and change all three now,
or set SEED_DEFAULT_PASSWORD in the env file and re-seed.

  citizen     ananya@routesathi.app
  authority   authority@routesathi.app
  maintenance maintenance@routesathi.app
MSG
else
    echo
    echo "Seeded using the password from SEED_DEFAULT_PASSWORD."
fi
