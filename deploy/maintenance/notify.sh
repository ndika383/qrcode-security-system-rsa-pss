#!/usr/bin/env bash
#
# Pengirim notifikasi SI penelitian QR Code RSA-PSS.
#
#   notify.sh <tingkat> <judul> <pesan>
#   notify.sh --test
#
# Tingkat: info | warning | critical
#
# Kanal ditentukan berkas konfigurasi /etc/qrcode-notify.conf yang memuat
# kredensial dan karenanya berizin 0600 milik root. Skrip ini sengaja tidak
# memuat kredensial apa pun agar dapat ikut terlacak git.
#
# Domain rsa-pss.com memiliki record MX yang menunjuk ke server ini, tetapi tidak
# ada MTA yang berjalan. Email dari/ke domain tersebut karenanya tidak berfungsi,
# dan kanal email hanya sah lewat relay SMTP eksternal.
#
set -uo pipefail

KONFIG=/etc/qrcode-notify.conf
LOG=/var/log/qrcode-notify.log
HOSTNAME_=$(hostname)

log() { echo "[$(date -Is)] $*" >> "$LOG" 2>/dev/null || true; }

if [ ! -r "$KONFIG" ]; then
  log "GALAT: $KONFIG tidak terbaca — notifikasi dilewati"
  exit 0   # sengaja 0: kegagalan notifikasi tidak boleh menggagalkan pemanggilnya
fi
# shellcheck source=/dev/null
. "$KONFIG"

KANAL="${NOTIFY_CHANNEL:-none}"

if [ "${1:-}" = "--test" ]; then
  TINGKAT=info
  JUDUL="Uji notifikasi"
  PESAN="Pesan uji dari $HOSTNAME_ pada $(date -Is). Bila Anda menerima ini, kanal $KANAL berfungsi."
else
  TINGKAT="${1:-info}"
  JUDUL="${2:-Tanpa judul}"
  PESAN="${3:-}"
fi

case "$TINGKAT" in
  critical) IKON="🔴" ;;
  warning)  IKON="🟠" ;;
  *)        IKON="🔵" ;;
esac

TEKS="$IKON [$HOSTNAME_] $JUDUL

$PESAN

Waktu: $(date -Is)"

kirim_telegram() {
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] || {
    log "GALAT: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diisi"; return 1; }
  curl -sS -m 20 -o /dev/null -w '%{http_code}' \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${TEKS}"
}

kirim_discord() {
  [ -n "${DISCORD_WEBHOOK_URL:-}" ] || { log "GALAT: DISCORD_WEBHOOK_URL belum diisi"; return 1; }
  curl -sS -m 20 -o /dev/null -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -d "$(printf '{"content": %s}' "$(printf '%s' "$TEKS" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')")" \
    "$DISCORD_WEBHOOK_URL"
}

kirim_webhook() {
  [ -n "${WEBHOOK_URL:-}" ] || { log "GALAT: WEBHOOK_URL belum diisi"; return 1; }
  curl -sS -m 20 -o /dev/null -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -d "$(python3 -c 'import json,sys,os; print(json.dumps({"host":os.environ["H"],"level":os.environ["L"],"title":os.environ["T"],"message":os.environ["M"]}))' )" \
    "$WEBHOOK_URL"
}

kirim_email() {
  command -v msmtp >/dev/null 2>&1 || { log "GALAT: msmtp belum terpasang"; return 1; }
  [ -n "${EMAIL_TO:-}" ] || { log "GALAT: EMAIL_TO belum diisi"; return 1; }
  printf 'To: %s\nSubject: %s [%s] %s\n\n%s\n' \
    "$EMAIL_TO" "$IKON" "$HOSTNAME_" "$JUDUL" "$PESAN" | msmtp "$EMAIL_TO" && echo 200
}

case "$KANAL" in
  telegram) HASIL=$(kirim_telegram) ;;
  discord)  HASIL=$(kirim_discord) ;;
  webhook)  HASIL=$(H="$HOSTNAME_" L="$TINGKAT" T="$JUDUL" M="$PESAN" kirim_webhook) ;;
  email)    HASIL=$(kirim_email) ;;
  none)     log "Kanal 'none' — notifikasi [$TINGKAT] $JUDUL tidak dikirim"; exit 0 ;;
  *)        log "GALAT: kanal '$KANAL' tidak dikenal"; exit 0 ;;
esac

if [[ "${HASIL:-}" =~ ^2 ]]; then
  log "TERKIRIM via $KANAL [$TINGKAT] $JUDUL"
else
  log "GAGAL via $KANAL (kode '${HASIL:-kosong}') [$TINGKAT] $JUDUL"
fi
exit 0
