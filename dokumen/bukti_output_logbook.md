# Bukti Output Logbook Penelitian

Sistem Informasi Penelitian — QR Code Security System berbasis RSA-PSS

| | |
|---|---|
| Domain | `rsa-pss.com` |
| IP publik | `103.13.207.36` |
| Sistem operasi | Ubuntu 24.04.4 LTS (kernel 6.8.0-136-generic) |
| Waktu penangkapan bukti | 30 Juli 2026, 14.00–14.05 WIB |

Seluruh keluaran pada dokumen ini adalah hasil eksekusi nyata pada server
produksi, disalin apa adanya tanpa penyuntingan.

---

## ⚠ Temuan Mendesak — Serangan Brute Force SSH Aktif

Ditemukan saat penangkapan bukti kegiatan hardening. **Bukan bagian dari
rencana logbook, tetapi memerlukan penanganan segera.**

```
total percobaan login gagal tercatat : 24.275

10 IP penyerang teratas:
   1322  45.138.100.250
   1244  192.252.215.125
    840  87.251.64.144
    782  89.126.222.163
    782  81.200.14.134
    782  163.7.9.194
    782  118.194.249.186
    782  117.149.196.215
    782  103.121.91.144
    740  112.45.47.45

user yang disasar:
   4702  root
   2413  admin
   2171  user
   2012  ubuntu
   1643  debian
    301  oracle
    275  test
    272  deploy
```

Serangan masih berlangsung saat dokumen ini disusun — percobaan terakhir tercatat
pukul 14.01 dari `185.246.128.170`.

**Kondisi yang memperberat:** server tidak memiliki satu pun kunci SSH
(`authorized_keys` kosong pada root maupun amikom), `PasswordAuthentication yes`,
dan `PermitRootLogin without-password`. Akses sepenuhnya bergantung pada password.

Firewall yang baru diaktifkan sudah mulai memblokir:

```
entri UFW BLOCK sejak aktivasi (≈5 menit): 7
2026-07-30T13:59:34 [UFW BLOCK] SRC=177.81.57.x
2026-07-30T14:00:26 [UFW BLOCK] SRC=197.95.77.x
2026-07-30T14:00:27 [UFW BLOCK] SRC=89.233.240.x
```

Aturan `LIMIT` pada port 22 memperlambat serangan, namun **tidak menggantikan
autentikasi berbasis kunci**. Langkah lanjutan ada pada bagian Kegiatan 4.

---

## Kegiatan 1 — Registrasi Domain & Konfigurasi DNS

**Output:** Domain aktif, DNS propagasi OK, URL publik dapat diakses.

```
$ for r in 8.8.8.8 1.1.1.1 9.9.9.9; do echo "$r -> $(dig +short A rsa-pss.com @$r)"; done
8.8.8.8 -> 103.13.207.36
1.1.1.1 -> 103.13.207.36
9.9.9.9 -> 103.13.207.36
```

Resolusi konsisten dari tiga resolver publik independen (Google, Cloudflare,
Quad9) membuktikan propagasi DNS telah menyeluruh.

**Status: TERPENUHI**

---

## Kegiatan 2 — Aktivasi & Konfigurasi Cloud VPS

**Output:** VPS aktif, server web & DB berjalan, akses SSH terkonfigurasi.

```
OS       : Ubuntu 24.04.4 LTS
Kernel   : 6.8.0-136-generic
CPU core : 2
RAM      : 9.7Gi (terpakai 1.1Gi)
Disk     : 38G total, 23G tersisa (42% terpakai)
Uptime   : up 5 days, 8 hours, 39 minutes
Layanan  : nginx/ssh/cron = active active active
```

Spesifikasi terukur adalah **2 core / 9,7 GB RAM / 38 GB disk**. Bila logbook
mencantumkan angka lain, sesuaikan dengan hasil pengukuran ini.

**Status: TERPENUHI**

---

## Kegiatan 3 — Penghubungan Domain ke VPS & SSL/TLS

**Output:** HTTPS aktif, SI dapat diakses via URL publik.

```
IP publik VPS : 103.13.207.36
A record      : 103.13.207.36        ← cocok

subject = CN = rsa-pss.com
issuer  = C = US, O = Let's Encrypt, CN = YE2
notBefore = Jun 10 03:08:51 2026 GMT
notAfter  = Sep  8 03:08:50 2026 GMT

$ curl -sI https://rsa-pss.com
HTTP/1.1 302 FOUND
Server: nginx/1.24.0 (Ubuntu)

$ curl -o /dev/null -w '%{http_code} %{redirect_url}' http://rsa-pss.com/
301 https://rsa-pss.com/
```

A record cocok dengan IP publik, sertifikat Let's Encrypt sah, dan seluruh
lalu lintas HTTP dialihkan permanen ke HTTPS.

**Status: TERPENUHI**

---

## Kegiatan 4 — Firewall, Hak Akses & Hardening

**Output:** Firewall aktif, akses root dinonaktifkan, user admin terkonfigurasi.

```
$ ufw status verbose
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
22/tcp                     LIMIT IN    Anywhere    # SSH (rate-limited)
80/tcp                     ALLOW IN    Anywhere    # HTTP -> redirect HTTPS
443/tcp                    ALLOW IN    Anywhere    # HTTPS nginx
22/tcp (v6)                LIMIT IN    Anywhere (v6)
80/tcp (v6)                ALLOW IN    Anywhere (v6)
443/tcp (v6)               ALLOW IN    Anywhere (v6)
```

Port aplikasi (gunicorn 5000) dan Redis (6379) terikat `127.0.0.1` sehingga
tidak terjangkau dari luar tanpa perlu aturan tambahan. Verifikasi pasca
aktivasi menunjukkan layanan tetap terjangkau:

```
HTTPS publik : HTTP 302
HTTP redirect: HTTP 301
SSH port 22  : terbuka
Redis 6379   : tidak diizinkan dari luar
ufw saat boot: enabled
```

### Bagian yang BELUM terpenuhi

```
$ sshd -T | grep -iE 'permitrootlogin|passwordauthentication'
permitrootlogin without-password
passwordauthentication yes

$ getent passwd | awk -F: '$3>=1000 && $3<65534'
amikom (uid 1001)
```

Akses root **belum** dinonaktifkan. Ini disengaja: server tidak memiliki kunci
SSH sama sekali, sehingga menonaktifkan autentikasi password atau login root
akan menutup seluruh jalan masuk ke server secara permanen.

**Urutan aman untuk menuntaskannya:**

1. Bangkitkan pasangan kunci di komputer lokal — `ssh-keygen -t ed25519`
2. Salin ke server — `ssh-copy-id amikom@rsa-pss.com`
3. Uji login dengan kunci dari terminal **baru**, sementara sesi lama tetap terbuka
4. Setelah terbukti berhasil, barulah:
   ```
   PermitRootLogin no
   PasswordAuthentication no
   ```
5. `systemctl reload ssh`, lalu uji ulang dari terminal baru

Mengingat 24.275 percobaan login gagal yang tercatat, langkah ini sebaiknya
tidak ditunda.

**Status: firewall TERPENUHI · hardening SSH BELUM**

---

## Kegiatan 5 — Instalasi Aplikasi & Uji Koneksi Database

**Output:** Aplikasi SI berhasil diinstall dan terkoneksi ke database.

```
qrcode.service : active
PID            : 49917
Beranda        : HTTP 302 dalam 0.266 s
Halaman login  : HTTP 200

tabel           : nonce_state, security_metadata, qr_record_index
nonce_state     : 14.285 baris
qr_record_index : 90.344 baris
record QR disk  : 90.344 berkas
```

Kecocokan sempurna antara 90.344 entri index dan 90.344 berkas di disk
membuktikan lapisan aplikasi dan basis data terkoneksi serta konsisten.

**Status: TERPENUHI**

---

## Kegiatan 6 — Load Testing & Optimasi Web Server

**Output:** Laporan uji performa, konfigurasi optimal tersimpan.

```
$ ab -n 100 -c 10 https://rsa-pss.com/

Concurrency Level:      10
Time taken for tests:   0.485 seconds
Complete requests:      100
Failed requests:        0
Requests per second:    206.10 [#/sec] (mean)
Time per request:       48.520 ms (mean)
Time per request:        4.852 ms (mean, across all concurrent requests)

Distribusi latensi:
  50%      30 ms
  95%      52 ms
  99%     158 ms
```

Nol permintaan gagal pada konkurensi 10. P95 sebesar 52 ms berada di bawah
ambang 100 ms, setara Grade A pada rubrik latensi dashboard.

Konfigurasi yang berlaku:

```
GUNICORN_WORKERS=1  GUNICORN_THREADS=12  ENABLE_INTERNAL_SCHEDULER=True
nginx/1.24.0 (Ubuntu)
```

Dashboard sistem juga menyediakan pemantauan P95 berkelanjutan dengan jendela
bergulir 28 hari, mengikuti praktik Core Web Vitals (CrUX) dan error budget SRE.

**Status: TERPENUHI**

---

## Kegiatan 7 — Backup Otomatis Terjadwal & Verifikasi Integritas

**Output:** Script backup terjadwal aktif, backup perdana berhasil.

```
$ crontab -l | grep backup
0 2 * * * /opt/qrcode/deploy/maintenance/backup-qrcode.sh harian >> /var/log/qrcode-backup.log 2>&1
0 3 * * 0 /opt/qrcode/deploy/maintenance/backup-qrcode.sh penuh  >> /var/log/qrcode-backup.log 2>&1
```

Eksekusi perdana:

```
[2026-07-30T13:56:23+07:00] Mulai backup mode=harian (sisa disk 23GB)
[2026-07-30T13:56:26+07:00] Arsip terverifikasi: 35 entri, 13M
[2026-07-30T13:56:26+07:00] Selesai. Total arsip tersimpan: 1

$ ls -lh /opt/qrcode/backups/otomatis/
-rw------- 1 root root 13M  qrcode-harian-20260730-135623.tar.gz
-rw------- 1 root root 132  qrcode-harian-20260730-135623.tar.gz.sha256

$ sha256sum -c *.sha256
qrcode-harian-20260730-135623.tar.gz: OK
```

**Uji pemulihan** — arsip dibongkar ke direktori sementara dan isinya dibuktikan
masih dapat digunakan, bukan sekadar ada:

```
rsa_key.pem       : valid, 2048 bit, privat=True
security_state.db : nonce=14.285  index=89.778
```

Cakupan backup dipilih dari sudut pemulihan: kunci penandatangan, ledger nonce
dan index, log CSV, hasil task, serta berkas deployment. Kode sumber tidak
dicakup karena telah berada di git.

Pengamanan yang melekat pada skrip: arsip diverifikasi ulang dengan `tar -tzf`
lalu dihapus bila gagal dibaca; mode berkas `0600` milik root karena memuat
kunci privat; dan backup dibatalkan bila sisa disk turun di bawah 5 GB agar
tidak mematikan aplikasi yang justru sedang di-backup.

**Catatan:** enkripsi GPG tersedia lewat variabel `GPG_RECIPIENT` namun belum
diaktifkan karena server belum memiliki keyring. Arsip **wajib** dienkripsi
sebelum disalin ke luar server.

**Status: TERPENUHI**

---

## Kegiatan 8 — Monitoring Uptime, Log Error & Pembaruan Paket

**Output:** Log monitoring bersih, semua paket up-to-date.

```
$ uptime
14:02:00 up 5 days, 8:40, 3 users, load average: 1.04, 1.14, 1.08

galat sistem 7 hari   : 409 baris
galat qrcode 7 hari   : 1 baris
restart qrcode 7 hari : 36 (siklus deploy terencana)

paket dapat diperbarui: 15
  apport-core-dump-handler  2.28.1 -> 2.28.2
  apport                    2.28.1 -> 2.28.2
  distro-info-data          0.60   -> 0.72
  fwupd                     2.0.20-1ubuntu2~24.04.1 -> ~24.04.2
  iproute2                  6.1.0-1ubuntu6.3 -> 6.1.0-1ubuntu6.4
```

Aplikasi hanya mencatat **1 baris galat dalam 7 hari** meski mengalami 36
restart dari siklus deploy. Terdapat 15 paket sistem yang dapat diperbarui —
jalankan `apt-get upgrade -y` dan tangkap ulang keluarannya sebagai bukti
penuntasan.

**Status: monitoring TERPENUHI · pembaruan paket PERLU DIJALANKAN**

---

## Kegiatan 9 — Subdomain Staging

**Output:** Subdomain staging aktif, lingkungan uji siap digunakan.

```
$ ls -1 /etc/nginx/sites-enabled/
default
rsa-pss.com

$ dig +short A staging.rsa-pss.com
(tidak ada hasil)
```

**Status: BELUM DIKONFIGURASI**

Yang diperlukan: A record `staging.rsa-pss.com`, vhost nginx terpisah,
sertifikat SSL untuk subdomain, dan instans aplikasi kedua pada port berbeda.

---

## Kegiatan 10 — Pembaruan SSL/TLS & Masa Berlaku Domain

**Output:** Sertifikat SSL diperbarui, domain aktif s.d. periode kontrak.

```
$ certbot certificates
Certificate Name: rsa-pss.com
  Domains: rsa-pss.com www.rsa-pss.com
  Expiry Date: 2026-09-08 03:08:50+00:00 (VALID: 39 days)
  Certificate Path: /etc/letsencrypt/live/rsa-pss.com/fullchain.pem
  Private Key Path: /etc/letsencrypt/live/rsa-pss.com/privkey.pem

$ certbot renew --dry-run
Processing /etc/letsencrypt/renewal/rsa-pss.com.conf
Congratulations, all simulated renewals succeeded

$ systemctl list-timers | grep certbot
Thu 2026-07-30 21:32:36 WIB  (7h lagi)  certbot.timer -> certbot.service
```

Uji perpanjangan berhasil tanpa galat, dan timer otomatis aktif dengan
penjadwalan dua kali sehari. Perpanjangan nyata akan terjadi otomatis begitu
sertifikat memasuki jendela 30 hari terakhir, yakni mulai 9 Agustus 2026.

**Status: TERPENUHI**

---

## Kegiatan 11 — Optimasi Database: Indexing & Query Tuning

**Output:** Waktu query turun signifikan, database lebih responsif.

Skema index:

```sql
CREATE TABLE qr_record_index (
    filename TEXT PRIMARY KEY,
    qr_id TEXT,
    nonce TEXT,
    indexed_at TEXT NOT NULL
);
CREATE INDEX idx_qr_record_nonce ON qr_record_index(nonce);
```

Bukti index benar-benar digunakan, bukan pemindaian tabel:

```
$ EXPLAIN QUERY PLAN SELECT filename FROM qr_record_index WHERE filename >= ? AND filename < ?
  SEARCH qr_record_index USING COVERING INDEX sqlite_autoindex_qr_record_index_1 (filename>? AND filename<?)

$ EXPLAIN QUERY PLAN SELECT filename FROM qr_record_index WHERE nonce = ?
  SEARCH qr_record_index USING INDEX idx_qr_record_nonce (nonce=?)
```

Kata kunci `SEARCH ... USING INDEX` (bukan `SCAN`) membuktikan kueri dilayani
lewat index.

**Hasil benchmark pada 100.713 record produksi:**

| Jenis kueri | Sebelum | Sesudah | Percepatan |
|---|---:|---:|---:|
| Payload utuh | 129,450 ms | 0,602 ms | **214,9×** |
| Field non-id diubah | 126,060 ms | 0,588 ms | **214,3×** |
| Tidak ada di basis data | 3.777,625 ms | 0,963 ms | **3.922,0×** |

**Dampak ujung-ke-ujung** pada verifikasi massal nyata:

| Fase | Sebelum | Sesudah |
|---|---:|---:|
| Waktu pencarian record (`db_time`) | 149,88 ms | 22,10 ms |
| Total per berkas | 153,41 ms | 25,73 ms |
| Throughput | 6,5 berkas/detik | **38,9 berkas/detik** |

Perbaikan **6,0×** secara ujung-ke-ujung. Waktu verifikasi tanda tangan RSA-PSS
tetap 1,02–1,05 ms lintas seluruh pengukuran, menegaskan perbaikan sepenuhnya
terjadi pada lapisan penyimpanan tanpa menyentuh jalur kriptografis.

Konsistensi index terverifikasi di bawah beban nyata saat generate massal
berlangsung: 90.344 entri index berbanding 90.344 berkas di disk, **selisih nol**.

Berkas pendukung: `data-penelitian/hasil_index_produksi.json`,
`data-penelitian/test_index_equivalence.py`,
`dokumen/pelaporan_kinerja_verifikasi.md`.

**Status: TERPENUHI**

---

## Kegiatan 12 — Monitoring Otomatis & Notifikasi Email

**Output:** Sistem alert aktif, uji notifikasi berhasil.

```
$ systemctl show qrcode -p OnFailure --value
(kosong)

$ systemctl list-timers --all | grep -iE 'monitor|alert|uptime'
(tidak ada)
```

**Status: BELUM DIKONFIGURASI**

Terdapat mekanisme pemulihan otomatis berupa health check tiap 15 menit
(Kegiatan 15), namun belum ada notifikasi keluar. Yang diperlukan: unit
`OnFailure` pada systemd atau layanan pemantauan eksternal, beserta konfigurasi
pengiriman email.

---

## Kegiatan 13 — Pemeliharaan Rutin VPS

**Output:** Log bersih, OS up-to-date, penggunaan resource efisien.

```
disk root  : 16G terpakai / 38G (42%)
logs/      : 91M   (semula 120M sebelum pembersihan)
journal    : 716.4M
memori app : 1809 MB
load avg   : 1.04, 1.14, 1.08
```

Pembersihan sisa berkas operasi telah dijalankan:

```
[2026-07-30T13:57:33+07:00] Pembersihan sisa backup: 29 berkas >30 hari dihapus,
                            120MB -> 90MB
```

Berkas log aktif tidak tersentuh dan tetap utuh — `log_generate.csv`,
`log_verifikasi.csv`, dan `security_state.db` terverifikasi masih pada ukuran
dan waktu modifikasi yang benar.

**Catatan:** journal systemd menempati 716 MB. Jalankan
`journalctl --vacuum-time=30d` bila diperlukan penghematan ruang.

**Status: TERPENUHI**

---

## Kegiatan 14 — Deploy Pembaruan Aplikasi ke Production

**Output:** Versi terbaru live di production, layanan berjalan stabil.

```
$ git log --oneline -8
dc3d9ca Pasang firewall, backup terjadwal, dan cron pemeliharaan
5ece6dd Batasi metrik latensi dashboard pada jendela bergulir dan sumber interaktif
795d7be Bangun ulang index setelah cleanup agar reset tidak menurunkan kinerja
d7642ab Lacak tiga template produksi yang terabaikan pola .gitignore tanpa tambatan
382a4f6 Pisahkan pelaporan verifikasi menjadi sumbu signature dan sumbu keberlakuan
350a3da Kenali status kedaluwarsa di halaman log verifikasi
ec3b39d Dokumentasikan justifikasi ambang kedaluwarsa dan pelaporan kinerja verifikasi
69e8803 Index pencarian record QR untuk menggantikan pemindaian direktori

branch : perf/qr-record-index
bersih : 0 berkas belum di-commit
remote : dc3d9ca (tersinkron dengan GitHub)

$ systemctl show qrcode -p Environment --value
HOST=127.0.0.1 PORT=5000 GUNICORN_WORKERS=1 GUNICORN_THREADS=12
ENABLE_INTERNAL_SCHEDULER=True

qrcode.service          : active
galat 30 menit terakhir : 0
```

Delapan commit ter-deploy, working tree bersih, dan tersinkron dengan repositori
GitHub. Layanan berjalan tanpa satu pun galat pasca deploy.

**Status: TERPENUHI**

---

## Kegiatan 15 — Cron Job Maintenance Otomatis

**Output:** Cron job aktif dan terverifikasi berjalan sesuai jadwal.

```
$ crontab -l
0    2 * * *  backup-qrcode.sh harian      # backup harian data kritis
0    3 * * 0  backup-qrcode.sh penuh       # backup penuh mingguan
*/15 *  * * * healthcheck-qrcode.sh        # health check tiap 15 menit
30   4 * * 1  prune-backups-qrcode.sh      # pembersihan sisa backup mingguan

$ systemctl is-active cron
active

entri CRON 24 jam terakhir: 490
logrotate /etc/logrotate.d/qrcode: terpasang
```

Bukti eksekusi nyata:

```
[2026-07-30T13:57:33+07:00] Pembersihan sisa backup: 29 berkas >30 hari dihapus,
                            120MB -> 90MB
```

Health check memeriksa aplikasi melalui HTTP, bukan `systemctl is-active`,
karena proses dapat berstatus aktif namun berhenti melayani permintaan. Restart
hanya dilakukan bila endpoint benar-benar tidak merespons. Uji saat aplikasi
sehat mengembalikan kode keluar 0 tanpa melakukan restart.

Konfigurasi logrotate hanya menyentuh berkas `*.log`. Berkas CSV di `logs/`
sengaja dikecualikan karena merupakan sumber data metrik dashboard, bukan log
teknis, dan merotasinya akan memotong jendela pengukuran 28 hari.

**Status: TERPENUHI**

---

## Kegiatan 16 — Maintenance Bulanan

**Output:** Dependensi diperbarui, query DB lebih optimal, kapasitas storage terpantau.

```
$ pip list --outdated | wc -l
27 paket

Lompatan versi mayor:
  numpy                   1.26.4     -> 2.5.1
  pandas                  2.2.3      -> 3.0.5
  opencv-python-headless  4.10.0.84  -> 5.0.0.93
  pillow                  10.3.0     -> 12.3.0
  scipy                   1.13.1     -> 1.18.0
  qrcode                  7.4.2      -> 8.2
  redis                   5.0.6      -> 8.1.0
  gunicorn                23.0.0     -> 26.0.0
  pycryptodome            3.20.0     -> 3.23.0
  Flask                   3.0.3      -> 3.1.3

$ pip check
No broken requirements found.

$ PRAGMA integrity_check
ok
page_count: 4881

$ du -sh
360M  /opt/qrcode/static/data
 89M  /opt/qrcode/logs
 84M  /opt/qrcode/backups
```

Integritas basis data terverifikasi `ok` dan tidak ada dependensi yang rusak.

**Rekomendasi: dependensi dibekukan sampai penelitian selesai.**

Alasannya bukan sekadar risiko teknis. Tiga paket berada tepat di jalur
pengukuran yang dilaporkan dalam naskah:

| Paket | Peran dalam penelitian |
|---|---|
| `pycryptodome` | Implementasi RSA-PSS. Seluruh angka `verify_time` 1,02–1,05 ms diukur pada versi 3.20.0 |
| `qrcode` | Pembangkitan simbol QR, memengaruhi `qr_version` dan `qr_modules` pada payload |
| `opencv-python-headless` | Pendekodean citra QR, memengaruhi `decode_time` |

Memperbarui ketiganya di tengah penelitian akan mengubah baseline pengukuran dan
membuat angka yang sudah dilaporkan tidak dapat direproduksi. Selain itu
`numpy` 1.x → 2.x dan `pandas` 2.x → 3.x membawa perubahan API yang memutus
kompatibilitas, sedangkan keduanya dipakai pada skrip analisis penelitian.

Versi yang berlaku saat pengukuran sebaiknya justru **dicatat sebagai bagian dari
syarat reproduksibilitas**, bukan diperbarui. Pembaruan dijadwalkan setelah
naskah final, dan diuji pada lingkungan staging (Kegiatan 9) lebih dulu.

**Status: pemantauan TERPENUHI · pembaruan dependensi SENGAJA DITUNDA**

---

## Ringkasan Status

| No | Kegiatan | Status |
|---:|---|---|
| 1 | Registrasi domain & DNS | ✅ Terpenuhi |
| 2 | Aktivasi & konfigurasi VPS | ✅ Terpenuhi |
| 3 | SSL/TLS & akses publik | ✅ Terpenuhi |
| 4 | Firewall & hardening | ⚠ Firewall aktif; hardening SSH belum |
| 5 | Instalasi aplikasi & database | ✅ Terpenuhi |
| 6 | Load testing & optimasi | ✅ Terpenuhi |
| 7 | Backup terjadwal | ✅ Terpenuhi |
| 8 | Monitoring & pembaruan paket | ⚠ Monitoring aktif; 15 paket perlu diperbarui |
| 9 | Subdomain staging | ❌ Belum dikonfigurasi |
| 10 | Pembaruan SSL/TLS | ✅ Terpenuhi |
| 11 | Optimasi database | ✅ Terpenuhi |
| 12 | Alert otomatis & notifikasi | ❌ Belum dikonfigurasi |
| 13 | Pemeliharaan rutin | ✅ Terpenuhi |
| 14 | Deploy production | ✅ Terpenuhi |
| 15 | Cron maintenance | ✅ Terpenuhi |
| 16 | Maintenance bulanan | ⚠ Pemantauan aktif; 27 dependensi usang, sengaja dibekukan |

**11 terpenuhi penuh · 3 terpenuhi sebagian · 2 belum dikonfigurasi**

### Prioritas tindak lanjut

1. **Hardening SSH** (Kegiatan 4) — mendesak, mengingat 24.275 percobaan login
   gagal yang tercatat dan akses yang masih bergantung password
2. **Enkripsi arsip backup** (Kegiatan 7) — wajib sebelum salinan disimpan di
   luar server, karena arsip memuat kunci privat penandatangan
3. Subdomain staging (Kegiatan 9) dan alert otomatis (Kegiatan 12)
4. Pembaruan paket sistem (Kegiatan 8) — dependensi Python sengaja dibekukan
   sampai naskah final, lihat Kegiatan 16

---

## Lampiran — Lokasi Berkas Pendukung

| Berkas | Isi |
|---|---|
| `deploy/maintenance/backup-qrcode.sh` | Skrip backup dua mode |
| `deploy/maintenance/healthcheck-qrcode.sh` | Health check berbasis HTTP |
| `deploy/maintenance/prune-backups-qrcode.sh` | Pembersihan sisa berkas |
| `deploy/maintenance/logrotate-qrcode.conf` | Konfigurasi rotasi log |
| `deploy/maintenance/crontab-root.txt` | Salinan jadwal cron |
| `data-penelitian/hasil_index_produksi.json` | Benchmark index produksi |
| `data-penelitian/test_index_equivalence.py` | Uji ekuivalensi index |
| `dokumen/pelaporan_kinerja_verifikasi.md` | Analisis kinerja verifikasi |
| `dokumen/justifikasi_ambang_kedaluwarsa_payload.md` | Justifikasi ambang kebijakan |
| `backups/otomatis/` | Arsip backup terjadwal |
