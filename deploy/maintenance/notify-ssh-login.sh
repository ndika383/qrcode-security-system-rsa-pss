#!/usr/bin/env bash
#
# Beritakan sesi SSH yang BERHASIL dibuka.
#
# Dipanggil PAM lewat pam_exec pada sshd. Yang diberitakan sengaja keberhasilan,
# bukan kegagalan: server ini mencatat lebih dari 24.000 percobaan login gagal,
# sehingga memberitakan kegagalan akan menghasilkan ratusan notifikasi per hari
# dan berujung diabaikan. Kegagalan sudah ditangani fail2ban pada lapisan yang
# tepat.
#
# Keberhasilan justru bernilai tinggi dan bervolume sangat rendah: hanya pemilik
# server yang masuk. Bila suatu saat muncul pemberitahuan yang tidak Anda kenali,
# itulah yang benar-benar perlu ditindaklanjuti.
#
set -uo pipefail

# pam_exec dipanggil pada pembukaan maupun penutupan sesi.
[ "${PAM_TYPE:-}" = "open_session" ] || exit 0

PENGGUNA="${PAM_USER:-tidak diketahui}"
ASAL="${PAM_RHOST:-lokal}"
LAYANAN="${PAM_SERVICE:-ssh}"

# IP pemilik server yang sudah dikenal. Login dari sini tetap diberitakan —
# justru itu gunanya, sebagai konfirmasi rutin bahwa notifikasi masih hidup —
# tetapi ditandai agar yang tidak dikenal langsung menonjol.
case "$ASAL" in
  202.91.8.200|210.87.83.219) TANDA="dikenal" ; TINGKAT=info ;;
  *)                          TANDA="TIDAK DIKENAL" ; TINGKAT=warning ;;
esac

/opt/qrcode/deploy/maintenance/notify.sh "$TINGKAT" \
  "Sesi SSH dibuka: $PENGGUNA" \
  "Asal   : $ASAL ($TANDA)
Layanan: $LAYANAN
Metode : dua faktor (password + TOTP)

Bila bukan Anda, segera ganti password dan periksa: last -n 20" &

# Notifikasi dijalankan di latar dan skrip selalu keluar 0. Login tidak boleh
# tertunda maupun gagal hanya karena pengiriman notifikasi bermasalah.
exit 0
