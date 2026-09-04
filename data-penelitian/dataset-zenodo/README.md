# Dataset Pengujian Keamanan dan Kalibrasi Kinerja — QR Code Security System RSA-PSS

Dataset ini memuat data mentah dan ringkasan hasil pengujian keamanan serta kalibrasi
kinerja kriptografi dari *QR Code Security System RSA-PSS*. Mulai versi 1.2.0 dataset
disertakan langsung di dalam arsip rilis perangkat lunaknya, sehingga kode dan data
terarsip dalam satu rekaman Zenodo yang sama
(concept DOI [10.5281/zenodo.21271011](https://doi.org/10.5281/zenodo.21271011)).

Dataset ini memuat **dua jenis data yang tidak boleh dicampur**:

1. **Simulasi peristiwa diskret terkalibrasi** — delapan sesi pengujian keamanan
   berisi 350.000 operasi. Angkanya diekspor apa adanya dari basis data hasil
   pengujian sistem (`data/testing/testing_results.db`) dan **diverifikasi identik
   bit-per-bit** terhadap sumbernya: 461.950 nilai dibandingkan, 0 selisih. Waktu
   operasinya diturunkan dari kalibrasi empiris, tetapi keputusan terdeteksi atau
   tidaknya sebuah serangan dibangkitkan dari laju terparameter, bukan dari
   pemanggilan jalur verifikasi.
2. **Pengukuran empiris** — 66.500 operasi pada `empiris/`, seluruhnya hasil
   pemanggilan jalur verifikasi asli. Tidak ada satu pun keputusan deteksi yang
   diundi.

Perbedaan ini menentukan cara membaca setiap angka dan diuraikan pada bagian
[Pengukuran empiris](#pengukuran-empiris).

## Struktur

```
indeks_sesi.csv                        14 sesi pengujian beserta waktu dan status
ringkasan_metrik.json                  ringkasan skalar tiap sesi
deret-mentah/                          18 berkas CSV, satu baris per operasi
stress-http/
  stress_http_ringkasan.csv            6 sesi real HTTP stress test
  stress_http_tahap.csv                19 tahap konkurensi, termasuk CPU dan memori
  stress_http_vs_inprocess.csv         perbandingan terhadap stress test in-process
empiris/
  hasil_empiris_20260904.json          keluaran lengkap harness pengukuran empiris
  empiris_ringkasan.csv                11 metrik, termasuk 4 kontrol negatif
  empiris_per_subjenis.csv             laju deteksi 7 subjenis pemalsuan data
  empiris_waktu.csv                    statistik waktu 4 skenario
  MANIFEST.sha256                      checksum SHA-256 keempat berkas di atas
kalibrasi/
  kalibrasi_quick_check.json           tier 1.000 sampel
  kalibrasi_production.json            tier 10.000 sampel
  kalibrasi_validation.json            tier 100.000 sampel (kalibrasi 2026-07-21)
  kalibrasi_validation_20260820.json   tier 100.000 sampel (sesi sama, lihat catatan)
  ringkasan_kalibrasi_tiga_tingkat.csv tabel gabungan ketiga tier
(.zenodo.json berada di akar repositori, bukan di folder ini)
```

Berkas di `deret-mentah/` bernama `<session_id>__<nama_deret>.csv` dengan kolom
`indeks_operasi`, `nilai`, `satuan`. Nilai ditulis memakai `repr()` Python sehingga
dapat dibaca ulang tanpa kehilangan presisi.

## Sesi pengujian

Delapan sesi pertama dijalankan berurutan pada 23 Juli 2026 melalui harness
`run_backend_tests.py`, dengan total 350.000 operasi.

| Jenis | Sesi | Operasi/sesi | Hasil pokok |
|---|---:|---:|---|
| `normal_operations` | 2 | 50.000 | Keberhasilan penandatanganan dan verifikasi 100% pada kedua sesi |
| `replay_attack` | 2 | 55.000 | Laju deteksi 92,35% dan 92,08%; positif palsu 0,96% dan 0,88% |
| `data_tampering` | 1 | 50.000 | Laju deteksi 78,14%; 1.465 pelanggaran integritas |
| `signature_forgery` | 2 | 25.000 | Akurasi penolakan 97,28% dan 96,88% |
| `stress_test` | 1 | 40.000 | Keberhasilan 97,42%; throughput 1.000 ops/detik pada 100 pengguna |
| `real_http_stress_test` | 6 | 80–800 | Uji HTTP nyata terhadap endpoint produksi |

Setiap sesi `normal_operations` mencatat 25.000 waktu penandatanganan dan 25.000 waktu
verifikasi; `total_operations` menghitung keduanya.

## Kalibrasi tiga tingkat

Kalibrasi mengukur waktu penandatanganan dan verifikasi pada tiga tingkat pengambilan
sampel. Berkas `ringkasan_kalibrasi_tiga_tingkat.csv` memuat kolom `kelompok` yang
memisahkan pengukuran sesi tunggal dari arsip terdahulu.

Kelompok `sesi_20260820` — ketiganya diukur berurutan pada mesin dan kondisi yang sama,
sehingga layak dipakai sebagai studi konvergensi. Rerata mendekati nilai stabil sementara
galat relatif menyempit sesuai pertambahan sampel:

| Tier | Sampel | RSA-PSS sign | RSA-PSS verify | ECDSA sign | ECDSA verify | Galat relatif |
|---|---:|---:|---:|---:|---:|---:|
| `quick_check` | 1.000 | 2,4882 ms | 0,8844 ms | 1,2178 ms | 2,4945 ms | 1,11–1,30% |
| `production` | 10.000 | 2,4843 ms | 0,8801 ms | 1,2150 ms | 2,4768 ms | 0,34–0,44% |
| `validation` | 100.000 | 2,4509 ms | 0,8647 ms | 1,2031 ms | 2,4443 ms | 0,10–0,13% |

Rentang rerata RSA-PSS sign antar-tier hanya 1,5%, dan galat relatif turun kira-kira
sepersepuluh setiap kenaikan sampel sepuluh kali lipat — pola yang diharapkan dari
penyempitan selang kepercayaan.

### Catatan penting tentang keterbandingan

Kelompok `arsip_20260721` berisi kalibrasi `validation` terdahulu, diukur **2026-07-21**
di atas kernel `6.8.0-134-generic`, sedangkan seluruh kelompok `sesi_20260820` diukur di
atas kernel `6.8.0-137-generic`. Rerata penandatanganan RSA-PSS pada arsip Juli tercatat
2,2443 ms, sekitar 9% lebih rendah daripada pengukuran Agustus. Selisih itu berasal dari
perbedaan kondisi sistem, bukan dari perbedaan tier.

**Untuk analisis konvergensi antar-tier, gunakan kelompok `sesi_20260820`.** Arsip Juli
dipertahankan karena berkas itulah yang dimuat sistem produksi dan dirujuk pada
dokumentasi terdahulu, tetapi tidak boleh disandingkan langsung dalam satu tabel
konvergensi.

Perbedaan cakupan lain: berkas kalibrasi Juli hanya memuat `rsa_pss_2048`, sedangkan
kalibrasi Agustus memuat `rsa_pss_2048` dan `ecdsa_p256`. Selisih ini dipertahankan apa
adanya, tidak ditambal.

## Real HTTP stress test

Enam sesi menguji sistem lewat HTTP sungguhan, berbeda dari `stress_test` yang berjalan
in-process. Kolom `kesahihan` pada `stress_http_ringkasan.csv` menandai mana yang layak
dipakai:

| Sesi | Endpoint | Timeout | Permintaan | Sukses | Kesahihan |
|---:|---|---:|---:|---:|---|
| 1 | `generate_verify` | 15 s | 80 | 0 | `gagal_total` |
| 2 | `generate_verify` | 15 s | 800 | 0 | `gagal_total` |
| 3 | `generate_verify` | 20 s | 80 | 7 | `sebagian_besar_gagal` |
| 4 | `generate_verify` | 90 s | 90 | 90 | `sah` |
| 5 | `server_metrics` | 60 s | 600 | 600 | `sah` |
| 6 | `generate_verify` | 120 s | 300 | 300 | `sah` |

**Hanya sesi 4, 5, dan 6 yang merupakan hasil pengukuran.** Sesi 1 dan 2 mencatat status
HTTP `0`, artinya tidak ada respons yang sah diterima, sehingga angka latensinya bukan
latensi layanan. Penyebabnya berbeda dan terbaca pada kolom `galat_dominan`:

- Sesi 1 dan 3 — `The read operation timed out`. Timeout 15 s dan 20 s lebih pendek
  daripada waktu alur sebenarnya. Setelah timeout dinaikkan ke 90–120 s pada sesi 4 dan 6,
  keberhasilan langsung 100%.
- Sesi 2 — `Generate response did not include ...`, dengan `timeout` nol pada keempat
  tahapnya. Server membalas cepat (p95 antara 0,068 dan 0,497 detik) tetapi harness gagal
  mengurai responsnya. Ini kegagalan alat ukur, bukan kegagalan sistem.

Sesi 5 menyasar `server_metrics`, endpoint pembacaan ringan tanpa operasi kriptografi,
sehingga tidak sebanding dengan `generate_verify` yang menjalankan penandatanganan,
pembuatan berkas QR, dan penulisan log.

### Catatan pembacaan

Beban dibangkitkan dari mesin yang sama dengan aplikasi, sehingga pembangkit beban dan
aplikasi berbagi 2 vCPU. Kolom `cpu_rerata_persen` memperlihatkan dampaknya: pada sesi 6
pemakaian CPU naik dari 71,0% pada 5 pengguna menjadi 88,9% pada 25 pengguna. Angka
throughput dan latensi di sini mencerminkan kondisi berbagi sumber daya itu, bukan batas
kemampuan sistem bila beban dibangkitkan dari mesin terpisah.

Perbandingan pada `stress_http_vs_inprocess.csv` perlu dibaca sebagai **simulasi
in-process versus pengukuran HTTP nyata**, bukan dua pengukuran setara. Throughput
in-process tercatat persis 1000,0 untuk 100, 500, 1.000, dan 1.500 pengguna — datar di
seluruh rentang beban, ciri nilai model dan bukan hasil ukur.

Jumlah permintaan pada sesi yang sah kecil (90 dan 300), sehingga p99 ditentukan oleh
satu atau dua nilai ekstrem. Pada sesi 4, p99 sebesar 104,863 detik praktis sama dengan
nilai maksimum 106,939 detik.

Nilai p95 pada sesi 4 (99,616 detik) melampaui timeout 90 detik tanpa satu pun kegagalan
karena timeout berlaku per permintaan HTTP, sedangkan waktu yang diukur mencakup alur
`generate_verify` yang terdiri atas dua permintaan berurutan.

## Pengukuran empiris

Dijalankan 4 September 2026 melalui `data-penelitian/harness_empiris.py`, seed 20260824, durasi 3 menit 46 detik. Berbeda dari
delapan sesi simulasi, harness ini benar-benar memodifikasi payload lalu memanggil
verifikasi RSA-PSS dan `classify_qr_verification()` milik aplikasi. Basis data status
keamanan diarahkan ke berkas sementara sehingga buku besar nonce produksi tidak
tersentuh.

| Skenario | Operasi | Hasil pokok |
|---|---:|---|
| Pemalsuan data, 7 subjenis | 50.000 | Deteksi 100%, termasuk kategori kritis |
| Replay, 1.500 sampel × 3 verifikasi | 4.500 | Deteksi 100%, negatif palsu 0%, positif palsu 0% |
| Kedaluwarsa dengan kontrol negatif | 5.000 | Deteksi 100% atas 2.451 payload kedaluwarsa; 0% positif palsu atas 2.549 kontrol |
| Kontrol negatif pemalsuan data | 2.500 | 0 payload sah ditolak keliru |
| Kontrol negatif pemalsuan tanda tangan | 500 | 0 payload sah ditolak keliru |
| Pemalsuan tanda tangan, 4 jenis | 4.000 | Penolakan 100% |

### Perbandingan terhadap sesi simulasi

| Metrik | Simulasi | Empiris | Target proposal |
|---|---:|---:|---:|
| Akurasi deteksi pemalsuan data | 78,14% | 100% | 79,2% |
| Deteksi kategori kritis | 54,17% | 100% | — |
| Laju deteksi replay | 92,21% | 100% | 95,8% |
| Laju negatif palsu replay | 0,161% | 0% | ≤ 0,1% |
| Laju penolakan pemalsuan tanda tangan | 97,08% | 100% | 97,0% |

Selisihnya bukan perbaikan sistem antara dua tanggal. Angka simulasi merupakan
keluaran laju terparameter di dalam harness, sedangkan angka empiris merupakan
perilaku sistem yang sebenarnya. Deteksi 100% pada pemalsuan data bersifat struktural:
setiap perubahan pada field yang ditandatangani merusak tanda tangan RSA-PSS, sehingga
tidak tersedia ruang bagi angka di bawah 100%. Kontrol negatif disertakan pada tiga skenario penolakan — 2.500 pada pemalsuan data,
500 pada pemalsuan tanda tangan, dan 2.549 pada kedaluwarsa. Dari 5.549 payload sah
tersebut, nol ditolak keliru. Tanpa kontrol negatif, detektor yang menolak segalanya
akan mencatat laju deteksi sempurna, sehingga kontrol inilah yang menjadikan angka
100% bermakna.

Kontrol negatif memakai generator acak terpisah, `random.Random(seed + 1)`, agar aliran
acak utama tidak tergeser. Sudah diverifikasi: alokasi ketujuh subjenis pemalsuan data
reproduksi identik terhadap run sebelum kontrol ditambahkan.

### Catatan membaca `empiris_waktu.csv`

Waktu deteksi pemalsuan data (0,879 ms) dan pemalsuan tanda tangan (0,671 ms) berada di bawah 1 ms karena
kedua jalur itu berhenti pada pemeriksaan kriptografis dan perbandingan payload.
Skenario replay (1,575 ms) dan kedaluwarsa (1,924 ms) sedikit lebih tinggi karena keduanya
menulis ke buku besar nonce berbasis SQLite, tetapi 99,6% dan 99,4% operasinya tetap di
bawah 20 ms. Metrik yang dibandingkan terhadap target proposal
20,0 ms adalah **waktu deteksi pemalsuan data**, sesuai definisi pada usulan penelitian.

## Lingkungan pengukuran

Ubuntu, Python 3.12.3, 2 vCPU pada 2,2 GHz, RAM 9,71 GB. Rincian per berkas kalibrasi
tersimpan pada `metadata.system_info`.

## Reproduksi

```bash
python3 data-penelitian/export_dataset_pengujian.py
python3 calibrate_performance.py --tier quick_check --output <path>.json
python3 data-penelitian/susun_ringkasan_kalibrasi.py

# pengukuran empiris (wajib root: kunci privat bermode 0640 root:www-data)
sudo venv/bin/python data-penelitian/harness_empiris.py \
     --operasi 50000 --replay 1500 --forgery 4000 --kedaluwarsa 5000
```

Skrip ekspor membuka basis data dalam mode baca saja dan tidak pernah menulis ke sumber.
Skrip kalibrasi **wajib** dijalankan dengan `--output` ke berkas terpisah; tanpa opsi itu
ia menimpa `data/calibration/multi_scenario_calibration.json` yang dimuat aplikasi produksi
saat start.

## Lisensi dan sitasi

Dataset ini **tidak** diterbitkan sebagai rekaman Zenodo tersendiri. Sejak versi 1.2.0 ia
menjadi bagian dari rekaman perangkat lunak, sehingga ikut terarsip dan tersitasi melalui
concept DOI [10.5281/zenodo.21271011](https://doi.org/10.5281/zenodo.21271011) beserta
version DOI rilis yang memuatnya.

Karena satu rekaman Zenodo hanya membawa satu pernyataan lisensi, seluruh isi arsip —
kode maupun data — berada di bawah lisensi MIT yang sama seperti perangkat lunaknya.

### Catatan kinerja jalur verifikasi

Pengukuran 4 September pagi sempat mencatat waktu jauh lebih besar pada skenario replay
(29,5 ms) dan kedaluwarsa (41,3 ms). Penelusuran menemukan penyebabnya bukan pada beban
kriptografi melainkan pada pola koneksi SQLite: setiap panggilan membuka dan menutup
koneksinya sendiri, dan di bawah WAL setiap `close()` memicu checkpoint ber-fsync.
Pembedahan per tahap mencatat `close()` 12,1 ms dan `commit()` 7,3 ms, sedangkan tahap
lain mendekati nol.

Perbaikannya menggabungkan dua hal yang harus dikerjakan bersamaan: koneksi dipakai ulang
per thread, dan `synchronous` diturunkan ke NORMAL. Salah satu saja tidak cukup — 19,195 ms
untuk buka-tutup, 7,345 ms bila hanya koneksi dipakai ulang, dan 0,087 ms bila keduanya
diterapkan. Setelah perbaikan, seluruh empat skenario berada di bawah 2 ms dan sekurangnya
99,4% operasi tiap skenario di bawah 20 ms.

Hitungan deteksi tidak terpengaruh perbaikan ini dan tetap reproduksi identik.
