#!/usr/bin/env python3
"""Gabungkan halaman sampul dengan PDF isi hasil ekspor Word.

Buku Panduan Pengguna terdiri atas dua bagian:

  1. sampul_buku_panduan.pdf  - halaman sampul (1 halaman, dibuat terpisah)
  2. PDF isi                  - hasil "Save as PDF" dari
                                Word/Buku_Panduan_Pengguna_QR_Code_Security_System.docx

Skrip ini menyatukan keduanya menjadi "Buku Panduan Pengguna.pdf".

Pemakaian:

    python3 gabung_sampul_pdf.py isi_hasil_word.pdf

Berkas lama otomatis dicadangkan ke "Buku Panduan Pengguna.bak-<tanggal>.pdf".
"""
import shutil
import sys
from datetime import date
from pathlib import Path

from pypdf import PdfReader, PdfWriter

DOCS = Path(__file__).resolve().parent
COVER = DOCS / "sampul_buku_panduan.pdf"
OUTPUT = DOCS / "Buku Panduan Pengguna.pdf"


def main():
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python3 gabung_sampul_pdf.py <pdf-isi-dari-word>")
    body = Path(sys.argv[1])
    for path in (COVER, body):
        if not path.is_file():
            sys.exit("Berkas tidak ditemukan: %s" % path)

    writer = PdfWriter()
    writer.append(str(COVER))
    writer.append(str(body))

    if OUTPUT.exists():
        backup = OUTPUT.with_name("Buku Panduan Pengguna.bak-%s.pdf" % date.today().strftime("%Y%m%d"))
        shutil.copy2(OUTPUT, backup)
        print("cadangan  :", backup.name)

    with open(OUTPUT, "wb") as handle:
        writer.write(handle)
    print("sampul    : 1 halaman")
    print("isi       : %d halaman" % len(PdfReader(str(body)).pages))
    print("hasil     : %s (%d halaman)" % (OUTPUT.name, len(PdfReader(str(OUTPUT)).pages)))


if __name__ == "__main__":
    main()
