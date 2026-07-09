# QR Code Security System RSA-PSS

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21271012.svg)](https://doi.org/10.5281/zenodo.21271012)

Sistem ini adalah aplikasi Flask untuk membuat, memindai, dan memverifikasi QR Code berbasis tanda tangan digital RSA-PSS/ECDSA. Aplikasi menyertakan dashboard, log audit, pengujian keamanan, deteksi replay/tampering, dan panduan deployment Ubuntu 24.04.

## Fitur Utama

- Generate QR Code tunggal dan massal dari data terstruktur.
- Verifikasi QR Code melalui scanner USB, kamera perangkat, atau endpoint langsung.
- Validasi tanda tangan digital, nonce, timestamp, dan status replay.
- Dashboard log generate, verifikasi, modifikasi, benchmark, dan testing.
- Paket deployment Ubuntu dengan Nginx, Gunicorn, Redis, dan systemd.

## Menjalankan di Ubuntu

```bash
chmod +x setup_ubuntu.sh run_app.sh create_folders.sh
./setup_ubuntu.sh
cp .env.ubuntu.example .env
nano .env
./run_app.sh
```

Panduan lengkap tersedia di [README_UBUNTU_24_04.md](README_UBUNTU_24_04.md).

## Keamanan Sebelum Publikasi

Jangan commit file runtime seperti `.env`, `rsa_key.pem`, `ecdsa_key.pem`, folder `logs/`, folder `data/`, virtual environment, database lokal, dan hasil QR yang dihasilkan aplikasi. File-file tersebut sudah masuk `.gitignore`.

Sebelum deploy produksi, ganti minimal:

- `SECRET_KEY`
- `AUTH_PASSWORD`
- `BASE_URL`
- private key RSA/ECDSA produksi

## Sitasi (DOI Zenodo)

Perangkat lunak ini diarsipkan di Zenodo dengan DOI: **[10.5281/zenodo.21271012](https://doi.org/10.5281/zenodo.21271012)**

Contoh sitasi:

> Slameto, A. A., Sutanto, Y., & Kurniawan, H. (2026). *QR Code Security System RSA-PSS* (v1.0.0). Zenodo. https://doi.org/10.5281/zenodo.21271012

Metadata sitasi lengkap tersedia di [CITATION.cff](CITATION.cff); konfigurasi arsip Zenodo di [.zenodo.json](.zenodo.json).

## Struktur Penting

- `app.py`: aplikasi Flask utama.
- `routes/`: blueprint route pengujian.
- `modules/`: modul testing, metrik, dan skenario.
- `templates/`: halaman HTML aplikasi.
- `static/`: aset CSS, JS, vendor, dan grafik statis.
- `deploy/`: contoh konfigurasi Nginx dan systemd.
- `dokumen/`: dokumentasi teknis dan panduan operasional.
- `testing/`: data dan ringkasan pengujian keamanan.
