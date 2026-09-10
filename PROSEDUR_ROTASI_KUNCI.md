# Prosedur Rotasi, Masa Berlaku, dan Pemusnahan Kunci

Dokumen ini memenuhi aspek 3.9, 3.10, dan 3.11 pada daftar periksa NIST SP 800-57
Part 1 Rev. 5 di Lampiran 7 laporan penelitian. Sasarannya satu: kunci penandatangan
dapat diganti tanpa membatalkan QR Code yang sudah beredar.

## 1. Dasar dan parameter

| Parameter | Nilai | Letak |
|---|---|---|
| Masa berlaku kunci penandatangan | 1.095 hari (3 tahun) | `Config.RSA_KEY_VALIDITY_DAYS` |
| Direktori kunci pensiun | `keys/retired/` | `Config.RETIRED_KEYS_DIR` |
| Penyertaan `kid` pada payload | nonaktif | `Config.QR_EMIT_KEY_ID` |
| Kunci aktif | `rsa_key.pem` | `Config.RSA_KEY_FILE` |

NIST SP 800-57 menetapkan cryptoperiod terbatas bagi kunci privat penandatangan.
Tiga tahun dipilih agar selaras dengan kekuatan keamanan 112 bit RSA-2048 yang
berlaku sampai 2030. Sistem hanya **memperingatkan** lewat log bila kunci
melampaui masa berlakunya dan tidak menolak menandatangani, karena penghentian
mendadak pada layanan produksi lebih merugikan daripada rotasi yang terlambat
beberapa hari.

## 2. Mengapa registri kunci pensiun diperlukan

Sebelum mekanisme ini ada, mengganti `rsa_key.pem` akan membuat **seluruh** QR
Code yang pernah terbit gagal diverifikasi, karena tanda tangannya hanya sah
terhadap kunci lama. Direktori `keys/retired/` menyimpan bagian publik kunci
yang sudah dipensiunkan. Saat verifikasi, kunci aktif dicoba lebih dulu; bila
gagal, kunci pensiun dicoba berurutan. Dengan begitu:

- QR Code lama tetap dapat diverifikasi setelah rotasi.
- QR Code baru diverifikasi kunci aktif pada percobaan pertama, sehingga biaya
  verifikasi normal tidak bertambah.
- Tanda tangan dari kunci di luar registri tetap ditolak.

## 3. Langkah rotasi

Jalankan sebagai root pada server produksi. Lakukan di luar jam sibuk.

```bash
cd /opt/qrcode
sudo systemctl stop qrcode.service

# 1. Pensiunkan kunci aktif: simpan HANYA bagian publiknya
sudo mkdir -p keys/retired
STAMP=$(date +%Y%m%d)
sudo venv/bin/python3 -c "
from Crypto.PublicKey import RSA
k = RSA.import_key(open('rsa_key.pem','rb').read())
open('keys/retired/rsa-$STAMP.pem','wb').write(k.publickey().export_key())
"

# 2. Arsipkan kunci privat lama ke penyimpanan luring sebelum dimusnahkan
sudo cp rsa_key.pem /root/arsip-kunci/rsa_key-$STAMP.pem
sudo chmod 600 /root/arsip-kunci/rsa_key-$STAMP.pem

# 3. Terbitkan kunci aktif baru
sudo venv/bin/python3 -c "
from Crypto.PublicKey import RSA
open('rsa_key.pem','wb').write(RSA.generate(2048).export_key())
"
sudo chown root:www-data rsa_key.pem && sudo chmod 640 rsa_key.pem
sudo chown -R root:www-data keys && sudo chmod 750 keys keys/retired

# 4. Aktifkan penyertaan kid supaya pemilihan kunci menjadi deterministik
#    Ubah QR_EMIT_KEY_ID menjadi True pada kelas Config di app.py

sudo systemctl start qrcode.service
```

## 4. Verifikasi setelah rotasi

Ketiga pemeriksaan berikut wajib lulus sebelum rotasi dinyatakan selesai.

```bash
# a. Kunci pensiun termuat dan kid kunci aktif berubah
sudo journalctl -u qrcode.service -n 20 | grep -E "Kunci pensiun|kid RSA"

# b. Kunci publik baru tersaji
curl -s -i http://127.0.0.1:5000/.well-known/qr-public-key | grep X-Key-Id

# c. QR Code TERBITAN LAMA masih sah. Ganti <token> dengan token QR sebelum rotasi.
curl -s http://127.0.0.1:5000/v/<token> | grep -oE "Valid dan Authentik|Signature tidak valid"
```

Pemeriksaan (c) adalah yang menentukan. Bila hasilnya `Signature tidak valid`,
kunci pensiun tidak termuat: hentikan layanan, periksa isi dan hak akses
`keys/retired/`, lalu ulangi. Jangan biarkan kondisi itu berjalan di produksi.

## 5. Pemusnahan kunci yang tidak terpakai

Kunci **privat** yang dipensiunkan tidak lagi berguna setelah rotasi karena tidak
ada lagi yang perlu ditandatangani dengannya. Kunci **publik**-nya harus tetap
disimpan di `keys/retired/` selama masih ada QR Code terbitannya yang berlaku.

Masa tunggu pemusnahan: **masa berlaku payload (7 hari) ditambah margin 30 hari**.
Sesudah itu tidak ada lagi QR Code sah dari kunci tersebut.

```bash
# Setelah masa tunggu terlewati, musnahkan salinan kunci privat lama
sudo shred -u -n 3 /root/arsip-kunci/rsa_key-$STAMP.pem

# Kunci publiknya boleh ikut dilepas hanya bila tidak ada lagi QR terbitannya
# yang perlu diverifikasi ulang untuk keperluan audit
sudo rm keys/retired/rsa-$STAMP.pem
```

Catat setiap pemusnahan pada log audit dengan mencantumkan kid, tanggal rotasi,
dan tanggal pemusnahan. Kid dapat dihitung ulang dari kunci publik mana pun:

```bash
sudo venv/bin/python3 -c "
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
k = RSA.import_key(open('keys/retired/rsa-YYYYMMDD.pem','rb').read())
print(SHA256.new(k.export_key(format='DER')).hexdigest()[:16])
"
```

## 6. Batas yang tetap berlaku

Rotasi ini tidak mengubah tempat penyimpanan kunci privat. Kunci tetap berupa
berkas PEM bermode 0640 pada sistem berkas server, bukan pada modul kriptografis
bersertifikasi FIPS 140-3. Aspek 3.8 pada Lampiran 7 karena itu tetap
dikecualikan, dan pemenuhannya menuntut pengadaan perangkat keras.
