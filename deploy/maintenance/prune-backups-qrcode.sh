#!/usr/bin/env bash
#
# Pembersihan berkas sisa operasi di direktori log aplikasi.
#
# Setiap Reset Statistik dan beberapa operasi pemeliharaan meninggalkan salinan
# berpola *.backup_* dan *.bak_*. Berkas ini menumpuk tanpa batas: pada 30 Juli
# 2026 direktori logs/ mencapai 120 MB dengan sebagian besar berupa sisa
# semacam itu, beberapa berumur lebih dari enam bulan.
#
# Berkas log_verifikasi.csv dan log_generate.csv yang aktif TIDAK disentuh —
# keduanya sumber metrik dashboard.
#
set -euo pipefail

LOG_DIR=/opt/qrcode/logs
UMUR_HARI=30
LOG=/var/log/qrcode-maintenance.log

log() { echo "[$(date -Is)] $*" >> "$LOG"; }

SEBELUM=$(du -sm "$LOG_DIR" | cut -f1)

JML=$(find "$LOG_DIR" -maxdepth 1 -type f \
  \( -name '*.backup_*' -o -name '*.bak_*' \) \
  -mtime +"$UMUR_HARI" -print -delete | wc -l)

SESUDAH=$(du -sm "$LOG_DIR" | cut -f1)
log "Pembersihan sisa backup: $JML berkas >${UMUR_HARI} hari dihapus, ${SEBELUM}MB -> ${SESUDAH}MB"
