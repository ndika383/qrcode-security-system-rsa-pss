#!/usr/bin/env bash
#
# Backup terjadwal SI penelitian QR Code RSA-PSS.
#
#   backup-qrcode.sh harian   -> data kritis saja, cepat, dijalankan tiap hari
#   backup-qrcode.sh penuh    -> termasuk static/data, dijalankan mingguan
#
# Yang dicakup dan alasannya:
#   rsa_key.pem, ecdsa_key.pem   kunci penandatangan. Hilang = seluruh QR yang
#                                pernah terbit tidak dapat diverifikasi lagi.
#   logs/security_state.db       ledger nonce dan index record. Hilang = deteksi
#                                replay kehilangan seluruh riwayatnya.
#   logs/*.csv                   log generate dan verifikasi, sumber metrik.
#   data/task_results/           hasil task, bukti penelitian.
#   deploy/                      berkas unit systemd dan vhost nginx.
#   static/data/                 record QR itu sendiri (hanya mode penuh).
#                                Tanpa ini verifikasi melaporkan seluruh QR
#                                sebagai "Data Tidak Ditemukan di Database".
#
# Kode sumber sengaja tidak dicakup: sudah berada di git.
#
set -euo pipefail

APP_DIR=/opt/qrcode
TUJUAN="$APP_DIR/backups/otomatis"
MODE="${1:-harian}"
SIMPAN_HARIAN=7
SIMPAN_PENUH=4
MIN_SISA_GB=5

# Isi GPG_RECIPIENT dengan key id publik untuk mengenkripsi arsip. Dikosongkan
# berarti arsip disimpan apa adanya — aman selama tetap di server ini (mode 0600,
# root saja), tetapi WAJIB dienkripsi sebelum disalin ke luar karena memuat kunci
# privat. Enkripsi memakai kunci publik, bukan passphrase, agar dapat berjalan
# tanpa campur tangan manusia.
GPG_RECIPIENT="${GPG_RECIPIENT:-}"

STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$TUJUAN"
chmod 700 "$TUJUAN"

log() { echo "[$(date -Is)] $*"; }

case "$MODE" in
  harian|penuh) ;;
  *) log "GALAT: mode tidak dikenal '$MODE' (gunakan: harian | penuh)"; exit 2 ;;
esac

# Jangan sampai backup justru memenuhi disk dan mematikan aplikasi.
SISA_GB=$(df -BG --output=avail "$APP_DIR" | tail -1 | tr -dc '0-9')
if [ "$SISA_GB" -lt "$MIN_SISA_GB" ]; then
  log "GALAT: sisa disk ${SISA_GB}GB di bawah ambang ${MIN_SISA_GB}GB, backup dibatalkan"
  exit 1
fi

ARSIP="$TUJUAN/qrcode-${MODE}-${STAMP}.tar.gz"
log "Mulai backup mode=$MODE -> $ARSIP (sisa disk ${SISA_GB}GB)"

SUMBER=(
  rsa_key.pem
  ecdsa_key.pem
  logs
  data/task_results
  deploy
)
[ "$MODE" = "penuh" ] && SUMBER+=(static/data)

# Log rotasi lama dan cache tidak perlu ikut; ukurannya besar tanpa nilai pemulihan.
tar -czf "$ARSIP" -C "$APP_DIR" \
  --exclude='logs/*.backup_*' \
  --exclude='logs/*.bak_*' \
  --exclude='__pycache__' \
  --ignore-failed-read \
  "${SUMBER[@]}" 2>/dev/null

chmod 600 "$ARSIP"

# Verifikasi integritas: arsip yang tidak dapat dibaca ulang tidak berguna.
if ! tar -tzf "$ARSIP" >/dev/null 2>&1; then
  log "GALAT: arsip gagal diverifikasi, dihapus"
  rm -f "$ARSIP"
  /opt/qrcode/deploy/maintenance/notify.sh critical \
      "Backup gagal diverifikasi" \
      "Arsip mode $MODE gagal dibaca ulang setelah dibuat dan telah dihapus. Tidak ada backup baru untuk siklus ini."
  exit 1
fi

JML=$(tar -tzf "$ARSIP" | wc -l)
UKURAN=$(du -h "$ARSIP" | cut -f1)
sha256sum "$ARSIP" > "$ARSIP.sha256"
chmod 600 "$ARSIP.sha256"
log "Arsip terverifikasi: $JML entri, $UKURAN"

if [ -n "$GPG_RECIPIENT" ]; then
  gpg --batch --yes --trust-model always -r "$GPG_RECIPIENT" -o "$ARSIP.gpg" -e "$ARSIP"
  chmod 600 "$ARSIP.gpg"
  rm -f "$ARSIP"
  sha256sum "$ARSIP.gpg" > "$ARSIP.gpg.sha256"
  log "Arsip dienkripsi untuk $GPG_RECIPIENT"
else
  log "PERINGATAN: GPG_RECIPIENT kosong, arsip tidak dienkripsi (memuat kunci privat)"
fi

# Retensi
SIMPAN=$([ "$MODE" = "penuh" ] && echo "$SIMPAN_PENUH" || echo "$SIMPAN_HARIAN")
mapfile -t LAMA < <(ls -1t "$TUJUAN"/qrcode-"$MODE"-*.tar.gz* 2>/dev/null | grep -v '\.sha256$' | tail -n +$((SIMPAN + 1)))
for f in "${LAMA[@]:-}"; do
  [ -n "$f" ] || continue
  rm -f "$f" "$f.sha256"
  log "Retensi: dihapus $(basename "$f")"
done

log "Selesai. Total arsip tersimpan: $(ls -1 "$TUJUAN"/qrcode-*.tar.gz* 2>/dev/null | grep -vc '\.sha256$' || echo 0)"
log "Catatan: arsip berada di disk yang sama dengan aplikasi. Salinan luar-server tetap diperlukan."
