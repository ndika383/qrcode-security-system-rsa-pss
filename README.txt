===================================================================
                SISTEM KEAMANAN QR CODE & TESTING
                Paket Deploy Linux Ubuntu 24.04 LTS
===================================================================

CARA MENJALANKAN DI UBUNTU:
---------------------------
1. Masuk ke direktori aplikasi, misalnya:
   cd /opt/qrcode

2. Beri izin eksekusi pada skrip:
   chmod +x setup_ubuntu.sh run_app.sh create_folders.sh

3. Jalankan setup pertama kali:
   ./setup_ubuntu.sh

4. Salin konfigurasi dan sesuaikan nilainya:
   cp .env.ubuntu.example .env
   nano .env

5. Jalankan aplikasi:
   ./run_app.sh

AKSES APLIKASI:
---------------
- Dashboard Utama: http://localhost:5000
- Dashboard Testing: http://localhost:5000/testing
- Scanner: http://localhost:5000/scanner

DEPLOY SEBAGAI SERVICE:
-----------------------
Contoh unit systemd tersedia di:
deploy/systemd/qrcode.service

Lihat panduan lengkap:
README_UBUNTU_24_04.md

CATATAN:
--------
- Folder "logs" berisi catatan aktivitas sistem.
- Folder "static/qr" berisi QR Code yang dihasilkan.
- Folder "data/testing" berisi database hasil pengujian otomatis.
- Virtual environment Windows tidak disalin. Ubuntu membuat venv baru dari requirements.txt.
