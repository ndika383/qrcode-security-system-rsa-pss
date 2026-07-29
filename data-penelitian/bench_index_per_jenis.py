"""Rincian kinerja per jenis kueri, agar percepatan tidak dilaporkan terinflasi."""
import json
import os
import time
import random
from datetime import datetime, timedelta, timezone

import app as A

DATA = A.app.config['DATA_FOLDER']
random.seed(7)

nama_file = [f for f in os.listdir(DATA) if f.endswith('.json')]
print(f"Korpus: {len(nama_file):,} record\n")


def muat(name):
    with open(os.path.join(DATA, name), 'r', encoding='utf-8') as f:
        return json.load(f)


sampel = [muat(n) for n in random.sample(nama_file, 40)]

JENIS = {
    'utuh          ': lambda r: dict(r),
    'nama_diubah   ': lambda r: {**r, 'nama': 'Diubah'},
    'id_diubah     ': lambda r: {**r, 'id': r['id'] + '_PALSU'},
    'tak_ada       ': lambda r: {**r, 'id': 'HANTU_' + r['id'], 'nonce': os.urandom(8).hex()},
}

# jumlah ulangan dibedakan: jalur fallback nonce sangat mahal di mode pemindaian
ULANG = {'utuh          ': 20, 'nama_diubah   ': 20, 'id_diubah     ': 3, 'tak_ada       ': 3}

hasil = {}
for mode in ('pemindaian', 'index'):
    asli = A.qr_record_index_ready
    if mode == 'pemindaian':
        A.qr_record_index_ready = lambda: False
    else:
        A.qr_record_index_ready = asli

    hasil[mode] = {}
    with A.app.app_context():
        for label, bikin in JENIS.items():
            n = ULANG[label]
            kueri = [bikin(r) for r in sampel[:n]]
            t0 = time.perf_counter()
            for q in kueri:
                A.find_original_qr_data(q)
            hasil[mode][label] = (time.perf_counter() - t0) / n * 1000
            print(f"  {mode:12s} {label} {hasil[mode][label]:10.3f} ms", flush=True)
    A.qr_record_index_ready = asli
    print()

print("===== RINGKASAN (ms per kueri) =====")
print(f"{'jenis kueri':16s} {'pemindaian':>12s} {'index':>10s} {'percepatan':>12s}")
for label in JENIS:
    s, i = hasil['pemindaian'][label], hasil['index'][label]
    print(f"{label:16s} {s:12.3f} {i:10.3f} {s/i:11.1f}x")

json.dump(hasil, open('hasil_per_jenis.json', 'w'), indent=2)
