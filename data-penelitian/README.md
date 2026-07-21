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
