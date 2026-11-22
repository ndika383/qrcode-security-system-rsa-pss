#!/usr/bin/env python3
"""Ukuran tanda tangan, envelope, dan versi QR Code untuk tiga skema tanda tangan.

Pelengkap kalibrasi_pembanding_skema.py (yang mengukur latensi). Dipakai untuk
Tabel 6 naskah JTIIK, menjawab permintaan reviewer agar RSA-PSS dibandingkan
langsung dengan ECDSA P-256 dan Ed25519 dari sisi ukuran QR Code.

Payload uji sengaja dibuat identik untuk ketiga skema dan lebih ringkas daripada
payload produksi, sehingga angka absolutnya TIDAK sebanding dengan Tabel 5.
Yang dibandingkan di sini adalah selisih antarskema pada payload yang sama.

Keluaran: dataset-zenodo/kalibrasi/ukuran_pembanding_skema.csv
"""
from __future__ import annotations

import base64
import csv
import json
from pathlib import Path

import qrcode
from Crypto.Hash import SHA256
from Crypto.PublicKey import ECC, RSA
from Crypto.Signature import DSS, eddsa, pss

DIR = Path(__file__).resolve().parent / 'dataset-zenodo' / 'kalibrasi'
DATA = {'nama': 'User 107', 'id': 'user_000107',
        'timestamp': '2026-09-07T08:59:20+07:00', 'nonce': '3f0f4ee309c90fbc'}
SER = json.dumps(DATA, sort_keys=True)


def envelope(sig: bytes, alg: str, salt_len: int | None) -> str:
    md = {'algorithm': alg}
    if salt_len is not None:
        md['salt_length'] = salt_len
    return json.dumps({'data': DATA, 'signature': base64.b64encode(sig).decode(),
                       'alg': alg, 'metadata': md}, separators=(',', ':'))


def qr_version(isi: str) -> int:
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=2, border=1)
    q.add_data(isi)
    q.make(fit=True)
    return q.version


def main() -> int:
    h = SHA256.new(SER.encode())
    rsa = RSA.generate(2048)
    p256 = ECC.generate(curve='P-256')
    ed = ECC.generate(curve='ed25519')

    skema = [
        ('rsa_pss_2048_slen8', pss.new(rsa, salt_bytes=8).sign(h), 8,
         len(rsa.publickey().export_key('DER'))),
        ('rsa_pss_2048_slen32', pss.new(rsa, salt_bytes=32).sign(h), 32,
         len(rsa.publickey().export_key('DER'))),
        ('ecdsa_p256', DSS.new(p256, 'fips-186-3').sign(h), None,
         len(p256.public_key().export_key(format='DER'))),
        ('ed25519', eddsa.new(ed, 'rfc8032').sign(SER.encode()), None,
         len(ed.public_key().export_key(format='DER'))),
    ]

    DIR.mkdir(parents=True, exist_ok=True)
    baris = []
    for nama, sig, slen, pk in skema:
        env = envelope(sig, nama, slen)
        baris.append({
            'algoritma': nama,
            'salt_bytes': slen if slen is not None else '',
            'signature_bytes': len(sig),
            'signature_base64_bytes': len(base64.b64encode(sig)),
            'envelope_json_bytes': len(env),
            'qr_version_envelope_tertanam': qr_version(env),
            'public_key_der_bytes': pk,
        })

    with (DIR / 'ukuran_pembanding_skema.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(baris[0].keys()))
        w.writeheader()
        w.writerows(baris)

    for b in baris:
        print(' '.join(f'{k}={v}' for k, v in b.items()))
    print(f'\nDitulis ke {DIR / "ukuran_pembanding_skema.csv"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
