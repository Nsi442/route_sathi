#!/usr/bin/env bash
#
# RouteSathi — provision a fresh Ubuntu 24.04 EC2 instance.
#
#   curl -fsSL https://raw.githubusercontent.com/<owner>/route_sathi/main/deploy/setup-ec2.sh | sudo bash
#
# or, from a clone:
#
#   sudo bash deploy/setup-ec2.sh
#
# Installs PostgreSQL + PostGIS, Python, Node, nginx; creates the service
# user; clones or updates the app; builds the frontend; and starts the API
# behind nginx.
#
# Safe to re-run — every step checks before it acts, so this doubles as the
# upgrade path.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Nsi442/route_sathi.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/routesathi}"
APP_USER="${APP_USER:-routesathi}"
ENV_DIR="/etc/routesathi"
ENV_FILE="${ENV_DIR}/routesathi.env"
DB_NAME="${DB_NAME:-routesathi}"
DB_USER="${DB_USER:-routesathi}"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m    %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m!!  %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run this with sudo."

# ── Packages ───────────────────────────────────────────────────────────────
log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    build-essential git curl ca-certificates \
    python3 python3-venv python3-dev \
    postgresql postgresql-contrib postgis postgresql-16-postgis-3 \
    nginx libpq-dev

if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -c2- | cut -d. -f1)" -lt 18 ]]; then
    log "Installing Node.js 20"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi

# ── Service user ───────────────────────────────────────────────────────────
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    log "Creating the ${APP_USER} service account"
    useradd --system --create-home --home-dir "/home/${APP_USER}" --shell /usr/sbin/nologin "$APP_USER"
fi

# ── Database ───────────────────────────────────────────────────────────────
log "Configuring PostgreSQL and PostGIS"
systemctl enable --now postgresql

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    DB_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    sudo -u postgres psql -qc "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';"
    warn "Database password generated. It is written into ${ENV_FILE}."
    NEW_DB_PASS="$DB_PASS"
else
    warn "Role ${DB_USER} already exists; leaving its password alone."
    NEW_DB_PASS=""
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
fi

# PostGIS needs superuser to install, so do it here rather than at app start.
sudo -u postgres psql -d "$DB_NAME" -qc "CREATE EXTENSION IF NOT EXISTS postgis;"
sudo -u postgres psql -d "$DB_NAME" -qc "GRANT ALL ON SCHEMA public TO ${DB_USER};"
POSTGIS_VER="$(sudo -u postgres psql -d "$DB_NAME" -tAc "SELECT postgis_version();" 2>/dev/null || echo 'not installed')"
echo "    PostGIS: ${POSTGIS_VER}"

# ── Application ────────────────────────────────────────────────────────────
if [[ -d "${APP_DIR}/.git" ]]; then
    log "Updating the existing checkout"
    git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$APP_DIR" reset --hard "origin/${BRANCH}"
else
    log "Cloning ${REPO_URL} (${BRANCH})"
    rm -rf "$APP_DIR"
    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

log "Installing Python dependencies"
[[ -d "${APP_DIR}/.venv" ]] || python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --quiet --upgrade pip
"${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"

log "Building the frontend"
cd "$APP_DIR"
npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
npm run build

mkdir -p "${APP_DIR}/.model-cache"
chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"

# ── Environment file ───────────────────────────────────────────────────────
install -d -m 750 "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
    log "Creating ${ENV_FILE}"
    cp "${APP_DIR}/deploy/env.example" "$ENV_FILE"
    JWT="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" "$ENV_FILE"
    if [[ -n "$NEW_DB_PASS" ]]; then
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://${DB_USER}:${NEW_DB_PASS}@localhost:5432/${DB_NAME}|" "$ENV_FILE"
    fi
    sed -i "s|^ML_MODEL_DIR=.*|ML_MODEL_DIR=${APP_DIR}/.model-cache|" "$ENV_FILE"
    sed -i "s|^FRONTEND_DIST=.*|FRONTEND_DIST=${APP_DIR}/dist|" "$ENV_FILE"
    warn "A JWT secret and database password were generated for you."
    warn "Edit ${ENV_FILE} to add your S3 bucket before uploading photos."
else
    warn "${ENV_FILE} already exists; leaving it untouched."
fi
chmod 600 "$ENV_FILE"

# ── Services ───────────────────────────────────────────────────────────────
log "Installing the systemd unit"
cp "${APP_DIR}/deploy/systemd/routesathi-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable routesathi-api
systemctl restart routesathi-api

log "Configuring nginx"
cp "${APP_DIR}/deploy/nginx/routesathi.conf" /etc/nginx/sites-available/routesathi
ln -sf /etc/nginx/sites-available/routesathi /etc/nginx/sites-enabled/routesathi
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

# ── Verify ─────────────────────────────────────────────────────────────────
log "Waiting for the API to come up"
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then break; fi
    sleep 2
done

echo
if curl -fsS http://127.0.0.1:8000/api/health 2>/dev/null | python3 -m json.tool; then
    IP="$(curl -fsS --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'your-instance-ip')"
    log "RouteSathi is running"
    echo "    Open        : http://${IP}/"
    echo "    Health      : http://${IP}/api/health"
    echo "    API logs    : sudo journalctl -u routesathi-api -f"
    echo
    echo "    Next: seed the staff accounts, once."
    echo "      sudo bash ${APP_DIR}/deploy/seed.sh"
    echo
    warn "Then change the seeded passwords — they are published in the repository."
else
    die "The API did not become healthy. Check: sudo journalctl -u routesathi-api -n 60"
fi
