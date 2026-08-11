#!/usr/bin/env python3
"""Bangun ulang file PNG QR yang terhapus cleanup dari payload verifikasi asli.

QR hanya memuat URL `{BASE_URL}v/{token}`, dan token itu adalah nama file di
data/verify_payloads. Jadi selama payload masih ada, PNG bisa dipulihkan persis
seperti aslinya lengkap dengan signature asli, tanpa menandatangani ulang.

Nama file PNG mengikuti nama file record di static/data
(qr_<id>_<hex>.json -> qr_<id>_<hex>.png), dicocokkan lewat nonce.

Contoh:
    python3 scripts/restore_qr_images.py --dry-run
    python3 scripts/restore_qr_images.py --workers 8
"""

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_DIR = os.path.join(BASE_DIR, 'data', 'verify_payloads')
DATA_DIR = os.path.join(BASE_DIR, 'static', 'data')
QR_TUNGGAL_DIR = os.path.join(BASE_DIR, 'static', 'qr')
QR_MASSAL_DIR = os.path.join(BASE_DIR, 'static', 'qr_massal')

DEFAULT_BASE_URL = os.environ.get('BASE_URL', 'https://rsa-pss.com/')


def iter_payload_files():
    for root, _, files in os.walk(PAYLOAD_DIR):
        for filename in files:
            if filename.endswith('.json'):
                yield os.path.join(root, filename)


def read_payload_key(path):
    """Kembalikan (nonce, token) dari satu file payload."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            record = json.load(f)
    except Exception:
        return None

    token = record.get('token') or os.path.basename(path)[:-5]
    data = (record.get('payload') or {}).get('data') or {}
    nonce = data.get('nonce')
    if not nonce or not token:
        return None
    return nonce, token


def build_nonce_to_token(workers):
    """Index nonce -> token dari seluruh payload yang masih tersimpan."""
    paths = list(iter_payload_files())
    print(f'Membaca {len(paths)} payload verifikasi...', flush=True)

    mapping = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, result in enumerate(pool.map(read_payload_key, paths, chunksize=500), start=1):
            if result:
                mapping[result[0]] = result[1]
            if i % 25000 == 0:
                print(f'  ...{i} payload dibaca', flush=True)

    print(f'Index nonce siap: {len(mapping)} entri.', flush=True)
    return mapping


def render_qr(job):
    """Tulis satu PNG. job = (url, target_path)."""
    url, target_path = job
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_Q,
            box_size=2,
            border=1
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white', contrast=1.3)
        img.save(target_path, optimize=True, quality=85)
        return True
    except Exception as e:
        print(f'GAGAL {target_path}: {e}', file=sys.stderr, flush=True)
        return False


def collect_jobs(nonce_to_token, base_url, target_dir, overwrite):
    """Pasangkan record di static/data dengan token, hasilkan daftar job render."""
    jobs = []
    missing_token = 0
    skipped = 0

    with os.scandir(DATA_DIR) as entries:
        for entry in entries:
            if not entry.is_file() or not entry.name.endswith('.json'):
                continue

            target_path = os.path.join(target_dir, entry.name[:-5] + '.png')
            if not overwrite and os.path.exists(target_path):
                skipped += 1
                continue

            try:
                with open(entry.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                continue

            token = nonce_to_token.get(data.get('nonce'))
            if not token:
                missing_token += 1
                continue

            jobs.append((f'{base_url}v/{token}', target_path))

    return jobs, missing_token, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help='Base URL verifikasi, harus sama dengan saat QR dibuat')
    parser.add_argument('--target-dir', default=QR_MASSAL_DIR,
                        help='Folder tujuan PNG (default static/qr_massal)')
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 4)
    parser.add_argument('--overwrite', action='store_true',
                        help='Tulis ulang PNG yang sudah ada')
    parser.add_argument('--limit', type=int, default=0,
                        help='Batasi jumlah PNG yang dirender (0 = semua)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Hanya laporkan berapa yang bisa dipulihkan')
    args = parser.parse_args()

    base_url = args.base_url if args.base_url.endswith('/') else args.base_url + '/'
    os.makedirs(args.target_dir, exist_ok=True)

    nonce_to_token = build_nonce_to_token(args.workers)
    jobs, missing_token, skipped = collect_jobs(
        nonce_to_token, base_url, args.target_dir, args.overwrite
    )

    if args.limit:
        jobs = jobs[:args.limit]

    print(f'Siap dipulihkan : {len(jobs)}', flush=True)
    print(f'Payload hilang  : {missing_token}', flush=True)
    print(f'Sudah ada       : {skipped}', flush=True)

    if args.dry_run or not jobs:
        return 0

    print(f'Merender PNG ke {args.target_dir} dengan {args.workers} worker...', flush=True)
    ok = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, result in enumerate(pool.map(render_qr, jobs, chunksize=200), start=1):
            if result:
                ok += 1
            if i % 10000 == 0:
                print(f'  ...{i}/{len(jobs)} selesai', flush=True)

    print(f'Selesai: {ok}/{len(jobs)} PNG dipulihkan.', flush=True)
    return 0 if ok == len(jobs) else 1


if __name__ == '__main__':
    sys.exit(main())
