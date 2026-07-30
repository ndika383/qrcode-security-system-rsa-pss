# Spesifikasi Bukti Output Logbook Penelitian

Panduan penangkapan bukti output sistem untuk 16 kegiatan logbook periode
Agustus–September 2026.

---

## Catatan Penting Sebelum Digunakan

### 1. Kegiatan bertanggal di masa depan

Seluruh kegiatan bertanggal 4 Agustus – 25 September 2026, sedangkan dokumen ini
disusun 30 Juli 2026. Output tidak dapat dihasilkan tertanggal hari pelaksanaan
sebelum kegiatannya benar-benar dijalankan. Dokumen ini karenanya memuat
**spesifikasi perintah dan bentuk output**, bukan output jadi. Jalankan perintahnya
pada hari pelaksanaan dan simpan keluarannya apa adanya.

Setiap penangkapan sebaiknya diawali penanda waktu agar bukti dapat diaudit:

```bash
date -Is && hostname && whoami
```

### 2. Ketidakcocokan spesifikasi

| Butir logbook | Kondisi server saat ini |
|---|---|
| Domain `.my.id` | Domain aktif adalah `rsa-pss.com`, bukan `.my.id` |
| VPS 2 GB RAM, 4 Core, 40 GB SSD | Terukur: **9,7 GB RAM, 2 Core, 38 GB disk** |
| OS | Ubuntu 24.04.4 LTS |

Bila logbook merujuk VPS/domain yang berbeda dari server ini, bukti harus diambil
dari server yang dimaksud. Bila merujuk server ini, angka pada logbook perlu
disesuaikan dengan hasil pengukuran.

### 3. Butir yang kondisinya belum sesuai pernyataan output

Tiga baris logbook menyatakan hasil yang **belum terpenuhi** pada server ini.
Menangkap bukti hari ini justru akan bertentangan dengan pernyataan tersebut.

| No | Pernyataan output | Kondisi terukur |
|---|---|---|
| 4 | "Firewall aktif, akses root dinonaktifkan" | `ufw` **inactive**; `PermitRootLogin without-password` (masih dapat login via kunci); `PasswordAuthentication yes` |
| 7 | "Script backup terjadwal aktif" | Crontab root kosong; hanya ada dua arsip manual tertanggal 22 Juni 2026 |
| 15 | "Cron job aktif dan terverifikasi" | Crontab root kosong |

Kerjakan konfigurasinya lebih dulu pada tanggal pelaksanaan, baru tangkap
buktinya. Butir 4 khususnya perlu dikerjakan, sebab kondisi sekarang berarti
server berjalan tanpa firewall.

### 4. Dua butir sudah memiliki bukti nyata

Butir **11** (optimasi database: indexing, query tuning) dan **14** (deploy ke
production) sudah dikerjakan pada 29 Juli 2026 dengan bukti terukur yang
terarsip. Rinciannya ada pada bagian masing-masing di bawah.

### 5. Konvensi

Ganti `$DOMAIN` dengan domain yang berlaku. Simpan setiap keluaran sebagai berkas
teks dengan penamaan `bukti_<no>_<tanggal>.txt`, dan lampirkan tangkapan layar
panel penyedia bila kegiatannya di luar server (registrasi domain, aktivasi VPS).

```bash
export DOMAIN=rsa-pss.com
```

---

## 1 — Registrasi domain & konfigurasi DNS (4 Agt, 4 jam)

**Output logbook:** Domain aktif, DNS propagasi OK, URL publik dapat diakses.

```bash
date -Is
whois $DOMAIN | grep -iE 'domain name|creation|expiry|registrar'
dig +short NS $DOMAIN
dig +short A $DOMAIN
dig +short A $DOMAIN @8.8.8.8
dig +short A $DOMAIN @1.1.1.1
```

**Bukti yang ditangkap:** data registrar beserta masa berlaku, daftar nameserver,
dan resolusi A record yang konsisten dari minimal dua resolver publik sebagai
bukti propagasi. Lampirkan tangkapan layar panel DNS Management IDCloudhost.

---

## 2 — Aktivasi & konfigurasi Cloud VPS (6 Agt, 6 jam)

**Output logbook:** VPS aktif, server web & DB berjalan, akses SSH terkonfigurasi.

```bash
date -Is
. /etc/os-release && echo "$PRETTY_NAME"
nproc && free -h && df -h /
systemctl is-active nginx
systemctl is-enabled ssh && ss -tlnp | grep -E ':22|:80|:443'
```

**Bukti:** spesifikasi mesin, status layanan web, dan port yang mendengarkan.

> Catatan: keluaran `nproc`/`free -h` pada server ini adalah 2 core / 9,7 GB,
> berbeda dari 4 Core / 2 GB pada logbook. Sesuaikan salah satunya.

---

## 3 — Penghubungan domain ke VPS, SSL/TLS, uji akses publik (8 Agt, 3 jam)

**Output logbook:** HTTPS aktif, SI dapat diakses via URL publik.

```bash
date -Is
echo "IP publik VPS : $(curl -s ifconfig.me)"
echo "A record      : $(dig +short A $DOMAIN)"
curl -sI https://$DOMAIN | head -5
openssl s_client -connect $DOMAIN:443 -servername $DOMAIN </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
curl -sI http://$DOMAIN | grep -i location
```

**Bukti:** kecocokan IP publik dengan A record, status HTTP 200/302 atas HTTPS,
detail sertifikat, dan pengalihan otomatis HTTP ke HTTPS.

**Status saat ini:** terpenuhi untuk `rsa-pss.com` — sertifikat Let's Encrypt
berlaku sampai 8 September 2026.

---

## 4 — Firewall, hak akses, hardening (11 Agt, 4 jam)

**Output logbook:** Firewall aktif, akses root dinonaktifkan, user admin terkonfigurasi.

**Kerjakan dulu** (kondisi sekarang belum sesuai):

```bash
sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh
```

> Pastikan kunci SSH user non-root sudah berfungsi **sebelum** menonaktifkan
> login root dan autentikasi password, agar tidak terkunci dari server.

**Tangkap bukti:**

```bash
date -Is
sudo ufw status verbose
sudo sshd -T | grep -iE '^permitrootlogin|^passwordauthentication'
getent passwd | awk -F: '$3>=1000 && $3<65534 {print $1,$3}'
sudo lastb 2>/dev/null | head -5
```

---

## 5 — Instalasi aplikasi SI, uji koneksi DB & endpoint API (13 Agt, 4 jam)

**Output logbook:** Aplikasi SI berhasil diinstall dan terkoneksi ke database.

```bash
date -Is
systemctl status qrcode --no-pager | head -12
curl -s -o /dev/null -w 'Beranda   : HTTP %{http_code} dalam %{time_total}s\n' https://$DOMAIN/
curl -s -o /dev/null -w 'Login     : HTTP %{http_code}\n' https://$DOMAIN/login
sudo sqlite3 /opt/qrcode/logs/security_state.db '.tables'
sudo sqlite3 /opt/qrcode/logs/security_state.db \
  'SELECT COUNT(*) AS nonce_state FROM nonce_state;'
```

**Bukti:** status unit systemd, kode respons endpoint, dan pembuktian koneksi
basis data lewat pembacaan tabel nyata.

---

## 6 — Load testing & optimasi web server (18 Agt, 4 jam)

**Output logbook:** Laporan uji performa, konfigurasi optimal tersimpan.

```bash
date -Is
sudo apt-get install -y apache2-utils
ab -n 500 -c 20 https://$DOMAIN/ | grep -E 'Requests per second|Time per request|Failed|Percentage|50%|95%|99%'
nginx -T 2>/dev/null | grep -E 'worker_processes|worker_connections|keepalive_timeout|gzip'
systemctl show qrcode -p Environment
```

**Bukti:** throughput, distribusi persentil latensi, jumlah permintaan gagal, dan
parameter nginx serta worker Gunicorn yang berlaku.

**Bukti pendukung tambahan:** dashboard sistem menyediakan metrik P95 latensi
dengan jendela bergulir 28 hari dan pemisahan sumber interaktif. Sertakan
tangkapan layar panel *P95 Response Time Grade* sebagai pelengkap.

---

## 7 — Backup otomatis terjadwal & verifikasi integritas (20 Agt, 3 jam)

**Output logbook:** Script backup terjadwal aktif, backup perdana berhasil.

**Kerjakan dulu** — crontab root saat ini kosong. Contoh penjadwalan harian:

```bash
sudo crontab -e
# 0 2 * * * /opt/qrcode/backup-sistem/backup.sh >> /var/log/backup-qrcode.log 2>&1
```

**Tangkap bukti:**

```bash
date -Is
sudo crontab -l | grep -v '^#'
ls -lh /opt/qrcode/backup-sistem/
sha256sum /opt/qrcode/backup-sistem/*.tar.gz
tar -tzf /opt/qrcode/backup-sistem/<berkas>.tar.gz | head -20
```

**Bukti:** entri cron aktif, arsip backup beserta ukuran dan waktunya, checksum
SHA-256 sebagai bukti integritas, dan daftar isi arsip sebagai bukti arsip tidak
korup. Untuk backup terenkripsi GPG, tambahkan `gpg --list-packets` guna
membuktikan enkripsi tanpa membuka isinya.

---

## 8 — Monitoring uptime, log error, pembaruan paket (25 Agt, 3 jam)

**Output logbook:** Log monitoring bersih, semua paket up-to-date.

```bash
date -Is
uptime -p && uptime
sudo journalctl -p err --since "-7 days" --no-pager | tail -20
sudo journalctl -u qrcode -p err --since "-7 days" --no-pager | wc -l
sudo apt-get update -qq && apt list --upgradable 2>/dev/null
sudo apt-get upgrade -y
```

**Bukti:** lama uptime, cacah galat sistem dan aplikasi selama sepekan, daftar
paket yang dapat diperbarui sebelum dan sesudah pembaruan.

---

## 9 — Subdomain staging (27 Agt, 4 jam)

**Output logbook:** Subdomain staging aktif, lingkungan uji siap digunakan.

```bash
date -Is
dig +short A staging.$DOMAIN
sudo ls -l /etc/nginx/sites-enabled/
sudo nginx -t
curl -sI https://staging.$DOMAIN | head -3
sudo certbot certificates | grep -A3 staging
```

**Bukti:** resolusi DNS subdomain, berkas vhost nginx, hasil uji konfigurasi,
respons HTTPS, dan sertifikat subdomain.

**Status saat ini:** belum ada vhost staging; hanya `default` dan `rsa-pss.com`.

---

## 10 — Pembaruan SSL/TLS & pengecekan masa berlaku domain (1 Sep, 3 jam)

**Output logbook:** Sertifikat SSL diperbarui, domain aktif s.d. periode kontrak.

```bash
date -Is
sudo certbot certificates
sudo certbot renew --dry-run
sudo systemctl list-timers | grep -i certbot
whois $DOMAIN | grep -iE 'expiry|expiration'
```

**Bukti:** masa berlaku sertifikat sebelum dan sesudah pembaruan, keberhasilan
uji perpanjangan, timer perpanjangan otomatis, dan masa berlaku registrasi domain.

**Catatan waktu:** sertifikat `rsa-pss.com` berlaku sampai **8 September 2026**.
Jadwal 1 September berada dalam jendela perpanjangan Let's Encrypt (30 hari
terakhir), sehingga `certbot renew` akan benar-benar memperbarui — waktunya tepat.

---

## 11 — Optimasi database: indexing, query tuning, pembersihan log (3 Sep, 3 jam)

**Output logbook:** Waktu query turun signifikan, database lebih responsif.

**Bukti nyata sudah tersedia.** Pekerjaan ini dilaksanakan 29 Juli 2026:
penggantian pemindaian direktori O(n) dengan index `qr_record_index` pada SQLite.

```bash
date -Is
sudo sqlite3 /opt/qrcode/logs/security_state.db '.schema qr_record_index'
sudo sqlite3 /opt/qrcode/logs/security_state.db \
  'EXPLAIN QUERY PLAN SELECT filename FROM qr_record_index WHERE filename >= ? AND filename < ?;'
sudo sqlite3 /opt/qrcode/logs/security_state.db 'SELECT COUNT(*) FROM qr_record_index;'
cat /opt/qrcode/data-penelitian/hasil_index_produksi.json
```

**Hasil terukur pada 100.713 record produksi:**

| Jenis kueri | Sebelum | Sesudah | Percepatan |
|---|---:|---:|---:|
| Payload utuh | 129,450 ms | 0,602 ms | 215× |
| Field non-id diubah | 126,060 ms | 0,588 ms | 214× |
| Tidak ada di basis data | 3.777,625 ms | 0,963 ms | 3.922× |

Dampak ujung-ke-ujung: waktu per berkas 153,41 ms → 25,73 ms; throughput
6,5 → 38,9 berkas/detik.

Berkas pendukung: `data-penelitian/hasil_index_produksi.json`,
`data-penelitian/test_index_equivalence.py`, dan
`dokumen/pelaporan_kinerja_verifikasi.md`.

---

## 12 — Monitoring otomatis & notifikasi email (8 Sep, 4 jam)

**Output logbook:** Sistem alert aktif, uji notifikasi berhasil.

**Kerjakan dulu** — belum ada mekanisme alert. Contoh dengan systemd `OnFailure`:

```bash
sudo systemctl edit qrcode
# [Unit]
# OnFailure=notify-admin@%n.service
```

**Tangkap bukti:**

```bash
date -Is
systemctl show qrcode -p OnFailure
sudo systemctl list-timers --all | head
sudo systemctl start notify-admin@test.service
sudo journalctl -u notify-admin@test --no-pager | tail -10
```

**Bukti:** konfigurasi pemicu, daftar timer, dan log pengiriman notifikasi uji.
Lampirkan tangkapan layar email yang diterima.

---

## 13 — Pemeliharaan rutin VPS (10 Sep, 4 jam)

**Output logbook:** Log bersih, OS up-to-date, penggunaan resource efisien.

```bash
date -Is
df -h / && sudo du -sh /var/log
sudo journalctl --disk-usage
sudo journalctl --vacuum-time=30d
sudo apt-get update -qq && sudo apt-get upgrade -y && sudo apt-get autoremove -y
systemctl show qrcode -p MemoryCurrent -p CPUUsageNSec
free -h && top -bn1 | head -5
```

**Bukti:** penggunaan disk sebelum dan sesudah pembersihan log, hasil pembaruan
OS, serta konsumsi memori dan CPU layanan aplikasi.

---

## 14 — Deploy pembaruan aplikasi ke production (15 Sep, 5 jam)

**Output logbook:** Versi terbaru live di production, layanan berjalan stabil.

```bash
date -Is
cd /opt/qrcode && git log --oneline -5 && git status --short
systemctl show qrcode -p Environment
sudo systemctl restart qrcode && sleep 4
systemctl is-active qrcode
curl -s -o /dev/null -w 'HTTP %{http_code} dalam %{time_total}s\n' https://$DOMAIN/
sudo journalctl -u qrcode --since "-5 min" --no-pager | grep -icE 'error|traceback'
```

**Bukti:** commit yang ter-deploy, variabel lingkungan, status layanan pasca
restart, respons endpoint, dan cacah galat pasca deploy (idealnya nol).

**Bukti nyata sudah tersedia.** Deploy dilaksanakan 29 Juli 2026 sebanyak
beberapa siklus, menghasilkan 7 commit pada branch `perf/qr-record-index` dengan
layanan sehat dan nol galat pada journal setiap kali.

---

## 15 — Cron job maintenance otomatis (22 Sep, 3 jam)

**Output logbook:** Cron job aktif dan terverifikasi berjalan sesuai jadwal.

**Kerjakan dulu** — crontab root kosong. Contoh:

```bash
sudo crontab -e
# 0 3 * * * /usr/sbin/logrotate -f /etc/logrotate.d/qrcode
# */30 * * * * curl -sf https://rsa-pss.com/ >/dev/null || systemctl restart qrcode
```

**Tangkap bukti:**

```bash
date -Is
sudo crontab -l | grep -v '^#'
sudo logrotate -d /etc/logrotate.d/qrcode 2>&1 | head -20
sudo journalctl -u cron --since "-24 hours" --no-pager | tail -15
ls -lh /opt/qrcode/logs/
```

**Bukti:** daftar cron aktif, simulasi rotasi log, log eksekusi cron dalam 24 jam
sebagai bukti benar-benar berjalan, dan kondisi berkas log setelah rotasi.

> Catatan: aplikasi juga memiliki penjadwal internal
> (`ENABLE_INTERNAL_SCHEDULER=True`) yang menjalankan pembersihan berkas lama
> setiap 24 jam. Sertakan `systemctl show qrcode -p Environment` sebagai
> pelengkap.

---

## 16 — Maintenance bulanan: dependensi, database, storage (25 Sep, 4 jam)

**Output logbook:** Dependensi diperbarui, query DB lebih optimal, kapasitas storage terpantau.

```bash
date -Is
/opt/qrcode/venv/bin/pip list --outdated
/opt/qrcode/venv/bin/pip check
sudo sqlite3 /opt/qrcode/logs/security_state.db 'PRAGMA integrity_check;'
sudo sqlite3 /opt/qrcode/logs/security_state.db 'VACUUM; ANALYZE;'
df -h / && sudo du -sh /opt/qrcode/static/data /opt/qrcode/logs /opt/qrcode/backups
find /opt/qrcode/static/data -name '*.json' | wc -l
```

**Bukti:** daftar dependensi usang beserta hasil pemeriksaan konsistensi,
pemeriksaan integritas basis data, hasil VACUUM/ANALYZE, dan pemantauan kapasitas
per direktori.

---

## Ringkasan Status

| No | Kegiatan | Status terhadap server saat ini |
|---:|---|---|
| 1 | Domain & DNS | Aktif, tetapi `rsa-pss.com`, bukan `.my.id` |
| 2 | Aktivasi VPS | Aktif; spesifikasi berbeda dari logbook |
| 3 | SSL/TLS & akses publik | **Terpenuhi** |
| 4 | Firewall & hardening | **Belum** — ufw inactive, root masih dapat login |
| 5 | Instalasi aplikasi | **Terpenuhi** |
| 6 | Load testing | Perlu dijalankan |
| 7 | Backup terjadwal | **Belum** — crontab kosong |
| 8 | Monitoring & update paket | Perlu dijalankan |
| 9 | Subdomain staging | **Belum ada** |
| 10 | Pembaruan SSL | Terjadwal tepat (kedaluwarsa 8 Sep) |
| 11 | Optimasi database | **Sudah, dengan bukti terukur** |
| 12 | Alert otomatis | **Belum ada** |
| 13 | Pemeliharaan rutin | Perlu dijalankan |
| 14 | Deploy production | **Sudah, dengan bukti terukur** |
| 15 | Cron maintenance | **Belum** — crontab kosong |
| 16 | Maintenance bulanan | Perlu dijalankan |
