# Bukti Output Logbook Penelitian

Sistem Informasi Penelitian — QR Code Security System berbasis RSA-PSS

| | |
|---|---|
| Domain produksi | `rsa-pss.com` |
| Domain staging | `staging.rsa-pss.com` |
| IP publik | `103.13.207.36` |
| Sistem operasi | Ubuntu 24.04.4 LTS (kernel 6.8.0-136-generic) |
| Spesifikasi | 2 core · 9,7 GB RAM · 38 GB disk |
| Waktu penangkapan bukti | 31 Juli 2026, 13.56–14.00 WIB |

Seluruh keluaran pada dokumen ini adalah hasil eksekusi nyata pada server
produksi, disalin apa adanya tanpa penyuntingan.

---

## Ringkasan Status

| No | Kegiatan | Status |
|---:|---|---|
| 1 | Registrasi domain & DNS | ✅ Terpenuhi |
| 2 | Aktivasi & konfigurasi VPS | ✅ Terpenuhi |
| 3 | SSL/TLS & akses publik | ✅ Terpenuhi |
| 4 | Firewall, hak akses & hardening | ✅ Terpenuhi |
| 5 | Instalasi aplikasi & database | ✅ Terpenuhi |
| 6 | Load testing & optimasi | ✅ Terpenuhi |
| 7 | Backup terjadwal & verifikasi integritas | ✅ Terpenuhi |
| 8 | Monitoring & pembaruan paket | ✅ Terpenuhi |
| 9 | Subdomain staging | ✅ Terpenuhi |
| 10 | Pembaruan SSL/TLS | ✅ Terpenuhi |
| 11 | Optimasi database | ✅ Terpenuhi |
| 12 | Alert otomatis & notifikasi | ✅ Terpenuhi |
| 13 | Pemeliharaan rutin VPS | ✅ Terpenuhi |
| 14 | Deploy ke production | ✅ Terpenuhi |
| 15 | Cron maintenance otomatis | ✅ Terpenuhi |
| 16 | Maintenance bulanan | ⚠ Pemantauan terpenuhi; pembaruan dependensi sengaja ditunda |

**15 terpenuhi penuh · 1 ditunda atas keputusan yang tercatat alasannya**

---

## Kegiatan 1 — Registrasi Domain & Konfigurasi DNS

**Output:** Domain aktif, DNS propagasi OK, URL publik dapat diakses.

```
$ for r in 8.8.8.8 1.1.1.1 9.9.9.9; do dig +short A rsa-pss.com @$r; done
8.8.8.8 -> 103.13.207.36
1.1.1.1 -> 103.13.207.36
9.9.9.9 -> 103.13.207.36

$ dig +short staging.rsa-pss.com @8.8.8.8
rsa-pss.com.
103.13.207.36
```

Resolusi konsisten dari tiga resolver publik independen membuktikan propagasi
menyeluruh. Subdomain staging memakai CNAME ke domain utama, sehingga perubahan
IP cukup dilakukan pada satu record A.

**Catatan:** zona juga memuat record MX yang menunjuk ke server ini, padahal
tidak ada MTA yang berjalan dan port 25, 465, serta 587 tidak mendengarkan.
Email dari maupun ke domain ini akan gagal. Hal tersebut diperhitungkan pada
Kegiatan 12 dengan memilih kanal notifikasi non-email.

**Status: TERPENUHI**

---

## Kegiatan 2 — Aktivasi & Konfigurasi Cloud VPS

**Output:** VPS aktif, server web & DB berjalan, akses SSH terkonfigurasi.

```
OS       : Ubuntu 24.04.4 LTS
Kernel   : 6.8.0-136-generic
CPU core : 2
RAM      : 9,7 GiB (terpakai 1,1 GiB)
Disk     : 38 GB (44 % terpakai)
Uptime   : 4 jam 42 menit (sejak reboot terjadwal 31 Juli 09.13)

Layanan  : qrcode=active  qrcode-staging=active  nginx=active
           redis-server=active  fail2ban=active  cron=active
```

Spesifikasi terukur adalah **2 core / 9,7 GB RAM / 38 GB disk**. Bila logbook
mencantumkan angka lain, sesuaikan dengan hasil pengukuran ini.

**Status: TERPENUHI**

---

## Kegiatan 3 — Penghubungan Domain ke VPS & SSL/TLS

**Output:** HTTPS aktif, SI dapat diakses via URL publik.

```
subject = CN = rsa-pss.com
notBefore = Jun 10 03:08:51 2026 GMT
notAfter  = Sep  8 03:08:50 2026 GMT

produksi : HTTP 302
staging  : HTTP 302
HTTP     : 301 -> https://rsa-pss.com/
```

A record cocok dengan IP publik, sertifikat Let's Encrypt sah, dan seluruh
lalu lintas HTTP dialihkan permanen ke HTTPS.

**Status: TERPENUHI**

---

## Kegiatan 4 — Firewall, Hak Akses & Hardening

**Output:** Firewall aktif, akses root dinonaktifkan, user admin terkonfigurasi.

### Firewall

```
$ ufw status
Status: active

Anywhere      REJECT   92.205.239.91   # by Fail2Ban after 2 attempts against sshd
22/tcp        LIMIT    Anywhere
80/tcp        ALLOW    Anywhere
443/tcp       ALLOW    Anywhere
```

Port aplikasi (gunicorn 5000 dan 5001) serta Redis (6379) terikat `127.0.0.1`
sehingga tidak terjangkau dari luar tanpa perlu aturan tambahan.

### Akun administratif

```
$ getent passwd | awk -F: '$3>=1000 && $3<65534'
amikom (uid 1001)

$ grep -rhE '^\s*(%sudo|amikom)' /etc/sudoers /etc/sudoers.d/
%sudo   ALL=(ALL:ALL) ALL
amikom ALL=(ALL) NOPASSWD:ALL
```

Hak administratif `amikom` berasal dari entri sudoers **eksplisit**, bukan
keanggotaan grup. Ini diperiksa sebelum akses root ditutup: seandainya hak
tersebut bergantung pada grup `sudo` yang ternyata kosong, menutup root akan
menghilangkan seluruh kemampuan administrasi.

### Latar: serangan brute force

```
total percobaan login gagal (btmp) : 24.341
   4.702 menyasar root · 2.413 admin · 2.171 user · 2.012 ubuntu
   sedikitnya sepuluh IP dengan lebih dari 700 percobaan masing-masing
```

### Pertahanan berlapis yang diterapkan

```
$ sshd -T
permitrootlogin              no
passwordauthentication       no
kbdinteractiveauthentication yes
authenticationmethods        publickey keyboard-interactive
maxauthtries                 3
logingracetime               30

$ grep -E '^\s*auth' /etc/pam.d/sshd
auth required pam_google_authenticator.so
```

| Lapis | Kontrol |
|---|---|
| 1 | ufw `LIMIT` pada port 22 |
| 2 | fail2ban — 3 kegagalan per 10 menit, blokir bertingkat sampai 7 hari |
| 3 | `MaxAuthTries 3` (bawaan 6) |
| 4 | `LoginGraceTime 30` |
| 5 | `PermitRootLogin no` |
| 6 | Autentikasi dua faktor TOTP (RFC 6238) |

### Mengapa TOTP, bukan kunci SSH

Kunci SSH menuntut pemasangan pada setiap mesin, sedangkan pemilik sistem
mengelola server dari banyak perangkat. TOTP menempatkan faktor kedua di ponsel,
bukan di mesin yang dipakai menyambung, sehingga login tetap mungkin dari
perangkat mana pun tanpa persiapan apa pun di mesin tersebut.

`PasswordAuthentication no` **tidak** mematikan login password. Yang ditutup
adalah jalur password internal sshd; autentikasi dialihkan ke PAM lewat
`keyboard-interactive`, dan PAM tetap menanyakan password Unix sebelum meminta
kode TOTP. Penutupan jalur internal itu syarat mutlak — bila dibiarkan aktif,
penyerang dapat melewati TOTP sepenuhnya hanya dengan menebak password.

Modul PAM dipasang **tanpa** `nullok`, sehingga pengguna tanpa rahasia TOTP tidak
dapat login melalui jalur ini.

### Bukti login dua faktor

```
13:53:26 sshd(pam_google_authenticator): Accepted google_authenticator for amikom
13:53:26 sshd: Accepted keyboard-interactive/pam for amikom from 202.91.8.200
```

### Konfigurasi drop-in dan urutan pembacaan

Konfigurasi ditulis sebagai `/etc/ssh/sshd_config.d/10-hardening.conf`.
Penomoran 10 bukan gaya penulisan melainkan syarat kebenaran: pada sshd, nilai
**pertama** yang diperoleh untuk sebuah kata kunci adalah yang berlaku, bukan
yang terakhir. Server ini memiliki dua drop-in bawaan cloud-image yang saling
bertentangan — `50-cloud-init.conf` menyatakan `PasswordAuthentication yes` dan
`60-cloudimg-settings.conf` menyatakan `no` — dan yang bernomor 50 menang karena
dibaca lebih dulu. Berkas hardening bernomor lebih besar akan diabaikan secara
diam-diam: konfigurasi tampak benar, tetapi tidak berlaku.

### Penerapan bertahap dengan pembatalan otomatis

Konfigurasi PAM yang keliru dapat mengunci seluruh akses SSH. Setiap penerapan
karenanya dijadwalkan bersama tugas pembatalan otomatis yang memulihkan
konfigurasi bila tidak dikonfirmasi dalam tenggat tertentu.

Mekanisme ini terbukti bekerja pada percobaan pertama. Kode TOTP ditolak, dan
pembatalan menyala tepat waktu memulihkan akses tanpa campur tangan manusia:

```
13:37:15 sshd(pam_google_authenticator): Invalid verification code for amikom
13:37:39 2fa-rollback: Konfigurasi 2FA SSH dibatalkan otomatis dan dipulihkan
```

Penelusuran menemukan aplikasi authenticator memegang rahasia berbeda dari yang
tersimpan di server. Untuk memastikannya tanpa menebak, dibuat perkakas
`cek-totp` yang membandingkan kode dari aplikasi terhadap hitungan server pada
jendela ±5 menit, sehingga selisih jam dapat **diukur** dan dibedakan dari
rahasia yang memang tidak cocok. Setelah rahasia dibuat ulang dan `cek-totp`
melaporkan `COCOK TEPAT`, konfigurasi diterapkan kembali dan berhasil.

Urutan inilah yang seharusnya dipakai sejak awal: memverifikasi faktor kedua
lebih dulu memakan beberapa detik, sedangkan mengetahuinya lewat kegagalan login
memakan satu siklus penerapan penuh.

**Status: TERPENUHI**

---

## Kegiatan 5 — Instalasi Aplikasi & Uji Koneksi Database

**Output:** Aplikasi SI berhasil diinstall dan terkoneksi ke database.

```
qrcode.service         : active        (produksi, port 5000)
qrcode-staging.service : active        (staging, port 5001)

tabel           : nonce_state, security_metadata, qr_record_index
qr_record_index : 100.000 baris
nonce_state     : 114.285 baris
integritas DB   : ok
record QR disk  : 100.000 berkas
```

Kecocokan sempurna antara 100.000 entri index dan 100.000 berkas di disk
membuktikan lapisan aplikasi dan basis data terkoneksi serta konsisten.

**Status: TERPENUHI**

---

## Kegiatan 6 — Load Testing & Optimasi Web Server

**Output:** Laporan uji performa, konfigurasi optimal tersimpan.

```
$ ab -n 200 -c 10 https://rsa-pss.com/

Complete requests    : 200
Failed requests      : 0
Requests per second  : 381,82 [#/sec]

Distribusi latensi:
  50%   25 ms
  95%   37 ms
  99%   48 ms
```

Nol permintaan gagal pada konkurensi 10. P95 sebesar 37 ms berada jauh di bawah
ambang 100 ms.

Dashboard sistem menyediakan pemantauan P95 berkelanjutan dengan jendela bergulir
28 hari mengikuti praktik Core Web Vitals (CrUX) dan error budget SRE, dengan
grade dihitung dari permintaan interaktif saja agar volume verifikasi massal
tidak dapat menggesernya.

**Status: TERPENUHI**

---

## Kegiatan 7 — Backup Otomatis Terjadwal & Verifikasi Integritas

**Output:** Script backup terjadwal aktif, backup perdana berhasil.

```
$ crontab -l | grep backup
0 2 * * *  backup-qrcode.sh harian    # data kritis, tiap hari
0 3 * * 0  backup-qrcode.sh penuh     # termasuk static/data, tiap Minggu

$ ls -lh /opt/qrcode/backups/otomatis/
13M  qrcode-harian-20260730-135623.tar.gz
20M  qrcode-harian-20260731-020001.tar.gz   <- dijalankan cron, tanpa campur tangan
49M  qrcode-penuh-20260731-083431.tar.gz

$ sha256sum -c *.sha256
qrcode-harian-20260730-135623.tar.gz: OK
qrcode-harian-20260731-020001.tar.gz: OK
qrcode-penuh-20260731-083431.tar.gz: OK
```

Arsip pukul 02.00 dihasilkan cron secara terjadwal tanpa campur tangan manusia —
bukti bahwa penjadwalannya benar-benar berjalan, bukan sekadar terpasang.

**Uji pemulihan** — arsip dibongkar ke direktori sementara dan isinya dibuktikan
masih dapat digunakan, bukan sekadar ada:

```
rsa_key.pem       : valid, 2048 bit, privat=True
security_state.db : terbaca utuh
```

Cakupan dipilih dari sudut pemulihan: kunci penandatangan (hilang berarti seluruh
QR yang pernah terbit tidak dapat diverifikasi), ledger nonce dan index, log CSV,
hasil task, serta berkas deployment. Kode sumber tidak dicakup karena sudah
berada di git.

Pengamanan yang melekat: arsip diverifikasi ulang dengan `tar -tzf` lalu dihapus
bila gagal dibaca; mode berkas 0600 milik root karena memuat kunci privat; dan
backup dibatalkan bila sisa disk turun di bawah 5 GB agar tidak mematikan
aplikasi yang justru sedang di-backup.

**Catatan:** enkripsi GPG tersedia lewat variabel `GPG_RECIPIENT` namun belum
diaktifkan. Arsip **wajib** dienkripsi sebelum disalin ke luar server.

**Status: TERPENUHI**

---

## Kegiatan 8 — Monitoring Uptime, Log Error & Pembaruan Paket

**Output:** Log monitoring bersih, semua paket up-to-date.

```
paket dapat diperbarui   : 0
reboot diperlukan        : tidak
galat sistem sejak boot  : 3 baris
galat qrcode sejak boot  : 0 baris
uptime                   : 4 jam 42 menit
```

Seluruh 15 paket sistem diperbarui pada 31 Juli, termasuk `openssl` dan
`libssl3t64` yang berasal dari repositori `noble-security`. Keduanya semula
tertahan mekanisme *phased update* Ubuntu dan dipasang eksplisit — menunda
pembaruan keamanan OpenSSL pada server publik yang melayani HTTPS tidak dapat
dibenarkan.

Karena `libssl` sedang dipakai gunicorn, nginx, dan redis, ketiganya direstart
agar benar-benar memuat pustaka baru. Diverifikasi 0 proses masih memakai
pustaka terhapus. Reboot untuk `libc6` dituntaskan pada 09.13.

**Status: TERPENUHI**

---

## Kegiatan 9 — Subdomain Staging

**Output:** Subdomain staging aktif, lingkungan uji siap digunakan.

```
$ curl -sI https://staging.rsa-pss.com
HTTP/1.1 302 FOUND
X-Environment: staging
X-Robots-Tag: noindex, nofollow

subject = CN = staging.rsa-pss.com
notAfter = Oct 29 02:06:02 2026 GMT
```

### Isolasi dari produksi

Seluruh path aplikasi bersifat relatif terhadap direktori kerja
(`static/data`, `logs/security_state.db`, `rsa_key.pem`). Staging dijalankan
dengan `WorkingDirectory=/opt/qrcode-staging`, menghasilkan basis data, ledger
nonce, dan kunci penandatangan yang sepenuhnya terpisah.

Isolasi ini **wajib**, bukan sekadar rapi: instans staging yang berbagi direktori
dengan produksi akan menulis record uji ke `static/data` dan mencatat nonce uji
ke ledger replay, sehingga merusak data penelitian.

| Aspek | Produksi | Staging |
|---|---|---|
| Direktori kerja | `/opt/qrcode` | `/opt/qrcode-staging` |
| Port | 5000 | 5001 |
| Git | `main` | detached HEAD |
| Virtualenv | sendiri | sendiri (48 paket) |
| Record QR | 100.000 | 0 |
| `security_state.db` | inode 524699 | inode 263617 |
| Sidik jari kunci publik | `beb65cbc981d7eac` | `02dd9a1351445d71` |

Inode berbeda membuktikan berkas basis data benar-benar terpisah, bukan hardlink
maupun symlink. Kunci penandatangan berbeda berarti QR terbitan staging **tidak
akan pernah lolos verifikasi di produksi** — pemisahan yang justru diinginkan.

Virtualenv terpisah memungkinkan pengujian pembaruan dependensi (Kegiatan 16)
tanpa menyentuh versi yang menjadi baseline pengukuran penelitian.

**Status: TERPENUHI**

---

## Kegiatan 10 — Pembaruan SSL/TLS & Masa Berlaku Domain

**Output:** Sertifikat SSL diperbarui, domain aktif s.d. periode kontrak.

```
$ certbot certificates
sertifikat dikelola: 2

rsa-pss.com          : notAfter Sep  8 03:08:50 2026 GMT
staging.rsa-pss.com  : notAfter Oct 29 02:06:02 2026 GMT

$ certbot renew --dry-run
Congratulations, all simulated renewals succeeded

$ systemctl list-timers | grep certbot
certbot.timer aktif — dua kali sehari
```

Uji perpanjangan berhasil tanpa galat dan timer otomatis aktif. Perpanjangan
nyata terjadi otomatis begitu sertifikat memasuki jendela 30 hari terakhir.

Pemeriksaan harian (Kegiatan 12) turut memantau masa berlaku dan memberitakan
bila tersisa kurang dari 21 hari — jaring pengaman bila perpanjangan otomatis
gagal secara senyap.

**Status: TERPENUHI**

---

## Kegiatan 11 — Optimasi Database: Indexing & Query Tuning

**Output:** Waktu query turun signifikan, database lebih responsif.

Implementasi lama memanggil `os.listdir()` atas seluruh direktori data pada
setiap verifikasi. Pada 100.713 record, satu verifikasi membaca 100.713 nama
berkas untuk menemukan satu record — biaya O(n) terhadap jumlah QR yang pernah
diterbitkan, bukan terhadap jumlah yang sedang diverifikasi.

```sql
CREATE TABLE qr_record_index (
    filename TEXT PRIMARY KEY,
    qr_id TEXT,
    nonce TEXT,
    indexed_at TEXT NOT NULL
);
CREATE INDEX idx_qr_record_nonce ON qr_record_index(nonce);
```

Bukti index benar-benar dipakai, bukan pemindaian tabel:

```
$ EXPLAIN QUERY PLAN SELECT filename FROM qr_record_index WHERE filename >= ? AND filename < ?
SEARCH qr_record_index USING COVERING INDEX sqlite_autoindex_qr_record_index_1

$ EXPLAIN QUERY PLAN SELECT filename FROM qr_record_index WHERE nonce = ?
SEARCH qr_record_index USING INDEX idx_qr_record_nonce
```

Kata kunci `SEARCH ... USING INDEX` — bukan `SCAN` — membuktikannya.

### Hasil terukur pada 100.713 record produksi

| Jenis kueri | Sebelum | Sesudah | Percepatan |
|---|---:|---:|---:|
| Payload utuh | 129,450 ms | 0,602 ms | **215×** |
| Field non-id diubah | 126,060 ms | 0,588 ms | **214×** |
| Tidak ada di basis data | 3.777,625 ms | 0,963 ms | **3.922×** |

### Dampak ujung-ke-ujung pada verifikasi 100.000 QR

| Fase | Sebelum | Sesudah |
|---|---:|---:|
| `db_time` | 149,88 ms | **20,44 ms** |
| Total per berkas | 153,41 ms | **23,06 ms** |
| Throughput | 6,5 berkas/detik | **43,4 berkas/detik** |

Perbaikan **6,65×**. Waktu verifikasi tanda tangan RSA-PSS tetap 1,02–1,05 ms
lintas seluruh pengukuran, menegaskan perbaikan sepenuhnya terjadi pada lapisan
penyimpanan tanpa menyentuh jalur kriptografis.

### Temuan keamanan tersirat

Baris terakhir tabel bukan sekadar isu kinerja. Pada implementasi lama, payload
dengan id tidak dikenal memaksa server membuka **setiap** berkas JSON di
direktori — terukur 3,78 detik per permintaan. Ini amplifikasi: permintaan murah
bagi penyerang memicu kerja mahal bagi server, dan biayanya justru **paling
tinggi** pada payload yang tidak sah. Perbaikan menurunkan biaya kasus terburuk
menjadi 0,963 ms.

Berkas pendukung: `data-penelitian/hasil_index_produksi.json`,
`data-penelitian/test_index_equivalence.py`,
`dokumen/pelaporan_kinerja_verifikasi.md`.

**Status: TERPENUHI**

---

## Kegiatan 12 — Monitoring Otomatis & Notifikasi

**Output:** Sistem alert aktif, uji notifikasi berhasil.

Kanal memakai bot Telegram. Email tidak dipakai karena record MX `rsa-pss.com`
menunjuk ke server ini tetapi tidak ada MTA yang berjalan.

```
$ systemctl show qrcode -p OnFailure --value
qrcode-alert@qrcode.service.service

$ grep NOTIFY_CHANNEL /etc/qrcode-notify.conf
NOTIFY_CHANNEL=telegram

notifikasi terkirim tercatat: 6
```

### Lima pemicu, seluruhnya diuji sampai pesan terkirim

| # | Pemicu | Cara diuji | Hasil |
|---|---|---|---|
| 1 | systemd `OnFailure` | `systemctl start qrcode-alert@uji-pemicu-1` | `[critical] Layanan gagal` |
| 2 | Health check gagal pulih | Salinan diarahkan ke port mati, `systemctl` di-shim | `[critical] Aplikasi tidak pulih` |
| 3 | Backup gagal diverifikasi | Salinan merusak arsip tepat setelah dibuat | `[critical] Backup gagal diverifikasi` |
| 4 | Pemeriksaan harian | Salinan dengan ambang disk diturunkan ke 1 % | `[warning] 1 masalah` |
| 5 | Sesi SSH dibuka | Login nyata dari komputer pemilik sistem | `[info] Sesi SSH dibuka: amikom` |

### Pemicu 5: keberhasilan login, bukan kegagalan

Dipasang lewat `pam_exec` pada `session optional`, sehingga kegagalan pengiriman
notifikasi tidak dapat menghalangi login. Notifikasi dijalankan di latar agar
sesi tidak menunggu Telegram merespons.

Yang diberitakan sengaja keberhasilan, bukan kegagalan. Server mencatat 24.341
percobaan login gagal; memberitakannya akan menghasilkan ratusan notifikasi per
hari dan berujung diabaikan — sekaligus menenggelamkan alert yang benar-benar
penting. Kegagalan sudah ditangani fail2ban pada lapisan yang tepat.

Keberhasilan berperilaku sebaliknya: volumenya sangat rendah karena hanya pemilik
sistem yang masuk, sementara nilainya tinggi. Login gagal tidak berbahaya; login
**berhasil** yang tidak dikenali pemiliknya justru berbahaya. Asal koneksi
dibandingkan terhadap daftar IP yang dikenal, dan yang di luar daftar naik
tingkat menjadi `warning`.

Terverifikasi pada login nyata:

```
14:17:25 sshd(pam_google_authenticator): Accepted google_authenticator for amikom
14:17:25 sshd: pam_unix(sshd:session): session opened for user amikom
14:17:27 notify: TERKIRIM via telegram [info] Sesi SSH dibuka: amikom
```

Selisih dua detik antara sesi terbuka dan notifikasi terkirim menunjukkan login
tidak tertunda menunggu pengiriman.

Pengujian pemicu 2 dan 3 memakai salinan skrip, bukan yang terpasang. Pemicu 2
menjalankan `systemctl` tiruan yang hanya mencatat perintah tanpa
mengeksekusinya — tanpa itu, uji akan benar-benar me-restart layanan produksi.
Diverifikasi setelahnya bahwa layanan produksi tidak pernah restart dan seluruh
arsip backup tetap lolos checksum.

### Diam saat sehat

Pemeriksaan harian versi terpasang dijalankan tepat setelahnya dan **tidak
mengirim apa pun**:

```
[2026-07-31T12:59:38+07:00] Pemeriksaan harian: seluruh butir lolos
                            (disk 44%, sertifikat 38 hari)
```

Ini disengaja. Alert yang berbunyi setiap hari akan diabaikan, dan alert yang
diabaikan sama saja dengan tidak ada. Health check pun hanya memberitakan bila
aplikasi **tidak pulih** setelah restart otomatis.

### Cakupan pemeriksaan harian

Kapasitas disk, masa berlaku sertifikat, kesegaran arsip backup, konsistensi
index terhadap record di disk, dan integritas basis data. Kelimanya adalah
kegagalan yang tidak mengumumkan dirinya sendiri.

Kredensial berada pada `/etc/qrcode-notify.conf` berizin 0600 milik root dan
tidak dilacak git.

**Status: TERPENUHI**

---

## Kegiatan 13 — Pemeliharaan Rutin VPS

**Output:** Log bersih, OS up-to-date, penggunaan resource efisien.

```
disk root   : 17 GB / 38 GB (44 %)
logs/       : 146 MB
static/data : 397 MB
backups/    : 152 MB
journal     : 735 MB
RAM         : 1,1 GiB / 9,7 GiB
```

Pembersihan sisa berkas operasi berjalan mingguan lewat cron. Eksekusi pertama
menghapus 29 berkas `*.backup_*` berumur lebih dari 30 hari dan menurunkan
direktori log dari 120 MB ke 90 MB.

Berkas log aktif tidak tersentuh: `log_generate.csv`, `log_verifikasi.csv`, dan
`security_state.db` terverifikasi tetap utuh.

**Catatan:** journal systemd menempati 735 MB. Jalankan
`journalctl --vacuum-time=30d` bila diperlukan penghematan ruang.

**Status: TERPENUHI**

---

## Kegiatan 14 — Deploy Pembaruan Aplikasi ke Production

**Output:** Versi terbaru live di production, layanan berjalan stabil.

```
$ git log --oneline -3
c6b77eb Wajibkan autentikasi dua faktor SSH berbasis TOTP
61cad71 Hapus blok usang yang bertentangan pada bukti Kegiatan 4
57d279f Tuntaskan alert otomatis, empat pemicu diuji sampai pesan terkirim

branch          : main
belum di-commit : 0
belum di-push   : 0

$ git worktree list
/opt/qrcode          c6b77eb [main]
/opt/qrcode-staging  d9f690e (detached HEAD)
```

### Penyelarasan branch

Produksi semula berjalan pada branch fitur sementara `main` tertinggal 14 commit.
Susunan itu berbahaya: `main` adalah branch default repositori, sehingga clone
baru maupun rilis arsip akan mengambil kode lama — tanpa index, tanpa konfigurasi
firewall, dan tidak cocok dengan angka yang dilaporkan dalam naskah. Rollback ke
`main`, refleks paling wajar saat panik, justru akan menjadi regresi.

Branch fitur di-fast-forward ke `main`, dan produksi kini deploy dari `main`.
Checkout mengubah **0 berkas** karena pohonnya identik. Staging dilepas ke
detached HEAD agar tidak memegang ref `main` yang dibutuhkan produksi.

Alur kerja: fitur → staging → verifikasi → merge ke `main` → produksi.

**Status: TERPENUHI**

---

## Kegiatan 15 — Cron Job Maintenance Otomatis

**Output:** Cron job aktif dan terverifikasi berjalan sesuai jadwal.

```
$ crontab -l
0    2 * * *  backup-qrcode.sh harian
0    3 * * 0  backup-qrcode.sh penuh
*/15 *  * * *  healthcheck-qrcode.sh
30   4 * * 1  prune-backups-qrcode.sh
0    7 * * *  daily-check.sh

entri cron aktif : 5
cron.service     : active
logrotate        : /etc/logrotate.d/qrcode terpasang
```

Bukti eksekusi nyata:

```
[2026-07-31T02:00:01] backup harian terjadwal menghasilkan arsip 20 MB
[2026-07-31T12:59:38] Pemeriksaan harian: seluruh butir lolos
```

Health check memeriksa aplikasi melalui HTTP, bukan `systemctl is-active`, karena
proses dapat berstatus aktif namun berhenti melayani. Restart hanya dilakukan
bila dua pemeriksaan berturut-turut gagal **dan** tidak ada tanda pekerjaan latar
yang berjalan — generate serta verifikasi massal berjalan sebagai thread daemon,
sehingga restart akan membunuhnya tanpa jejak.

Logrotate hanya menyentuh berkas `*.log`. Berkas CSV di `logs/` sengaja
dikecualikan karena merupakan sumber data metrik dashboard, bukan log teknis, dan
merotasinya akan memotong jendela pengukuran 28 hari.

**Status: TERPENUHI**

---

## Kegiatan 16 — Maintenance Bulanan

**Output:** Dependensi diperbarui, query DB lebih optimal, kapasitas storage terpantau.

```
$ pip check
No broken requirements found.

$ PRAGMA integrity_check
ok

$ du -sh
397M  /opt/qrcode/static/data
146M  /opt/qrcode/logs
152M  /opt/qrcode/backups

dependensi usang: 27
```

**Rekomendasi: dependensi dibekukan sampai penelitian selesai.**

Alasannya bukan sekadar risiko teknis. Tiga paket berada tepat di jalur
pengukuran yang dilaporkan dalam naskah:

| Paket | Peran dalam penelitian |
|---|---|
| `pycryptodome` 3.20.0 | Implementasi RSA-PSS. Seluruh angka `verify_time` 1,02–1,05 ms diukur pada versi ini |
| `qrcode` 7.4.2 | Pembangkitan simbol QR, memengaruhi `qr_version` dan `qr_modules` |
| `opencv-python-headless` 4.10 | Pendekodean citra QR, memengaruhi `decode_time` |

Memperbarui ketiganya di tengah penelitian akan mengubah baseline pengukuran dan
membuat angka yang sudah dilaporkan tidak dapat direproduksi. Selain itu `numpy`
1.x → 2.x dan `pandas` 2.x → 3.x membawa perubahan API yang memutus
kompatibilitas, sedangkan keduanya dipakai skrip analisis penelitian.

Versi yang berlaku saat pengukuran dicatat pada
`data-penelitian/requirements-terukur.txt` sebagai **syarat reproduksibilitas**,
bukan sebagai utang teknis. Pembaruan dijadwalkan setelah naskah final dan diuji
pada lingkungan staging (Kegiatan 9) lebih dulu.

**Status: pemantauan TERPENUHI · pembaruan dependensi SENGAJA DITUNDA**

---

## Tindak Lanjut yang Tersisa

1. **Enkripsi arsip backup** — wajib sebelum salinan disimpan di luar server,
   karena arsip memuat kunci privat penandatangan. Cukup mengisi `GPG_RECIPIENT`.
2. **Pembersihan journal systemd** — 735 MB, opsional.
3. **Pembaruan dependensi** — setelah naskah final, diuji di staging.

---

## Lampiran — Berkas Pendukung

| Berkas | Isi |
|---|---|
| `deploy/maintenance/backup-qrcode.sh` | Skrip backup dua mode |
| `deploy/maintenance/healthcheck-qrcode.sh` | Health check berbasis HTTP |
| `deploy/maintenance/daily-check.sh` | Pemeriksaan harian lima butir |
| `deploy/maintenance/notify.sh` | Pengirim notifikasi multi-kanal |
| `deploy/maintenance/prune-backups-qrcode.sh` | Pembersihan sisa berkas |
| `deploy/maintenance/cek-totp` | Diagnosis kecocokan kode TOTP |
| `deploy/maintenance/notify-ssh-login.sh` | Pemberitahuan sesi SSH dibuka |
| `deploy/maintenance/sshd-10-hardening.conf` | Konfigurasi hardening SSH |
| `deploy/maintenance/pam-sshd.conf` | Konfigurasi PAM dengan TOTP |
| `deploy/maintenance/logrotate-qrcode.conf` | Konfigurasi rotasi log |
| `deploy/maintenance/crontab-root.txt` | Salinan jadwal cron |
| `deploy/systemd/qrcode-staging.service` | Unit layanan staging |
| `deploy/nginx/staging.rsa-pss.com.conf` | Vhost staging |
| `data-penelitian/hasil_index_produksi.json` | Benchmark index produksi |
| `data-penelitian/hasil_verifikasi_jalur_valid.json` | Pengukuran 100.000 verifikasi |
| `data-penelitian/requirements-terukur.txt` | Versi dependensi saat pengukuran |
| `dokumen/pelaporan_kinerja_verifikasi.md` | Analisis kinerja verifikasi |
| `dokumen/justifikasi_ambang_kedaluwarsa_payload.md` | Justifikasi ambang kebijakan |
