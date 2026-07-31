#!/usr/bin/env bash
#
# Health check berkala SI penelitian QR Code RSA-PSS.
#
# Memeriksa aplikasi lewat HTTP, bukan sekadar `systemctl is-active`: proses
# dapat berstatus aktif namun berhenti melayani permintaan.
#
# Restart hanya dilakukan bila SELURUH syarat berikut terpenuhi:
#   1. dua pemeriksaan berturut-turut gagal, bukan satu kali saja
#   2. tidak ada tanda pekerjaan latar yang sedang berjalan
#
# Syarat kedua penting. Generate dan verifikasi massal berjalan sebagai thread
# daemon di dalam worker gunicorn, sehingga restart akan membunuhnya tanpa jejak
# — pekerjaan berjam-jam bisa hilang saat hampir selesai. Aplikasi yang sedang
# sibuk memproses ratusan ribu berkas boleh saja lambat merespons; itu bukan
# alasan untuk mematikannya.
#
set -uo pipefail

ENDPOINT="http://127.0.0.1:5000/"
UNIT=qrcode.service
DATA_DIR=/opt/qrcode/static/data
BATAS_DETIK=30
JEDA_ULANG=20
LOG=/var/log/qrcode-healthcheck.log
PENANDA=/run/qrcode-healthcheck.count

log() { echo "[$(date -Is)] $*" >> "$LOG"; }

periksa() {
  curl -s -o /dev/null -w '%{http_code}' -m "$BATAS_DETIK" "$ENDPOINT" 2>/dev/null || echo 000
}

# Deteksi pekerjaan latar: jumlah record bertambah dalam rentang pengamatan
# berarti aplikasi jelas masih bekerja, betapapun lambat ia menjawab HTTP.
sedang_bekerja() {
  local a b
  a=$(find "$DATA_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
  sleep 10
  b=$(find "$DATA_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
  [ "$b" -gt "$a" ]
}

KODE=$(periksa)

# 2xx dan 3xx sama-sama sehat: beranda mengalihkan ke halaman login.
if [[ "$KODE" =~ ^[23] ]]; then
  rm -f "$PENANDA"
  exit 0
fi

log "Pemeriksaan pertama gagal (kode '$KODE'), mencoba ulang dalam ${JEDA_ULANG}s"
sleep "$JEDA_ULANG"
KODE2=$(periksa)

if [[ "$KODE2" =~ ^[23] ]]; then
  log "Pemeriksaan kedua sehat (kode '$KODE2'), tidak ada tindakan"
  rm -f "$PENANDA"
  exit 0
fi

if sedang_bekerja; then
  log "TIDAK SEHAT (kode '$KODE2') NAMUN pekerjaan latar terdeteksi berjalan — restart DIBATALKAN"
  exit 0
fi

log "TIDAK SEHAT: dua pemeriksaan gagal (kode '$KODE2'), tidak ada pekerjaan latar. Restart $UNIT"
systemctl restart "$UNIT"
sleep 8

KODE3=$(periksa)
if [[ "$KODE3" =~ ^[23] ]]; then
  log "PULIH: restart berhasil, endpoint mengembalikan '$KODE3'"
  exit 0
fi

log "GAGAL PULIH: setelah restart endpoint mengembalikan '$KODE3'"
systemctl status "$UNIT" --no-pager -n 20 >> "$LOG" 2>&1
# Hanya kegagalan pemulihan yang diberitakan. Restart yang berhasil tidak
# menghasilkan notifikasi — yang perlu perhatian manusia adalah saat sistem
# sudah mencoba menolong dirinya sendiri dan tetap gagal.
/opt/qrcode/deploy/maintenance/notify.sh critical \
    "Aplikasi tidak pulih setelah restart" \
    "Endpoint mengembalikan '$KODE3' setelah restart otomatis. Periksa: journalctl -u $UNIT -n 50"
exit 1
