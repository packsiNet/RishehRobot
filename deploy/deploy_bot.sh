#!/usr/bin/env bash
set -e

BOT_TOKEN="$1"
RUN_AS="$2"
DB_URL_UNUSED="$3"

APP_DIR="/opt/rishehrobot"
VENV_DIR="${APP_DIR}/.venv"
LOG_DIR="${APP_DIR}/logs"
DATA_DIR="${APP_DIR}/data"
SERVICE_NAME="rishehrobot"

if [ -z "$RUN_AS" ]; then
  echo "RUN_AS (server user) is required as 2nd arg" >&2
  exit 1
fi

mkdir -p "$LOG_DIR" "$DATA_DIR"

python3 -m venv "$VENV_DIR" || true
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"

# Write .env
if [ -n "$BOT_TOKEN" ]; then
  cat >"${APP_DIR}/.env" <<ENV
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
DB_PATH=${DATA_DIR}/app.db
ENV
fi

chown -R "$RUN_AS":"$RUN_AS" "$APP_DIR"

# Enable and restart service with specified user
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}.service
systemctl stop ${SERVICE_NAME}.service || true

# Ensure service runs as desired user
sed -i "s/^User=.*/User=${RUN_AS}/" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl start ${SERVICE_NAME}.service

sleep 2
systemctl is-active --quiet ${SERVICE_NAME} || (
  journalctl -u ${SERVICE_NAME} -n 100 --no-pager; exit 1)

echo "Service ${SERVICE_NAME} is active"
