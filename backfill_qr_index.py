#!/usr/bin/env python3
"""Bangun index pencarian record QR dari seluruh isi DATA_FOLDER.

Dijalankan sekali setelah pembaruan yang memperkenalkan tabel `qr_record_index`.
Sebelum skrip ini selesai, aplikasi tetap memakai pemindaian direktori, sehingga
menjalankannya tidak wajib untuk kebenaran — hanya untuk kinerja.

    ./venv/bin/python backfill_qr_index.py

Aman diulang: operasi bersifat idempoten (upsert per nama berkas).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as A  # noqa: E402


def main():
    data_dir = A.app.config['DATA_FOLDER']
    if not os.path.isdir(data_dir):
        print(f"DATA_FOLDER tidak ditemukan: {data_dir}")
        return 1

    print(f"Direktori data : {os.path.abspath(data_dir)}")
    print(f"Basis data     : {os.path.abspath(A.app.config['SECURITY_STATE_DB'])}")
    print("Memindai dan mengindeks... (sekali jalan)\n")

    mulai = time.time()

    def progress(total, gagal):
        laju = total / max(time.time() - mulai, 1e-9)
        print(f"  {total:>7} berkas terindeks | {gagal} rusak | {laju:,.0f} berkas/detik",
              flush=True)

    with A.app.app_context():
        total, gagal = A.backfill_qr_record_index(progress_callback=progress)

    durasi = time.time() - mulai
    print(f"\nSelesai: {total:,} berkas terindeks, {durasi:.1f} detik")
    print("Index kini otoritatif — pencarian record beralih dari pemindaian direktori.")
    if gagal:
        print(f"\nPeringatan: {gagal} berkas rusak atau kosong.")
        print("Berkas tersebut tetap diindeks tanpa isi agar klasifikasi verifikasi")
        print("tidak berubah, namun sebaiknya ditelusuri dan dibersihkan terpisah.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
