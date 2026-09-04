# Data Penelitian

Folder ini berisi data hasil pengukuran/eksperimen dari sistem
QR Code Security System (RSA-PSS) untuk keperluan penelitian dan reprodusibilitas.

## Berkas

### `multi_scenario_calibration.json`
Hasil kalibrasi performa operasi kriptografi (signing & verification) yang
diukur langsung pada mesin server produksi.

Struktur:
- `metadata` — tanggal kalibrasi, jumlah sampel, tier, dan informasi sistem
  (CPU, RAM, OS, versi Python) tempat pengukuran dilakukan.
- `benchmark_results` — per algoritma (mis. `rsa_pss_2048`), berisi statistik
  `signing` dan `verification`: `mean`, `std`, serta 95% confidence interval
  (`ci_lower`, `ci_upper`) dalam milidetik.

Data dihasilkan dari halaman kalibrasi aplikasi (`/testing/calibration`)
menggunakan `calibrate_performance.py`.

### `harness_empiris.py`
Harness pengukuran empiris skenario keamanan, ditambahkan 3 September 2026 sebagai
kegiatan 2 pada Tabel 16 Laporan Kemajuan.

Berbeda dari `modules/testing_controller.py` yang membangkitkan hasil deteksi dari
laju terparameter, harness ini benar-benar memodifikasi payload lalu memanggil
verifikasi RSA-PSS dan `classify_qr_verification()` milik aplikasi. Tidak ada satu
pun keputusan deteksi yang diundi.

Empat skenario: pemalsuan data tujuh subjenis, replay dengan verifikasi berulang,
masa berlaku, dan pemalsuan tanda tangan empat jenis. Ketiga skenario penolakan
disertai kontrol negatif berupa payload sah yang wajib diterima, sehingga laju
deteksi tinggi tidak dapat berasal dari detektor yang menolak segalanya.

Kontrol negatif memakai generator acak terpisah (`random.Random(seed + 1)`). Ini
disengaja: menambah operasi pada aliran acak utama akan menggeser alokasi subjenis
dan mengubah angka yang sudah dikutip di naskah dan laporan. Dengan pemisahan ini,
alokasi subjenis tetap reproduksi bit-per-bit terhadap run sebelum kontrol negatif
ditambahkan — sudah diverifikasi dengan membandingkan ketujuh subjenis sebelum dan
sesudah penyuntingan.

Isolasi bukti: basis data status keamanan diarahkan ke berkas sementara sehingga
buku besar nonce produksi tidak tersentuh, dan tidak ada penulisan ke
`data/testing/testing_results.db` maupun berkas log produksi.

```bash
sudo venv/bin/python data-penelitian/harness_empiris.py \
     --operasi 50000 --replay 1500 --forgery 4000 --kedaluwarsa 5000 \
     --kontrol-tampering 2500 --kontrol-forgery 500 --seed 20260824
```

Wajib dijalankan sebagai root karena kunci privat bermode 0640 `root:www-data`.
Keluarannya tersimpan di `dataset-zenodo/empiris/`.

**Sifat reproduksi.** Hitungan deteksi bersifat deterministik pada seed yang sama dan
terverifikasi identik pada dua run berturut-turut. Lajunya bahkan tidak bergantung
pada seed: pada seed berbeda alokasi subjenis bergeser, tetapi seluruh laju tetap
100% deteksi dan 0% negatif/positif palsu, karena capaian itu struktural — setiap
perubahan field tertandatangani merusak digest SHA-256. Yang **berubah tiap run**
hanyalah statistik waktu, sebab diukur dengan `time.perf_counter()` terhadap jam
dinding.

### `uji_penguatan_validasi_semantik.py`
Uji regresi 12 kasus atas penguatan lapisan validasi semantik (kegiatan 1 pada
Tabel 16): toleransi drift timestamp 300 detik, penegakan timestamp monotonik per
nonce, dan validasi struktur payload.

Empat kasus pertama adalah uji regresi yang memastikan QR sah berumur 0 sampai 6
hari tetap diterima. Sisanya menguji jalur deteksi baru dan memastikan deteksi
replay, kedaluwarsa, serta pemalsuan data tidak mengalami kemunduran.

Dijalankan terisolasi seperti harness di atas dan tidak menyentuh basis data produksi.
