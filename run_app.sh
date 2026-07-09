#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [ ! -x "venv/bin/python" ]; then
  echo "[ERROR] venv belum tersedia. Jalankan ./setup_ubuntu.sh terlebih dahulu."
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ".env"
  set +a
fi

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-5000}"
export DEBUG="${DEBUG:-False}"

echo "============================================================"
echo " Memulai QR Code Security System"
echo "============================================================"
echo "URL lokal: http://localhost:${PORT}"
echo "Bind: ${HOST}:${PORT}"
echo

exec venv/bin/python app.py
