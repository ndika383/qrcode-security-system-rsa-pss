#!/usr/bin/env bash
#
# Pemeriksaan harian SI penelitian QR Code RSA-PSS.
#
# Hanya melaporkan yang perlu ditindaklanjuti. Pemeriksaan yang lolos tidak
# menghasilkan notifikasi sama sekali — alert yang berbunyi setiap hari akan
# diabaikan orang, dan alert yang diabaikan sama saja dengan tidak ada.
#
set -uo pipefail

NOTIFY=/opt/qrcode/deploy/maintenance/notify.sh
APP_DIR=/opt/qrcode
DOMAIN=rsa-pss.com
AMBANG_DISK=85          # persen
AMBANG_SERTIFIKAT=21    # hari
LOG=/var/log/qrcode-maintenance.log

MASALAH=()
log() { echo "[$(date -Is)] $*" >> "$LOG"; }

# 1. Kapasitas disk. Backup harian menulis ke disk yang sama dengan aplikasi,
#    sehingga disk penuh berarti backup berhenti sekaligus aplikasi terganggu.
PAKAI=$(df --output=pcent "$APP_DIR" | tail -1 | tr -dc '0-9')
[ "$PAKAI" -ge "$AMBANG_DISK" ] && MASALAH+=("Disk terpakai ${PAKAI}% (ambang ${AMBANG_DISK}%)")

# 2. Masa berlaku sertifikat. Perpanjangan otomatis memang aktif, tetapi
#    kegagalannya senyap — tanpa pemeriksaan ini, kedaluwarsa baru ketahuan
#    saat pengguna tidak dapat membuka situs.
AKHIR=$(echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$AKHIR" ]; then
  SISA=$(( ( $(date -d "$AKHIR" +%s) - $(date +%s) ) / 86400 ))
  [ "$SISA" -le "$AMBANG_SERTIFIKAT" ] && MASALAH+=("Sertifikat $DOMAIN tersisa ${SISA} hari")
fi

# 3. Kesegaran backup. Skrip backup yang mati tidak mengumumkan dirinya;
#    yang terlihat hanya arsip yang berhenti bertambah.
TERBARU=$(find "$APP_DIR/backups/otomatis" -name '*.tar.gz' -mtime -2 2>/dev/null | wc -l)
[ "$TERBARU" -eq 0 ] && MASALAH+=("Tidak ada arsip backup baru dalam 48 jam terakhir")

# 4. Konsistensi index terhadap record di disk. Selisih berarti verifikasi dapat
#    melaporkan QR sah sebagai tidak ditemukan.
KONSISTEN=$(/opt/qrcode/venv/bin/python - <<'PY' 2>/dev/null
import sqlite3, os
try:
    c = sqlite3.connect('/opt/qrcode/logs/security_state.db')
    idx = c.execute('SELECT COUNT(*) FROM qr_record_index').fetchone()[0]
    c.close()
    disk = len([f for f in os.listdir('/opt/qrcode/static/data') if f.endswith('.json')])
    print(disk - idx)
except Exception:
    print('galat')
PY
)
[ "$KONSISTEN" != "0" ] && MASALAH+=("Index tidak konsisten dengan disk (selisih: $KONSISTEN)")

# 5. Integritas basis data.
INTEG=$(/opt/qrcode/venv/bin/python -c "
import sqlite3
try:
    c=sqlite3.connect('/opt/qrcode/logs/security_state.db')
    print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()
except Exception as e: print('galat')" 2>/dev/null)
[ "$INTEG" != "ok" ] && MASALAH+=("Integritas basis data: $INTEG")

if [ ${#MASALAH[@]} -eq 0 ]; then
  log "Pemeriksaan harian: seluruh butir lolos (disk ${PAKAI}%, sertifikat ${SISA:-?} hari)"
  exit 0
fi

PESAN=$(printf '%s\n' "${MASALAH[@]}")
log "Pemeriksaan harian menemukan ${#MASALAH[@]} masalah"
"$NOTIFY" warning "Pemeriksaan harian: ${#MASALAH[@]} masalah" "$PESAN"
