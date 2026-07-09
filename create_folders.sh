#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

mkdir -p \
  templates/components \
  modules \
  routes \
  static/css \
  static/js \
  static/charts \
  logs/testing \
  static/testing \
  static/testing/reports \
  static/testing/exports \
  static/uploads \
  static/qr \
  static/qr_massal \
  static/qr_fake \
  static/data \
  static/data/payloads \
  data/testing \
  backups/testing \
  temp

touch modules/__init__.py routes/__init__.py

echo "Struktur folder Linux siap."
