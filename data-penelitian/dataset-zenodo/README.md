# Dataset Pengujian Keamanan dan Kalibrasi Kinerja — QR Code Security System RSA-PSS

Dataset ini memuat data mentah dan ringkasan hasil pengujian keamanan serta kalibrasi
kinerja kriptografi dari *QR Code Security System RSA-PSS*. Mulai versi 1.2.0 dataset
disertakan langsung di dalam arsip rilis perangkat lunaknya, sehingga kode dan data
terarsip dalam satu rekaman Zenodo yang sama
(concept DOI [10.5281/zenodo.21271011](https://doi.org/10.5281/zenodo.21271011)).

Seluruh angka diekspor apa adanya dari basis data hasil pengujian sistem
(`data/testing/testing_results.db`), lalu **diverifikasi identik bit-per-bit**
terhadap sumbernya: 461.950 nilai dibandingkan, 0 selisih.

## Struktur

```
indeks_sesi.csv                        14 sesi pengujian beserta waktu dan status
ringkasan_metrik.json                  ringkasan skalar tiap sesi
deret-mentah/                          18 berkas CSV, satu baris per operasi
kalibrasi/
  kalibrasi_quick_check.json           tier 1.000 sampel
  kalibrasi_production.json            tier 10.000 sampel
  kalibrasi_validation.json            tier 100.000 sampel (kalibrasi 2026-07-21)
  kalibrasi_validation_20260820.json   tier 100.000 sampel (sesi sama, lihat catatan)
  ringkasan_kalibrasi_tiga_tingkat.csv tabel gabungan ketiga tier
.zenodo.json                           metadata rekaman Zenodo
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

## Lingkungan pengukuran

Ubuntu, Python 3.12.3, 2 vCPU pada 2,2 GHz, RAM 9,71 GB. Rincian per berkas kalibrasi
tersimpan pada `metadata.system_info`.

## Reproduksi

```bash
python3 data-penelitian/export_dataset_pengujian.py
python3 calibrate_performance.py --tier quick_check --output <path>.json
python3 data-penelitian/susun_ringkasan_kalibrasi.py
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
