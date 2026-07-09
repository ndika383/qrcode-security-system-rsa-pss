@echo off
title QR Code Security System Launcher
color 0F
cd /d "%~dp0"

echo ===============================================================================
echo                     QR CODE SECURITY SYSTEM LAUNCHER
echo ===============================================================================
echo.

REM 1. Cek Python Installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python tidak terdeteksi di sistem Anda!
    echo Mohon install Python terlebih dahulu dari https://www.python.org/
    echo Pastikan mencentang opsi "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit
)

REM 2. Setup Virtual Environment (Otomatis)
if not exist "venv" (
    echo [INFO] Virtual environment belum ada. Membuat baru...
    python -m venv venv
    if %errorlevel% neq 0 (
        color 0C
        echo [ERROR] Gagal membuat virtual environment.
        pause
        exit
    )
)

REM 3. Cek & Install Dependencies (Otomatis perbaiki jika gagal sebelumnya)
echo [INFO] Memeriksa kelengkapan library...
venv\Scripts\python.exe -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Library belum lengkap atau corrupt. Menginstall ulang...
    venv\Scripts\python.exe -m pip install --upgrade pip --default-timeout=1000 -i https://pypi.tuna.tsinghua.edu.cn/simple
    venv\Scripts\python.exe -m pip install --upgrade setuptools wheel --default-timeout=1000 -i https://pypi.tuna.tsinghua.edu.cn/simple
    venv\Scripts\python.exe -m pip install -r requirements.txt --default-timeout=1000 -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        color 0C
        echo [ERROR] Gagal menginstall library. Cek koneksi internet Anda.
        pause
        exit
    )
    echo [OK] Library berhasil diinstall.
) else (
    echo [OK] Library sudah terinstall.
)

REM 4. Jalankan Aplikasi
cls
echo ===============================================================================
echo                     MEMULAI QR CODE SECURITY SYSTEM...
echo ===============================================================================
echo.
echo [INFO] Server sedang diinisialisasi. Proses ini mungkin memakan waktu beberapa saat.
echo [INFO] Mohon tunggu hingga Anda melihat pesan "Running on http://...".
echo.
echo [AKSES] Setelah server berjalan, buka browser dan kunjungi: http://localhost:5000
echo.
echo [INFO] Browser akan terbuka secara otomatis setelah 5 detik.
start /b "" cmd /c "timeout /t 5 >nul & start http://localhost:5000"
venv\Scripts\python.exe app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Aplikasi berhenti dengan error.
    pause
)