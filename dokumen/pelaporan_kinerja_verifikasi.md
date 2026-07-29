# Pelaporan Kinerja Verifikasi: Memisahkan Biaya Kriptografi dari Biaya Penyimpanan

Dokumen pendukung metodologi untuk sistem verifikasi QR Code berbasis RSA-PSS.
Melengkapi [justifikasi ambang kedaluwarsa](justifikasi_ambang_kedaluwarsa_payload.md).

---

## 1. Masalah Pelaporan

Halaman hasil verifikasi massal melaporkan throughput sebesar 6,5 berkas/detik
dan waktu rerata 153 ms per berkas. Bila angka tersebut dikutip sebagai kinerja
skema Adapted RSA-PSS, kesimpulannya keliru: **99,3% dari waktu itu bukan
kriptografi.**

Dokumen ini menetapkan dekomposisi yang benar, angka mana yang boleh diklaim
sebagai kinerja skema, dan angka mana yang merupakan properti arsitektur
penyimpanan.

---

## 2. Dekomposisi Terukur

Sumber: verifikasi massal `task_id` `56d7146d-8ec1-42e1-aa88-932286f0fbe9`,
n = 528 berkas, pada `static/data` berisi 100.714 record.

| Fase | Rerata | Median | % total | Sifat biaya |
|---|---:|---:|---:|---|
| `load_time` (baca berkas PNG) | 0,04 ms | 0,00 ms | 0,0 % | I/O masukan |
| `decode_time` (citra → payload) | 1,04 ms | 1,00 ms | 0,7 % | Intrinsik medium QR |
| `verify_time` (RSA-PSS) | 1,02 ms | 1,00 ms | 0,7 % | **Intrinsik kriptografi** |
| `db_time` (pencarian record + nonce) | 149,88 ms | 146,00 ms | 97,7 % | Implementasi penyimpanan |
| **Total** | **153,41 ms** | **150,00 ms** | 100 % | |

### 2.1 Validasi silang pengukuran kriptografis

Angka `verify_time` diuji ulang secara independen pada sandbox terisolasi dengan
korpus, kunci, dan parameter yang sama (RSA-PSS 2048/SHA-256, salt 8 bita):
diperoleh 1,023–1,064 ms terhadap 1,02 ms pada pengukuran produksi. Dua
eksekusi terpisah menghasilkan nilai yang berimpit, sehingga pengukuran
kriptografis dapat dinyatakan stabil dan reproducible.

### 2.2 Anatomi `db_time`

`db_time` bukan biaya sia-sia seluruhnya. Di dalamnya terdapat tiga fungsi
keamanan yang memang disyaratkan protokol:

1. Pencarian record asli untuk mendeteksi modifikasi data.
2. Pencatatan nonce untuk mendeteksi replay.
3. Pemeriksaan kedaluwarsa — 2,2 µs, dapat diabaikan.

Yang bermasalah adalah *cara* butir 1 diimplementasikan. `find_original_qr_data()`
memanggil `os.listdir()` atas seluruh direktori data pada setiap verifikasi,
lalu menyaring hasilnya di memori. Pada 100.714 record, satu verifikasi membaca
100.714 nama berkas untuk menemukan satu record — terukur 122 ms, atau sekitar
81% dari `db_time`.

Rumusan yang akurat: **waktu yang dilaporkan didominasi biaya implementasi
lapisan penyimpanan, bukan biaya protokol maupun kriptografi.**

---

## 3. Sifat Skalabilitas

Biaya pencarian bersifat O(n) terhadap **jumlah seluruh QR yang pernah
diterbitkan**, bukan terhadap jumlah QR yang sedang diverifikasi. Konsekuensinya:

- Verifikasi satu QR menjadi lebih lambat seiring waktu tanpa ada perubahan pada
  QR itu sendiri.
- Setiap penerbitan QR baru memperlambat verifikasi seluruh QR lain, permanen.
- Throughput yang dilaporkan hanya berlaku untuk satu titik ukur populasi data.
  Angka 6,5 berkas/detik adalah nilai pada n = 100.714, bukan konstanta sistem.

Sifat ini yang membuat throughput ujung-ke-ujung tidak sah dipakai sebagai
karakteristik algoritma.

---

## 4. Perbaikan: Index Pencarian Record

### 4.1 Rancangan

Ditambahkan tabel `qr_record_index` pada `security_state.db` yang memetakan nama
berkas record ke `id` dan `nonce`-nya. Pencarian berbasis awalan nama berkas
diubah dari pemindaian direktori menjadi *range scan* atas primary key:

```sql
SELECT filename FROM qr_record_index WHERE filename >= ? AND filename < ?
```

Batas atas dibentuk dengan menaikkan satu karakter terakhir awalan, sehingga
rentangnya persis menyetarai semantik `str.startswith()` pada implementasi lama —
termasuk kasus tabrakan awalan seperti `qr_TEST_` yang juga mencakup
`qr_TEST_X_*.json`.

Pencarian via nonce, yang sebelumnya membuka setiap berkas JSON di direktori
sampai menemukan kecocokan, kini memakai kolom `nonce` yang terindeks.

### 4.2 Jaminan kebenaran selama transisi

Index baru dianggap otoritatif setelah backfill seluruh direktori selesai,
ditandai kunci `qr_record_index_backfilled_v1` pada tabel `security_metadata`.
Sebelum penanda itu ada, pencarian tetap memakai pemindaian direktori.

Ini disengaja: index yang belum lengkap akan melaporkan record asli sebagai
tidak ada, dan klasifikasi verifikasi ikut berubah — dari "Valid" menjadi "Data
Tidak Ditemukan di Database". Dengan pola ini, penerapan kode baru tanpa backfill
bersifat netral terhadap perilaku, dan percepatan baru aktif setelah backfill
dijalankan.

Konsistensi index terhadap penghapusan ditangani pada
`cleanup_all_generated_files()`, yang kini mengosongkan index sekaligus mencabut
status otoritatifnya.

### 4.3 Uji ekuivalensi

Diuji pada sandbox terisolasi dengan 525 kueri yang mencakup kasus batas: id
mengandung underscore, tabrakan awalan (`TEST`, `TEST_X`, `TEST_XY`), karakter
non-ASCII, id yang memerlukan `secure_filename()`, payload dengan id dimodifikasi
(memicu jalur fallback nonce), payload dengan field lain dimodifikasi, payload
yang sama sekali tidak ada di basis data, serta **berkas record yang rusak**
(0 bita, JSON terpotong, dan JSON bertipe non-objek).

Keluaran `find_original_qr_data()` dibandingkan elemen per elemen antara kedua
mode — record asli, daftar berkas, dan status kecocokan persis.

**Hasil: 0 selisih dari 525 kueri.**

Kasus berkas rusak awalnya **tidak** ekuivalen dan baru terungkap setelah
backfill produksi menemukan 12 berkas 0 bita sisa uji beban HTTP. Pada
pemindaian direktori, berkas rusak tetap masuk daftar kandidat berdasarkan nama
dan baru gagal ketika dibuka, sehingga `data_files` tidak kosong dan payload
diklasifikasikan sebagai "Data Palsu". Bila berkas seperti itu dihilangkan dari
index, klasifikasinya bergeser menjadi "Data Tidak Ditemukan di Database".
Karena itu backfill kini mendaftarkan berkas rusak tanpa isi, sehingga perilaku
terjaga persis. Perubahan ini murni soal kinerja, bukan semantik.

### 4.4 Temuan tambahan: kerapuhan pada record non-objek

Uji di atas menyingkap cacat yang **sudah ada sebelum perubahan ini**. Berkas
`qr_*.json` yang berisi JSON valid tetapi bukan objek — misalnya `[1,2,3]` —
lolos `json.load()`, lalu menabrak `similarity_score()` yang memanggil `.keys()`
atas list, sehingga verifikasi berakhir dengan `AttributeError`.

Cacat ini terdapat pada kedua mode dan tidak berkaitan dengan index. Ditutup
dengan penjagaan `isinstance(candidate, dict)` pada pemuatan kandidat; berkas
bertipe lain kini dilewati seperti berkas yang gagal dibaca.

### 4.5 Kinerja terukur pada produksi

Diukur langsung pada `static/data` produksi berisi **100.713 record**, per kueri:

| Jenis kueri | Pemindaian | Index | Percepatan |
|---|---:|---:|---:|
| Payload utuh | 129,450 ms | 0,602 ms | 215× |
| Field non-id dimodifikasi | 126,060 ms | 0,588 ms | 214× |
| Tidak ada di basis data | 3.777,625 ms | 0,963 ms | 3.922× |

Backfill 100.713 record memakan 14,8 detik, sekali jalan.

Perhatikan bahwa percepatan agregat sangat bergantung komposisi beban kerja.
Melaporkan satu angka tunggal akan menyesatkan; rincian per jenis kueri di atas
yang seharusnya dikutip.

### 4.6 Temuan keamanan tersirat

Baris terakhir tabel §4.5 bukan sekadar isu kinerja. Pada implementasi lama,
payload dengan id yang tidak dikenal memaksa server membuka **setiap** berkas
JSON di direktori data — terukur **3,78 detik** per permintaan pada 100.713
record produksi.

Ini merupakan amplifikasi: satu permintaan yang murah bagi penyerang memicu kerja
yang mahal bagi server, dan biayanya justru **paling tinggi** pada payload yang
tidak sah. Dengan konfigurasi 12 thread, belasan permintaan paralel berisi id
acak sudah cukup menjenuhkan thread pool selama beberapa detik, dan biaya itu
tumbuh seiring bertambahnya QR yang diterbitkan. Perbaikan pada §4.1 menutup
jalur ini dengan menurunkan biaya kasus terburuk menjadi 0,963 ms — sekitar
3.900 kali lebih murah.

Temuan ini layak masuk naskah sebagai bagian analisis keamanan, bukan hanya
sebagai catatan optimasi.

---

## 5. Cara Pelaporan yang Dianjurkan

### 5.1 Yang boleh diklaim sebagai kinerja skema

| Klaim | Dasar |
|---|---|
| Verifikasi tanda tangan 1,02–1,05 ms | `verify_time`, konsisten lintas tiga pengukuran independen (§2.1, §6.1) |
| ≈ 970 verifikasi tanda tangan/detik/thread | 1 / 1,03 ms |
| Dekode QR 1,04–1,07 ms | `decode_time`, properti medium QR |
| Pemeriksaan kedaluwarsa 2,2 µs | Mikrobenchmark |

### 5.2 Yang harus dilaporkan terpisah

| Besaran | Syarat pelaporan |
|---|---|
| Throughput ujung-ke-ujung | Wajib disertai ukuran populasi data (n = 100.714) dan keterangan bahwa nilainya dibatasi lapisan penyimpanan |
| `db_time` | Dinyatakan sebagai biaya implementasi, bukan biaya protokol |
| Percepatan index | Dirinci per jenis kueri, bukan satu angka agregat |

### 5.3 Yang tidak boleh diklaim

- "Skema Adapted RSA-PSS mencapai 6,5 verifikasi/detik." Angka ini mengukur
  arsitektur penyimpanan berkas datar, bukan algoritma.
- Perbandingan throughput ujung-ke-ujung terhadap sistem lain tanpa menyamakan
  ukuran populasi data — perbandingannya tidak setara.
- Klaim skalabilitas apa pun berdasarkan pengukuran pada satu ukuran korpus.

### 5.4 Bentuk sajian

Sajikan tabel dekomposisi §2 secara utuh, bukan hanya angka total. Selain lebih
jujur, tabel itu justru memperkuat naskah: ia menunjukkan bahwa biaya
kriptografis skema yang diusulkan sangat kecil, dan bahwa hambatan kinerja
berada pada lapisan yang dapat diperbaiki secara independen — sebagaimana
dibuktikan §4.

---

## 6. Status dan Langkah Lanjutan

| Butir | Status |
|---|---|
| Implementasi index | Selesai |
| Uji ekuivalensi (termasuk berkas rusak) | Selesai — 0 selisih dari 525 kueri |
| Perbaikan kerapuhan record non-objek | Selesai |
| Penerapan ke produksi | Selesai — layanan sehat pasca-restart |
| Backfill produksi | Selesai — 100.713 record, 14,8 detik |
| Pengukuran komponen produksi | Selesai — §4.5 |
| Pengukuran ujung-ke-ujung produksi | Selesai — §6.1 |

### 6.1 Hasil ujung-ke-ujung terukur

Dibandingkan atas dua verifikasi massal nyata pada produksi, keduanya dengan
korpus QR yang belum pernah diverifikasi sebelumnya:

| Fase | Sebelum (`56d7146d`, n = 528) | Sesudah (`7dc3bb0b`, n = 632) |
|---|---:|---:|
| `load_time` | 0,04 ms | 0,00 ms |
| `decode_time` | 1,04 ms | 1,07 ms |
| `verify_time` | 1,02 ms | 1,05 ms |
| `db_time` | 149,88 ms | **22,10 ms** |
| **Total** | **153,41 ms** | **25,73 ms** |
| Throughput | 6,5 berkas/detik | **38,9 berkas/detik** |
| Porsi `db_time` | 97,7 % | 85,9 % |

Perbaikan ujung-ke-ujung **6,0×**, dan nilainya berimpit dengan proyeksi
aritmetika yang dihitung sebelumnya (≈ 24,6 ms; ≈ 40 berkas/detik) — sehingga
model biaya pada §2 terkonfirmasi.

Perhatikan `verify_time` yang bergeming di 1,02–1,05 ms lintas kedua pengukuran
dan lintas sandbox (§2.1). Konsistensi ini menegaskan bahwa perbaikan sepenuhnya
terjadi pada lapisan penyimpanan dan tidak menyentuh jalur kriptografis sama
sekali — persis pemisahan yang menjadi pokok dokumen ini.

`db_time` yang tersisa (22,10 ms) kini didominasi pencatatan nonce ke SQLite dan
pembacaan record, yakni kerja yang memang disyaratkan protokol.

### 6.2 Catatan reproduksi

Pengukuran "sesudah" yang sah memerlukan korpus QR yang **belum pernah
diverifikasi**. Menjalankan ulang korpus lama akan menghasilkan klasifikasi
replay, bukan valid, sehingga tidak sebanding dengan pengukuran "sebelum".

Prosedur: terbitkan korpus QR baru melalui halaman generate massal, jalankan
verifikasi massal atas korpus tersebut, lalu baca dekomposisi fase dari
`data/task_results/<task_id>.json`.

### 6.3 Utang teknis yang tersisa

Terdapat **12 berkas record 0 bita** di `static/data`, sisa uji beban HTTP
(berpola `qr_HTTPSTRESS_f15f53_100_*.json`). Berkas tersebut kini terindeks
tanpa isi sehingga tidak mengubah perilaku, namun tetap merupakan data rusak
yang sebaiknya ditelusuri asal-usulnya — kemungkinan penulisan terpotong saat
uji beban — lalu dibersihkan.
