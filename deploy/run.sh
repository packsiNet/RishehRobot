#!/usr/bin/env bash
set -e
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
python3 -m venv .venv || true
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p logs data
export PYTHONUNBUFFERED=1
pkill -f "python -m src.bot" || true
nohup python -m src.bot >> logs/bot.log 2>&1 &
sleep 2
pgrep -f "python -m src.bot" >/dev/null
echo "---- last logs ----"
tail -n 80 logs/bot.log || true
