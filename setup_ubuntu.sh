#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "============================================================"
echo " Setup QR Code Security System - Ubuntu 24.04 LTS"
echo "============================================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 tidak ditemukan. Install Python 3 terlebih dahulu."
  exit 1
fi

echo "[1/5] Installing Ubuntu system packages..."
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  build-essential \
  libzbar0 \
  libglib2.0-0 \
  libgl1 \
  fonts-dejavu-core \
  redis-server

echo "[2/5] Preparing runtime folders..."
mkdir -p \
  logs/testing \
  static/uploads \
  static/qr \
  static/qr_massal \
  static/qr_fake \
  static/data \
  static/data/payloads \
  static/testing \
  static/testing/reports \
  static/testing/exports \
  data/testing \
  backups/testing \
  temp

echo "[3/5] Creating Python virtual environment..."
python3 -m venv venv

echo "[4/6] Installing Python dependencies..."
venv/bin/python -m pip install --upgrade pip setuptools wheel
venv/bin/python -m pip install -r requirements.txt

echo "[5/6] Verifying Python imports..."
venv/bin/python - <<'PY'
import importlib

modules = [
    'flask',
    'Crypto',
    'qrcode',
    'cv2',
    'pyzbar.pyzbar',
    'flask_limiter',
    'limits',
    'redis',
    'PIL',
    'pandas',
    'matplotlib',
    'numpy',
    'psutil',
    'scipy',
    'werkzeug',
    'prometheus_client',
    'schedule',
    'gunicorn',
]

for module in modules:
    importlib.import_module(module)

print('[OK] Semua import dependency utama berhasil.')
PY

echo "[6/6] Preparing environment file..."
if [ ! -f .env ]; then
  cp .env.ubuntu.example .env
  echo "[INFO] File .env dibuat dari .env.ubuntu.example. Ubah SECRET_KEY dan AUTH_PASSWORD sebelum production."
else
  echo "[INFO] File .env sudah ada, tidak ditimpa."
fi

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable --now redis-server >/dev/null 2>&1 || true
fi

echo "============================================================"
echo " Setup selesai."
echo " Jalankan aplikasi dengan: ./run_app.sh"
echo "============================================================"
