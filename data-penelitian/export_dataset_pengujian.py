#!/usr/bin/env python3
"""Ekspor isi data/testing/testing_results.db menjadi dataset CSV/JSON yang dapat disitasi.

Basis data asli berukuran ~135 MB, jauh di atas batas 100 MB per berkas GitHub,
sehingga tidak pernah ikut terarsip ke rekaman Zenodo. Sebagian besar ukuran itu
berasal dari tabel `test_metrics` yang menyimpan satu baris per operasi dengan
`metric_name` ber-indeks (`signing_time_0`, `signing_time_1`, ...), menghasilkan
221.514 nama metrik unik. Deret angka yang sama sudah tersimpan utuh sebagai array
di dalam kolom `results_json` pada tabel `test_sessions`, jadi ekspor ini membaca
dari sana: hasilnya identik tetapi ukurannya jauh lebih kecil.

Basis data dibuka read-only. Skrip ini tidak pernah menulis ke sumber.

Pemakaian:
    python3 data-penelitian/export_dataset_pengujian.py [--db PATH] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Kolom array mentah yang diekspor jadi CSV tersendiri, per jenis pengujian.
DERET_MENTAH = {
    'normal_operations': ['signing_times', 'verification_times'],
    'replay_attack': ['detection_times', 'detection_latency_ms'],
    'data_tampering': ['detection_times'],
    'signature_forgery': ['verification_times'],
    'stress_test': ['response_times'],
    'real_http_stress_test': ['response_times'],
}

# Satuan tiap deret, supaya dataset terbaca tanpa menebak.
SATUAN = {
    'signing_times': 'detik',
    'verification_times': 'detik',
    'detection_times': 'detik',
    'detection_latency_ms': 'milidetik',
    'response_times': 'detik',
}


def buka_readonly(db_path: Path) -> tuple[sqlite3.Connection, Path | None]:
    """Buka DB tanpa menyentuh berkas asli.

    Mode `?mode=ro` masih gagal bila SQLite merasa perlu memulihkan journal,
    jadi bila itu terjadi kita bekerja di atas salinan sementara.
    """
    try:
        con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        con.execute('select count(*) from test_sessions').fetchone()
        return con, None
    except sqlite3.OperationalError:
        tmp = Path(tempfile.mkdtemp(prefix='ekspor_dataset_')) / db_path.name
        shutil.copy2(db_path, tmp)
        return sqlite3.connect(tmp), tmp.parent


def skalar_saja(hasil: dict) -> dict:
    """Ambil ringkasan: buang array panjang, sisakan skalar dan dict kecil."""
    ringkas = {}
    for k, v in hasil.items():
        if isinstance(v, list):
            if len(v) <= 100:          # list pendek (mis. concurrent_tests) tetap berguna
                ringkas[k] = v
            else:
                ringkas[f'{k}__jumlah_elemen'] = len(v)
        else:
            ringkas[k] = v
    return ringkas


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--db', default='data/testing/testing_results.db')
    p.add_argument('--out', default='data-penelitian/dataset-zenodo')
    args = p.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f'ERROR: basis data tidak ditemukan: {db_path}', file=sys.stderr)
        return 1

    out = Path(args.out).resolve()
    (out / 'deret-mentah').mkdir(parents=True, exist_ok=True)

    con, tmpdir = buka_readonly(db_path)
    con.row_factory = sqlite3.Row

    sesi = list(con.execute('select * from test_sessions order by start_time'))
    print(f'Membaca {len(sesi)} sesi dari {db_path.name}\n')

    indeks_baris = []
    ringkasan = {}
    total_nilai = 0

    for r in sesi:
        sid = r['session_id']
        try:
            hasil = json.loads(r['results_json'] or '{}')
        except json.JSONDecodeError:
            hasil = {}

        indeks_baris.append({
            'session_id': sid,
            'test_type': r['test_type'],
            'test_name': r['test_name'],
            'start_time': r['start_time'],
            'end_time': r['end_time'],
            'status': r['status'],
            'total_operations': r['total_operations'],
            'completed_operations': r['completed_operations'],
        })
        ringkasan[sid] = {
            'test_type': r['test_type'],
            'test_name': r['test_name'],
            'start_time': r['start_time'],
            'end_time': r['end_time'],
            'total_operations': r['total_operations'],
            'ringkasan_hasil': skalar_saja(hasil),
        }

        for nama_deret in DERET_MENTAH.get(r['test_type'], []):
            deret = hasil.get(nama_deret)
            if not isinstance(deret, list) or not deret:
                continue
            berkas = out / 'deret-mentah' / f'{sid}__{nama_deret}.csv'
            with berkas.open('w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['indeks_operasi', 'nilai', 'satuan'])
                satuan = SATUAN.get(nama_deret, '')
                for i, nilai in enumerate(deret):
                    w.writerow([i, repr(float(nilai)), satuan])
            total_nilai += len(deret)
            print(f'  {berkas.name}  ({len(deret):,} nilai)')

    with (out / 'indeks_sesi.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(indeks_baris[0]))
        w.writeheader()
        w.writerows(indeks_baris)

    with (out / 'ringkasan_metrik.json').open('w', encoding='utf-8') as f:
        json.dump({
            'dibuat': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'sumber': db_path.name,
            'jumlah_sesi': len(sesi),
            'sesi': ringkasan,
        }, f, indent=2, ensure_ascii=False)

    con.close()
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f'\nindeks_sesi.csv       : {len(indeks_baris)} sesi')
    print(f'ringkasan_metrik.json : ringkasan {len(ringkasan)} sesi')
    print(f'deret-mentah/         : {total_nilai:,} nilai terukur')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
