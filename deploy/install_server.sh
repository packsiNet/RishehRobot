#!/usr/bin/env bash
set -e

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

APP_DIR="/opt/rishehbot"
SERVICE_NAME="rishehbot"

mkdir -p "$APP_DIR"

cat >/etc/systemd/system/${SERVICE_NAME}.service <<SERVICE
[Unit]
Description=RishehBot Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python -m src.bot
Restart=always
RestartSec=5
StandardOutput=append:${APP_DIR}/logs/bot.log
StandardError=append:${APP_DIR}/logs/bot.log

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
echo "Systemd unit installed at /etc/systemd/system/${SERVICE_NAME}.service"
