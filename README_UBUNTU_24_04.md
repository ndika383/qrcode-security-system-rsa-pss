# Deploy Ubuntu 24.04 LTS

Paket ini adalah salinan Linux dari sistem QR Code Security. Folder utama Windows tidak perlu diubah.

## 1. Pindahkan ke Server

Contoh lokasi production:

```bash
sudo mkdir -p /opt/qrcode
sudo rsync -a ./ /opt/qrcode/
sudo chown -R "$USER:$USER" /opt/qrcode
cd /opt/qrcode
```

## 2. Setup Pertama Kali

```bash
chmod +x setup_ubuntu.sh run_app.sh create_folders.sh
./setup_ubuntu.sh
```

Dependency sistem yang dipasang meliputi `libzbar0` untuk `pyzbar`, library OpenCV headless, Redis, Python venv, dan font DejaVu untuk grafik/screenshot.

Setelah `pip install`, skrip setup juga menjalankan import-check untuk dependency utama seperti Flask, PyCryptodome, OpenCV, pyzbar, pandas, matplotlib, psutil, scipy, dan Gunicorn. Jika ada library Python atau library sistem yang kurang, setup akan berhenti sebelum aplikasi dijalankan.

## 3. Konfigurasi

```bash
cp .env.ubuntu.example .env
nano .env
```

Minimal ubah:

```bash
SECRET_KEY=change-this-to-a-long-random-secret
AUTH_PASSWORD=change-this-password
BASE_URL=https://rsa-pss.com/
REQUIRE_HTTPS=True
TRUST_PROXY_HEADERS=True
HOST=127.0.0.1
```

Contoh membuat `SECRET_KEY` baru:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
```

`BASE_URL` adalah nilai yang masuk ke QR Code. Untuk verifikasi dari HP, nilai ini harus memakai domain publik yang bisa diakses dari internet.

## 4. Nginx dan HTTPS

Pastikan DNS domain sudah mengarah ke IP server:

```text
rsa-pss.com      A      IP_SERVER
www.rsa-pss.com  A      IP_SERVER
```

Install Nginx:

```bash
sudo apt install -y nginx
sudo cp deploy/nginx/rsa-pss.com.conf /etc/nginx/sites-available/rsa-pss.com
sudo ln -sf /etc/nginx/sites-available/rsa-pss.com /etc/nginx/sites-enabled/rsa-pss.com
sudo nginx -t
sudo systemctl reload nginx
```

Pasang SSL Let's Encrypt:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d rsa-pss.com -d www.rsa-pss.com
```

Setelah SSL aktif, pastikan `.env` berisi:

```bash
BASE_URL=https://rsa-pss.com/
REQUIRE_HTTPS=True
TRUST_PROXY_HEADERS=True
```

## 5. Jalankan Manual

```bash
./run_app.sh
```

Akses:

```text
https://rsa-pss.com
```

Jika menjalankan manual, biarkan terminal tetap terbuka. Untuk server online, gunakan service systemd pada langkah berikutnya.

## 6. Jalankan Sebagai Service

Unit contoh memakai path `/opt/qrcode`, user `www-data`, dan Gunicorn. Konfigurasi default memakai 1 worker dan 4 thread agar scheduler internal tidak berjalan dobel.

```bash
sudo chown -R www-data:www-data /opt/qrcode
sudo cp deploy/systemd/qrcode.service /etc/systemd/system/qrcode.service
sudo systemctl daemon-reload
sudo systemctl enable --now qrcode
sudo systemctl status qrcode
```

Cek aplikasi lokal di server:

```bash
curl -I http://127.0.0.1:5000
```

Cek melalui domain:

```bash
curl -I https://rsa-pss.com
```

Log service:

```bash
sudo journalctl -u qrcode -f
```

Jika firewall UFW aktif, buka akses web:

```bash
sudo ufw allow 'Nginx Full'
```

## 7. Verifikasi dari HP

QR yang dibuat setelah `BASE_URL=https://rsa-pss.com/` akan berisi URL seperti:

```text
https://rsa-pss.com/verify/....
```

QR lama yang masih berisi URL lokal perlu dibuat ulang jika ingin bisa diverifikasi dari luar jaringan lokal.

## 8. Folder Penting

- `logs/`: log aplikasi, generate, verifikasi, modifikasi.
- `static/qr/`: QR tunggal yang dihasilkan.
- `static/qr_massal/`: QR massal.
- `static/uploads/`: file upload sementara.
- `static/data/`: payload JSON QR.
- `data/testing/testing_results.db`: database pengujian.
- `requirements-windows.txt`: referensi dependency Windows lama.

## 9. Catatan Migrasi

- Virtualenv Windows tidak disalin karena tidak kompatibel dengan Ubuntu.
- `requirements.txt` sudah memakai `opencv-python-headless` untuk server Linux.
- Skrip Python yang sebelumnya menunjuk ke path absolut Windows sudah dibuat relatif terhadap direktori aplikasi.
- Aplikasi sudah diprioritaskan memakai `BASE_URL` saat membuat URL QR agar tidak kembali ke `localhost` atau IP lokal.
- Service production memakai Gunicorn melalui `wsgi.py`; jangan menaikkan `GUNICORN_WORKERS` di atas 1 kecuali scheduler internal dipisahkan.
