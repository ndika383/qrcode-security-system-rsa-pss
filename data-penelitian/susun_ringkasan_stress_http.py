#!/usr/bin/env python3
"""Susun ringkasan pengujian real HTTP stress test menjadi tabel CSV.

Menghasilkan tiga berkas di dataset-zenodo/stress-http/:

  stress_http_ringkasan.csv     satu baris per sesi
  stress_http_tahap.csv         satu baris per tahap konkurensi
  stress_http_vs_inprocess.csv  perbandingan terhadap stress test in-process

Kolom `kesahihan` menandai sesi yang tidak layak dipakai sebagai hasil
pengukuran. Sesi dengan laju kesalahan 100 persen mencatat status HTTP 0, yang
berarti tidak ada respons sama sekali, sehingga angka latensinya hanyalah waktu
sampai timeout tercapai dan bukan latensi layanan.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

BASIS = Path(__file__).resolve().parent / 'dataset-zenodo'
SUMBER = BASIS / 'ringkasan_metrik.json'
KELUAR = BASIS / 'stress-http'


def kesahihan(laju_error: float, sukses: int) -> str:
    if laju_error >= 100.0:
        return 'gagal_total'
    if laju_error > 50.0:
        return 'sebagian_besar_gagal'
    if sukses < 30:
        return 'sah_sampel_kecil'
    return 'sah'


def main() -> int:
    data = json.loads(SUMBER.read_text(encoding='utf-8'))['sesi']
    KELUAR.mkdir(parents=True, exist_ok=True)

    sesi_http = [(sid, s) for sid, s in data.items()
                 if s['test_type'] == 'real_http_stress_test']
    sesi_http.sort(key=lambda kv: kv[1]['start_time'])

    # ---- 1. ringkasan per sesi ----------------------------------------
    baris = []
    for i, (sid, s) in enumerate(sesi_http, 1):
        r = s['ringkasan_hasil']
        st = r.get('overall_stats', {})
        err = r.get('overall_error_rate', 0.0)
        baris.append({
            'sesi': i,
            'session_id': sid,
            'waktu_mulai': s['start_time'],
            'base_url': r.get('base_url'),
            'target_endpoint': r.get('target_endpoint'),
            'timeout_detik': r.get('request_timeout_seconds'),
            'permintaan': s['total_operations'],
            'sukses': r.get('successful_operations'),
            'gagal': r.get('failed_operations'),
            'laju_kesalahan_persen': err,
            'throughput_ops_per_detik': r.get('throughput'),
            'laju_permintaan_ditawarkan_per_detik': r.get('offered_load'),
            'laju_dibatasi_rate_limit_per_detik': r.get('rate_limited_request_rate'),
            'mean_detik': st.get('mean_ms', 0) / 1000,
            'min_detik': st.get('min_ms', 0) / 1000,
            'p50_detik': st.get('p50_ms', 0) / 1000,
            'p90_detik': st.get('p90_ms', 0) / 1000,
            'p95_detik': st.get('p95_ms', 0) / 1000,
            'p99_detik': r.get('overall_p99_response_time'),
            'max_detik': st.get('max_ms', 0) / 1000,
            'stddev_detik': st.get('stddev_ms', 0) / 1000,
            'titik_optimal_pengguna': r.get('optimal_user_count'),
            'status_http': json.dumps(r.get('http_status_counts', {}), sort_keys=True),
            'workflow_sukses': (r.get('workflow_counts') or {}).get('workflow_success'),
            'kesahihan': kesahihan(err, r.get('successful_operations') or 0),
        })

    tulis(KELUAR / 'stress_http_ringkasan.csv', baris)

    # ---- 2. rincian per tahap konkurensi ------------------------------
    tahap = []
    for i, (sid, s) in enumerate(sesi_http, 1):
        for t in s['ringkasan_hasil'].get('concurrent_tests', []):
            galat = t.get('errors') or {}
            dominan = max(galat.items(), key=lambda kv: kv[1])[0] if galat else ''
            tahap.append({
                'sesi': i,
                'session_id': sid,
                'pengguna_serentak': t.get('user_count'),
                'target_endpoint': t.get('target_endpoint'),
                'permintaan': t.get('operations'),
                'sukses': t.get('success_count'),
                'gagal': t.get('error_count'),
                'timeout': t.get('timeout_count'),
                'laju_kesalahan_persen': t.get('error_rate'),
                'laju_timeout_persen': t.get('timeout_rate'),
                'throughput_ops_per_detik': t.get('throughput'),
                'laju_permintaan_per_detik': t.get('request_rate'),
                'mean_detik': t.get('avg_response_time'),
                'p95_detik': t.get('p95_response_time'),
                'p99_detik': t.get('p99_response_time'),
                'max_detik': t.get('max_response_time'),
                'cpu_rerata_persen': t.get('avg_cpu_usage'),
                'memori_rerata_mb': t.get('avg_memory_usage'),
                'galat_dominan': dominan,
            })

    tulis(KELUAR / 'stress_http_tahap.csv', tahap)

    # ---- 3. perbandingan terhadap stress test in-process --------------
    ip = next((s['ringkasan_hasil'] for s in data.values()
               if s['test_type'] == 'stress_test'), None)
    banding = []
    if ip:
        ips = ip.get('overall_stats', {})
        acuan = {
            'mean_detik': ips.get('mean_ms', 0) / 1000,
            'p95_detik': ips.get('p95_ms', 0) / 1000,
            'p99_detik': ip.get('overall_p99_response_time'),
            'throughput_ops_per_detik': ip.get('throughput'),
            'laju_kesalahan_persen': ip.get('overall_error_rate'),
        }
        # hanya sesi yang sah yang layak dibandingkan
        for b in baris:
            if b['kesahihan'].startswith('gagal') or b['kesahihan'] == 'sebagian_besar_gagal':
                continue
            for metrik, nilai_ip in acuan.items():
                nilai_http = b[metrik]
                if metrik == 'throughput_ops_per_detik':
                    rasio = (nilai_ip / nilai_http) if nilai_http else None
                    arah = 'in-process lebih tinggi'
                elif metrik == 'laju_kesalahan_persen':
                    rasio = None
                    arah = '-'
                else:
                    rasio = (nilai_http / nilai_ip) if nilai_ip else None
                    arah = 'HTTP nyata lebih lambat'
                banding.append({
                    'sesi': b['sesi'],
                    'target_endpoint': b['target_endpoint'],
                    'metrik': metrik,
                    'in_process': nilai_ip,
                    'http_nyata': nilai_http,
                    'rasio': round(rasio, 3) if rasio is not None else '',
                    'arah': arah,
                })

    tulis(KELUAR / 'stress_http_vs_inprocess.csv', banding)
    return 0


def tulis(path: Path, baris: list[dict]) -> None:
    if not baris:
        print(f'  LEWAT {path.name}: tidak ada baris')
        return
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(baris[0]))
        w.writeheader()
        w.writerows(baris)
    print(f'  {path.name}: {len(baris)} baris')


if __name__ == '__main__':
    raise SystemExit(main())
