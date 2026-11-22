#!/usr/bin/env python3
"""Kalibrasi pembanding tiga skema tanda tangan: RSA-PSS-2048, ECDSA P-256, Ed25519.

Dibuat untuk menjawab permintaan reviewer JTIIK (Reviewer 1, butir 2/5/7) yang
meminta perbandingan langsung dengan ECDSA/Ed25519 dari sisi ukuran dan performa.

Metodologi disalin dari calibrate_performance.py agar hasilnya sebanding dengan
Tabel 3 naskah: kunci dibangkitkan sekali, 100 iterasi pemanasan, lalu
num_samples pengukuran sign dan verify per skema dengan time.perf_counter(),
dan interval kepercayaan 95% memakai distribusi t.

Catatan metodologis: RSA-PSS dan ECDSA menandatangani objek hash SHA-256,
sedangkan Ed25519 (RFC 8032) menandatangani pesan mentah karena skema itu
melakukan hashing SHA-512 di dalam dirinya sendiri. Perbedaan ini melekat pada
definisi skema, bukan pilihan pengukuran.

Keluaran: dataset-zenodo/kalibrasi/kalibrasi_pembanding_skema.json dan .csv
"""
from __future__ import annotations

import csv
import json
import platform
import statistics
import sys
import time
from pathlib import Path

from Crypto.Hash import SHA256
from Crypto.PublicKey import ECC, RSA
from Crypto.Signature import DSS, eddsa, pss

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None

DIR = Path(__file__).resolve().parent / 'dataset-zenodo' / 'kalibrasi'
SALT_BYTES = 8


def ci95(data):
    n = len(data)
    mean = statistics.mean(data)
    sd = statistics.stdev(data) if n > 1 else 0.0
    sem = sd / (n ** 0.5) if n else 0.0
    if scipy_stats is not None and n > 1:
        h = sem * scipy_stats.t.ppf(0.975, n - 1)
    else:
        h = sem * 1.96
    return {
        'mean': mean, 'std': sd,
        'ci_lower': mean - h, 'ci_upper': mean + h, 'ci_width': 2 * h,
        'relative_error_percent': (h / mean * 100) if mean else 0.0,
        'samples': n,
    }


def main(num_samples: int = 100_000) -> int:
    log = sys.stdout
    print(f'Kalibrasi pembanding skema, n = {num_samples:,} per operasi', file=log, flush=True)

    rsa_key = RSA.generate(2048)
    p256_key = ECC.generate(curve='P-256')
    ed_key = ECC.generate(curve='ed25519')
    rsa_pub, p256_pub, ed_pub = rsa_key.publickey(), p256_key.public_key(), ed_key.public_key()

    skema = ('rsa_pss_2048', 'ecdsa_p256', 'ed25519')
    hasil = {s: {'signing': [], 'verification': []} for s in skema}

    for i in range(100):  # pemanasan
        msg = f'warmup_{i}'.encode()
        h = SHA256.new(msg)
        pss.new(rsa_key, salt_bytes=SALT_BYTES).sign(h)
        DSS.new(p256_key, 'fips-186-3').sign(h)
        eddsa.new(ed_key, 'rfc8032').sign(msg)

    t0 = time.perf_counter()
    for i in range(num_samples):
        msg = f"test_data_{i}_{'x' * 100}".encode()
        h = SHA256.new(msg)

        s = time.perf_counter()
        sig = pss.new(rsa_key, salt_bytes=SALT_BYTES).sign(h)
        hasil['rsa_pss_2048']['signing'].append((time.perf_counter() - s) * 1000)
        s = time.perf_counter()
        pss.new(rsa_pub, salt_bytes=SALT_BYTES).verify(h, sig)
        hasil['rsa_pss_2048']['verification'].append((time.perf_counter() - s) * 1000)

        s = time.perf_counter()
        sig = DSS.new(p256_key, 'fips-186-3').sign(h)
        hasil['ecdsa_p256']['signing'].append((time.perf_counter() - s) * 1000)
        s = time.perf_counter()
        DSS.new(p256_pub, 'fips-186-3').verify(h, sig)
        hasil['ecdsa_p256']['verification'].append((time.perf_counter() - s) * 1000)

        s = time.perf_counter()
        sig = eddsa.new(ed_key, 'rfc8032').sign(msg)
        hasil['ed25519']['signing'].append((time.perf_counter() - s) * 1000)
        s = time.perf_counter()
        eddsa.new(ed_pub, 'rfc8032').verify(msg, sig)
        hasil['ed25519']['verification'].append((time.perf_counter() - s) * 1000)

        if (i + 1) % 10_000 == 0:
            el = time.perf_counter() - t0
            print(f'  {i + 1:,}/{num_samples:,} | {el:.0f}s | ETA {el / (i + 1) * (num_samples - i - 1):.0f}s',
                  file=log, flush=True)

    elapsed = time.perf_counter() - t0

    ringkas = {s: {op: ci95(hasil[s][op]) for op in ('signing', 'verification')} for s in skema}
    ukuran = {
        'rsa_pss_2048': {'signature_bytes': 256, 'public_key_bytes': len(rsa_pub.export_key('DER'))},
        'ecdsa_p256': {'signature_bytes': 64, 'public_key_bytes': len(p256_pub.export_key(format='DER'))},
        'ed25519': {'signature_bytes': 64, 'public_key_bytes': len(ed_pub.export_key(format='DER'))},
    }
    meta = {
        'tier': 'validation',
        'num_samples': num_samples,
        'calibration_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_runtime_seconds': elapsed,
        'salt_bytes_rsa_pss': SALT_BYTES,
        'platform': f'{platform.system()} {platform.release()} {platform.machine()}',
        'python': platform.python_version(),
        'catatan': 'Ed25519 menandatangani pesan mentah (RFC 8032); RSA-PSS dan ECDSA menandatangani digest SHA-256.',
    }

    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / 'kalibrasi_pembanding_skema.json').write_text(
        json.dumps({'metadata': meta, 'benchmark_results': ringkas, 'ukuran_statis': ukuran},
                   indent=2, ensure_ascii=False), encoding='utf-8')

    with (DIR / 'kalibrasi_pembanding_skema.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['algoritma', 'operasi', 'num_samples', 'mean_ms', 'std_ms',
                    'ci_lower_ms', 'ci_upper_ms', 'relative_error_percent',
                    'signature_bytes', 'public_key_bytes', 'calibration_date'])
        for s in skema:
            for op in ('signing', 'verification'):
                r = ringkas[s][op]
                w.writerow([s, op, r['samples'], f"{r['mean']:.6f}", f"{r['std']:.6f}",
                            f"{r['ci_lower']:.6f}", f"{r['ci_upper']:.6f}",
                            f"{r['relative_error_percent']:.6f}",
                            ukuran[s]['signature_bytes'], ukuran[s]['public_key_bytes'],
                            meta['calibration_date']])

    print(f'\nSelesai dalam {elapsed:.0f}s. Hasil di {DIR}', file=log, flush=True)
    for s in skema:
        for op in ('signing', 'verification'):
            r = ringkas[s][op]
            print(f"  {s:14} {op:12} {r['mean']:7.3f} ms (SD {r['std']:.3f}, "
                  f"CI [{r['ci_lower']:.3f}-{r['ci_upper']:.3f}], ±{r['relative_error_percent']:.2f}%)",
                  file=log, flush=True)
    return 0


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    raise SystemExit(main(n))
