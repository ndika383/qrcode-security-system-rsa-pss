#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifikator mandiri QR Code Security System (RSA-PSS salt 8 byte).

Alat ini memeriksa keabsahan tanda tangan digital pada payload QR Code tanpa
bergantung pada kode aplikasi maupun basis data server. Yang dibutuhkan hanya
payload bertanda tangan dan kunci publik penerbit. Dengan begitu pihak ketiga
dapat memeriksa ulang klaim keabsahan secara independen.

Kunci publik dapat diambil sekali dari endpoint distribusi kunci:

    curl -o kunci_publik.pem https://rsa-pss.com/.well-known/qr-public-key

Sesudah kunci tersimpan, pemeriksaan tanda tangan berjalan sepenuhnya luring.

Contoh pemakaian:

    python3 verifikator_mandiri.py payload.json --kunci kunci_publik.pem
    cat payload.json | python3 verifikator_mandiri.py - --kunci kunci_publik.pem

BATAS KEMAMPUAN. Alat ini memeriksa integritas kriptografis, bukan keberlakuan
operasional. Tiga hal berikut memerlukan status sisi server dan sengaja tidak
diklaim di sini: deteksi pemakaian ulang (replay) yang menuntut buku besar
nonce, keurutan waktu antaridentitas, dan pencabutan kunci. Payload yang
dinyatakan SAH oleh alat ini berarti tanda tangannya sahih dan datanya utuh;
statusnya sebagai kredensial yang masih berlaku tetap ditentukan server.
"""
import argparse
import base64
import json
import sys
from datetime import datetime, timezone

try:
    from Crypto.PublicKey import RSA, ECC
    from Crypto.Signature import pss, DSS
    from Crypto.Hash import SHA256
except ImportError:
    sys.exit("Butuh pycryptodome. Pasang dengan: pip install pycryptodome")

SALT_BYTES = 8            # Adaptasi inti penelitian: salt 8 byte, bukan 32 byte
MAX_AGE_SECONDS = 604800  # Masa berlaku payload pada konfigurasi produksi: 7 hari


def muat_payload(sumber):
    """Baca payload dari berkas, atau dari stdin bila sumber bernilai '-'."""
    teks = sys.stdin.read() if sumber == '-' else open(sumber, encoding='utf-8').read()
    payload = json.loads(teks)
    # Berkas simpanan sisi server membungkus payload di dalam field 'payload'.
    if 'payload' in payload and 'data' not in payload:
        payload = payload['payload']
    return payload


def muat_kunci(path):
    """Muat kunci publik PEM; bedakan RSA dan ECC berdasarkan isi berkas."""
    isi = open(path, 'rb').read()
    try:
        return RSA.import_key(isi), 'RSA'
    except (ValueError, IndexError, TypeError):
        return ECC.import_key(isi), 'ECDSA'


def periksa_tanda_tangan(payload, kunci, jenis_kunci):
    """Periksa tanda tangan atas blok data yang dikanonikalisasi.

    Kanonikalisasi harus sama persis dengan sisi penerbit, yaitu
    json.dumps(data, sort_keys=True) memakai pemisah bawaan. Perbedaan satu
    spasi pun membuat digest berbeda dan tanda tangan tampak tidak sah.
    """
    data = payload['data']
    alg = payload.get('alg', 'RSA')
    if alg != jenis_kunci:
        return False, f"Algoritma payload {alg} tidak cocok dengan kunci {jenis_kunci}"

    serialized = json.dumps(data, sort_keys=True)
    digest = SHA256.new(serialized.encode('utf-8'))
    signature = base64.b64decode(payload['signature'])

    verifier = (pss.new(kunci, salt_bytes=SALT_BYTES) if alg == 'RSA'
                else DSS.new(kunci, 'fips-186-3'))
    try:
        verifier.verify(digest, signature)
        return True, "Tanda tangan sahih"
    except (ValueError, TypeError) as e:
        return False, f"Tanda tangan tidak sah: {e}"


def periksa_umur(payload):
    """Hitung umur payload terhadap masa berlaku produksi."""
    stempel = payload.get('data', {}).get('timestamp')
    if not stempel:
        return None, "Tidak ada field timestamp"
    try:
        terbit = datetime.fromisoformat(stempel)
    except ValueError:
        return None, f"Format timestamp tidak dikenali: {stempel}"
    if terbit.tzinfo is None:
        terbit = terbit.replace(tzinfo=timezone.utc)
    umur = (datetime.now(timezone.utc) - terbit).total_seconds()
    return umur, ("dalam masa berlaku" if umur <= MAX_AGE_SECONDS else "melewati masa berlaku")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('payload', help="Berkas payload JSON, atau '-' untuk stdin")
    p.add_argument('--kunci', required=True, help='Berkas kunci publik PEM')
    p.add_argument('--json', action='store_true', help='Keluarkan hasil sebagai JSON')
    args = p.parse_args()

    payload = muat_payload(args.payload)
    kunci, jenis = muat_kunci(args.kunci)
    sah, pesan = periksa_tanda_tangan(payload, kunci, jenis)
    umur, ket_umur = periksa_umur(payload)

    data = payload.get('data', {})
    hasil = {
        'tanda_tangan_sah': sah,
        'pesan': pesan,
        'algoritma': payload.get('alg', 'RSA'),
        'kid': payload.get('kid'),
        'nama': data.get('nama'),
        'id': data.get('id'),
        'timestamp': data.get('timestamp'),
        'umur_detik': None if umur is None else round(umur, 1),
        'keterangan_umur': ket_umur,
        'catatan': 'Replay dan pencabutan kunci tidak diperiksa; keduanya menuntut status sisi server.'
    }

    if args.json:
        print(json.dumps(hasil, indent=2, ensure_ascii=False))
    else:
        print("Tanda tangan : %s" % ('SAH' if sah else 'TIDAK SAH'))
        print("Keterangan   : %s" % pesan)
        print("Algoritma    : %s" % hasil['algoritma'])
        if hasil['kid']:
            print("Kid          : %s" % hasil['kid'])
        print("Identitas    : %s (%s)" % (hasil['nama'], hasil['id']))
        print("Timestamp    : %s (%s)" % (hasil['timestamp'], ket_umur))
        print("Catatan      : %s" % hasil['catatan'])

    return 0 if sah else 1


if __name__ == '__main__':
    sys.exit(main())
