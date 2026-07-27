# Manual Passphrase & Pemulihan Cadangan
## QR Code Security System (RSA-PSS)

Panduan membuat, menyimpan, dan menggunakan passphrase untuk cadangan
terenkripsi sistem, serta cara memulihkannya.

**Lokasi cadangan:** repositori **private**
`https://github.com/ndika383/qrcode-rsa-pss-backup`

---

## 1. Kenapa Ini Penting

Cadangan berisi `rsa_key.pem` dan `ecdsa_key.pem` — **kunci privat** yang dipakai
menandatangani setiap QR Code.

> **Kunci ini tidak tergantikan.** Bila hilang, seluruh QR Code yang sudah
> diterbitkan **tidak dapat diverifikasi lagi selamanya**, dan tidak ada cara
> membuat ulang kunci yang identik.

Karena itu cadangan dienkripsi. Konsekuensinya:

| Yang hilang | Akibat |
|---|---|
| Server rusak, cadangan & passphrase aman | Dapat dipulihkan sepenuhnya |
| Passphrase hilang, cadangan aman | **Cadangan tidak dapat dibuka. Sama dengan tidak punya cadangan.** |
| Passphrase bocor ke pihak lain | Pihak itu dapat memalsukan tanda tangan QR Anda |

---

## 2. Aturan Passphrase

1. **Jangan pernah menuliskannya di dalam server.** Bukan di `.env`, bukan di
   skrip, bukan di catatan pada `/opt/qrcode`. Bila server jatuh ke tangan
   orang lain, passphrase ikut jatuh.
2. **Jangan pernah mengetiknya ke dalam chat/AI/tiket.** Apa pun yang diketik
   di sana tercatat dan enkripsi menjadi sia-sia.
3. **Jangan dikirim lewat WhatsApp, email, atau chat.** Bila harus diserahkan
   ke orang lain, gunakan pengelola kata sandi bersama atau serahkan langsung.
4. **Simpan minimal di dua tempat** yang tidak akan hilang bersamaan.

### Tempat penyimpanan yang disarankan

| Tempat | Keterangan |
|---|---|
| Pengelola kata sandi (Bitwarden, KeePassXC, 1Password) | Paling praktis dan aman |
| Ditulis tangan, disimpan di brankas/lemari terkunci | Tahan terhadap peretasan |
| Amplop tertutup pada pihak tepercaya | Cadangan bila Anda tak bisa dihubungi |

**Hindari:** catatan di ponsel tanpa kunci, Google Docs biasa, file `.txt` di
desktop, atau dikirim ke diri sendiri lewat email.

---

## 3. Membuat Passphrase yang Kuat

Gunakan **rangkaian kata** (diceware), bukan satu kata rumit. Contoh pola:

```
kopi-jembatan-langit-42-merapi
```

Ciri passphrase yang baik:

- Minimal **4–6 kata** acak (bukan potongan kalimat yang bermakna)
- Panjang total minimal **20 karakter**
- Bukan nama, tanggal lahir, NIM, nama kampus, atau kata dari dokumen ini
- Tidak dipakai ulang dari akun lain

Bila ingin dibangkitkan acak di komputer **pribadi** (bukan server):

```bash
shuf -n 5 /usr/share/dict/words | tr '\n' '-'
```

> Setelah dibuat, **langsung simpan** ke pengelola kata sandi sebelum menutup
> terminal.

---

## 4. Membuat / Memperbarui Cadangan

Lakukan bila kunci berubah, atau saat data penelitian bertambah signifikan.

### 4a. Buat arsip

```bash
cd /opt/qrcode
sudo tar -czf /tmp/secrets.tar.gz .env rsa_key.pem ecdsa_key.pem
sudo tar -czf /tmp/research-data.tar.gz \
  logs/log_generate.csv logs/log_verifikasi.csv data/calibration data-penelitian
sudo chown $(id -u):$(id -g) /tmp/secrets.tar.gz /tmp/research-data.tar.gz
chmod 600 /tmp/secrets.tar.gz /tmp/research-data.tar.gz
```

### 4b. Enkripsi (akan meminta passphrase dua kali)

```bash
cd /tmp && for f in secrets research-data; do gpg --symmetric --cipher-algo AES256 --output $f.tar.gz.gpg $f.tar.gz; done
```

### 4c. Hapus arsip polos — WAJIB

```bash
shred -u /tmp/secrets.tar.gz /tmp/research-data.tar.gz
```

### 4d. Kirim ke repositori cadangan

```bash
cd /tmp && git clone https://github.com/ndika383/qrcode-rsa-pss-backup.git bk && cd bk
cp /tmp/secrets.tar.gz.gpg /tmp/research-data.tar.gz.gpg .
git add -A && git commit -m "Update encrypted backup" && git push
cd /tmp && rm -rf bk /tmp/*.tar.gz.gpg
```

> Gunakan **passphrase yang sama** setiap kali memperbarui, agar Anda tidak
> perlu mengingat banyak passphrase untuk versi yang berbeda.

---

## 5. Memulihkan Cadangan

### 5a. Ambil dan dekripsi

```bash
git clone https://github.com/ndika383/qrcode-rsa-pss-backup.git
cd qrcode-rsa-pss-backup
gpg --decrypt --output secrets.tar.gz secrets.tar.gz.gpg
gpg --decrypt --output research-data.tar.gz research-data.tar.gz.gpg
```

### 5b. Periksa isi SEBELUM diekstrak

```bash
tar -tzf secrets.tar.gz
tar -tzf research-data.tar.gz
```

Keluaran `secrets.tar.gz` harus berisi tepat tiga berkas:
`.env`, `rsa_key.pem`, `ecdsa_key.pem`.

### 5c. Ekstrak ke sistem

```bash
sudo tar -xzf secrets.tar.gz -C /opt/qrcode
sudo tar -xzf research-data.tar.gz -C /opt/qrcode
```

### 5d. Kembalikan izin berkas — WAJIB

```bash
sudo chown root:www-data /opt/qrcode/rsa_key.pem /opt/qrcode/ecdsa_key.pem
sudo chmod 640 /opt/qrcode/rsa_key.pem /opt/qrcode/ecdsa_key.pem
sudo chown root:root /opt/qrcode/.env
sudo chmod 600 /opt/qrcode/.env
```

### 5e. Jalankan ulang dan pastikan sehat

```bash
sudo systemctl restart qrcode
sudo systemctl is-active qrcode
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:5000/testing/calibration
```

### 5f. Bersihkan berkas polos sisa pemulihan

```bash
shred -u secrets.tar.gz research-data.tar.gz
```

---

## 6. Menguji Cadangan Secara Berkala

Cadangan yang belum pernah diuji **bukan cadangan**. Uji setiap kali passphrase
diperbarui, dan minimal **sekali setiap 6 bulan**.

Uji aman berikut tidak menyentuh sistem produksi:

```bash
cd /tmp && git clone https://github.com/ndika383/qrcode-rsa-pss-backup.git uji-restore && cd uji-restore && gpg --decrypt --output cek.tar.gz secrets.tar.gz.gpg && tar -tzf cek.tar.gz && shred -u cek.tar.gz && cd /tmp && rm -rf uji-restore
```

Bila muncul daftar `.env`, `rsa_key.pem`, `ecdsa_key.pem` — cadangan sah.

---

## 7. Bila Terjadi Masalah

| Gejala | Sebab | Tindakan |
|---|---|---|
| `gpg: decryption failed: Bad session key` | Passphrase salah | Coba variasi yang Anda ingat; perhatikan Caps Lock & tata letak papan ketik |
| `gpg: no valid OpenPGP data found` | Berkas rusak/terpotong | Klon ulang repositori, jangan unduh lewat tombol "Download ZIP" |
| Aplikasi gagal jalan usai pulih | Izin berkas salah | Ulangi langkah **5d** |
| QR lama gagal diverifikasi usai pulih | Kunci yang dipulihkan berbeda | Pastikan memulihkan `secrets.tar.gz.gpg` versi yang benar (cek riwayat commit) |
| Lupa passphrase | — | **Tidak ada jalan pemulihan.** Segera terbitkan kunci baru; QR lama tidak lagi dapat diverifikasi |

---

## 8. Daftar Periksa

Saat membuat/memperbarui cadangan:

- \[ \] Passphrase tersimpan di pengelola kata sandi
- \[ \] Passphrase juga tersimpan di tempat kedua (brankas/tulisan tangan)
- \[ \] Arsip polos (`*.tar.gz`) sudah dihapus dengan `shred`
- \[ \] Berkas `.gpg` berhasil ter-push ke repositori private
- \[ \] Uji dekripsi sudah dijalankan dan berhasil
- \[ \] Repositori cadangan dipastikan masih **private**

Cek visibilitas repositori kapan saja:

```bash
gh repo view ndika383/qrcode-rsa-pss-backup --json isPrivate
```

Hasil harus `{"isPrivate":true}`.

---

## 9. Yang TIDAK Dicadangkan

Data berikut sengaja dikecualikan karena dapat dibuat ulang atau melampaui
batas GitHub (100 MB per berkas):

| Lokasi | Ukuran | Alasan |
|---|---|---|
| `data/verify_payloads/` | ±408 MB | Data turunan |
| `data/downloads/` | ±295 MB | Bundel ZIP, dapat dibuat ulang |
| `data/testing/testing_results.db` | ±129 MB | Melebihi batas GitHub |
| `data/task_results/` | ±46 MB | Data turunan |
| `venv/` | ±575 MB | `pip install -r requirements.txt` |

Kode sumber sistem berada di repositori terpisah:
`ndika383/qrcode-security-system-rsa-pss`.
