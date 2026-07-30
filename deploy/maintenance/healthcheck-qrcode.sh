#!/usr/bin/env bash
#
# Health check berkala SI penelitian QR Code RSA-PSS.
#
# Memeriksa aplikasi lewat HTTP, bukan sekadar `systemctl is-active`: proses
# dapat berstatus aktif namun berhenti melayani permintaan. Restart hanya
# dilakukan bila aplikasi benar-benar tidak merespons.
#
set -uo pipefail

ENDPOINT="http://127.0.0.1:5000/"
UNIT=qrcode.service
BATAS_DETIK=15
LOG=/var/log/qrcode-healthcheck.log

log() { echo "[$(date -Is)] $*" >> "$LOG"; }

KODE=$(curl -s -o /dev/null -w '%{http_code}' -m "$BATAS_DETIK" "$ENDPOINT" 2>/dev/null || echo 000)

# 2xx dan 3xx sama-sama sehat: beranda mengalihkan ke halaman login.
if [[ "$KODE" =~ ^[23] ]]; then
  exit 0
fi

log "TIDAK SEHAT: endpoint mengembalikan '$KODE', mencoba restart $UNIT"
systemctl restart "$UNIT"
sleep 5

KODE2=$(curl -s -o /dev/null -w '%{http_code}' -m "$BATAS_DETIK" "$ENDPOINT" 2>/dev/null || echo 000)
if [[ "$KODE2" =~ ^[23] ]]; then
  log "PULIH: restart berhasil, endpoint mengembalikan '$KODE2'"
  exit 0
fi

log "GAGAL PULIH: setelah restart endpoint mengembalikan '$KODE2'"
systemctl status "$UNIT" --no-pager -n 20 >> "$LOG" 2>&1
exit 1
