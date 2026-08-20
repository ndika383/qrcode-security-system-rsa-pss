#!/usr/bin/env python3
"""Gabungkan tiga tier kalibrasi menjadi satu tabel ringkas yang dapat disitasi.

Membaca kalibrasi_quick_check.json (1.000 sampel), kalibrasi_production.json
(10.000), dan kalibrasi_validation.json (100.000), lalu menulis
ringkasan_kalibrasi_tiga_tingkat.csv.

Catatan: berkas tier validation berasal dari kalibrasi 2026-07-21 dan hanya
memuat rsa_pss_2048, sedangkan dua tier lain memuat rsa_pss_2048 dan
ecdsa_p256. Selisih cakupan itu dipertahankan apa adanya, tidak ditambal.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent / 'dataset-zenodo' / 'kalibrasi'
TIER = [
    ('quick_check', 'kalibrasi_quick_check.json', 'sesi_20260820'),
    ('production', 'kalibrasi_production.json', 'sesi_20260820'),
    ('validation', 'kalibrasi_validation_20260820.json', 'sesi_20260820'),
    ('validation', 'kalibrasi_validation.json', 'arsip_20260721'),
]
KOLOM = [
    'tier', 'kelompok', 'num_samples', 'calibration_date', 'algoritma', 'operasi',
    'mean_ms', 'std_ms', 'ci_lower_ms', 'ci_upper_ms', 'ci_width_ms',
    'relative_error_percent', 'samples',
]


def main() -> int:
    baris = []
    for tier, nama, kelompok in TIER:
        p = DIR / nama
        if not p.exists():
            print(f'  LEWAT: {nama} tidak ada')
            continue
        d = json.loads(p.read_text(encoding='utf-8'))
        meta = d.get('metadata', {})
        for alg, isi in d.get('benchmark_results', {}).items():
            if alg == '_metadata' or not isinstance(isi, dict):
                continue
            for operasi in ('signing', 'verification'):
                s = isi.get(operasi)
                if not isinstance(s, dict):
                    continue
                baris.append({
                    'tier': tier,
                    'kelompok': kelompok,
                    'num_samples': meta.get('num_samples'),
                    'calibration_date': meta.get('calibration_date'),
                    'algoritma': alg,
                    'operasi': operasi,
                    'mean_ms': s.get('mean'),
                    'std_ms': s.get('std'),
                    'ci_lower_ms': s.get('ci_lower'),
                    'ci_upper_ms': s.get('ci_upper'),
                    'ci_width_ms': s.get('ci_width'),
                    'relative_error_percent': s.get('relative_error_percent'),
                    'samples': s.get('samples'),
                })

    keluar = DIR / 'ringkasan_kalibrasi_tiga_tingkat.csv'
    with keluar.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=KOLOM)
        w.writeheader()
        w.writerows(baris)

    print(f'{keluar.name}: {len(baris)} baris\n')
    print(f"{'kelompok':<16}{'tier':<13}{'sampel':>9}  {'algoritma':<15}"
          f"{'operasi':<14}{'mean (ms)':>11}{'err %':>8}")
    print('-' * 88)
    for b in baris:
        print(f"{b['kelompok']:<16}{b['tier']:<13}{b['num_samples']:>9,}  {b['algoritma']:<15}"
              f"{b['operasi']:<14}{b['mean_ms']:>11.4f}{b['relative_error_percent']:>8.2f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
