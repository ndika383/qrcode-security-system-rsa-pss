"""Uji ekuivalensi: pencarian via index harus identik dengan pemindaian direktori."""
import json
import os
import time
import random
from datetime import datetime, timedelta, timezone

import app as A

DATA = A.app.config['DATA_FOLDER']
random.seed(20260729)

N_BIASA = 8_000
IDS_RUMIT = [
    "TEST", "TEST_X", "TEST_XY",          # tabrakan awalan: qr_TEST_* juga cocok qr_TEST_X_*
    "CHARTFIX_10", "CHARTFIX_1",          # id mengandung underscore
    "a b/c", "id-dengan-dash", "ID.titik",  # butuh secure_filename
    "Ω-unicode", "UPPER", "upper",        # non-ASCII dan beda kapital
]


def buat(uid, seq, umur_hari=1.0):
    ts = datetime.now(timezone.utc) - timedelta(days=umur_hari)
    return {
        "nama": f"Subjek {seq}",
        "id": uid,
        "timestamp": ts.astimezone().isoformat(),
        "nonce": os.urandom(8).hex(),
        "qr_modules": 49,
        "qr_version": 8,
    }


def tulis(record, seq):
    """Tiru pola penamaan produksi: qr_{id}_{suffix}.json"""
    from werkzeug.utils import secure_filename
    uid = secure_filename(record['id']) or f"anon{seq}"
    name = f"qr_{uid}_{seq:08x}.json"
    with open(os.path.join(DATA, name), 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2)
    return name


print("Membangun korpus...", flush=True)
semua = []
seq = 0
for uid in IDS_RUMIT:
    for _ in range(3):                      # beberapa record per id rumit
        seq += 1
        r = buat(uid, seq)
        semua.append((tulis(r, seq), r))
for _ in range(N_BIASA):
    seq += 1
    r = buat(f"SUBJ{seq:07d}", seq)
    semua.append((tulis(r, seq), r))
# berkas rusak: 0-byte, JSON tak lengkap, dan JSON bertipe non-dict
RUSAK = []
for i, isi in enumerate([b"", b"{\"id\": ", b"[1,2,3]", b"bukan json"]):
    for j in range(3):
        nm = f"qr_RUSAK{i}{j}_deadbeef.json"
        open(os.path.join(DATA, nm), "wb").write(isi)
        RUSAK.append((nm, f"RUSAK{i}{j}"))
print(f"Korpus: {len(semua)} record + {len(RUSAK)} berkas rusak di {DATA}", flush=True)

# ---------------------------------------------------------------- kueri uji
kueri = []
for name, r in semua[:len(IDS_RUMIT) * 3]:          # seluruh kasus rumit
    kueri.append(('utuh', dict(r)))
for name, r in random.sample(semua, 300):           # sampel acak
    kueri.append(('utuh', dict(r)))
for name, r in random.sample(semua, 60):            # id dimodifikasi -> jalur nonce
    q = dict(r); q['id'] = q['id'] + "_PALSU"
    kueri.append(('id_diubah', q))
for name, r in random.sample(semua, 60):            # field lain diubah
    q = dict(r); q['nama'] = "Diubah"
    kueri.append(('nama_diubah', q))
for nm, uid in RUSAK:                               # id yang hanya punya berkas rusak
    kueri.append(('rusak', buat(uid, 0)))
for i in range(60):                                 # sama sekali tidak ada
    kueri.append(('tak_ada', buat(f"HANTU{i:05d}", i)))
print(f"Kueri uji: {len(kueri)}", flush=True)


def jalankan(label):
    hasil = []
    t0 = time.perf_counter()
    with A.app.app_context():
        for jenis, q in kueri:
            orig, files, exact = A.find_original_qr_data(q)
            hasil.append((jenis, orig, sorted(files or []), exact))
    return hasil, time.perf_counter() - t0


with A.app.app_context():
    assert not A.qr_record_index_ready(), "index seharusnya belum otoritatif"

print("\n[1] Mode pemindaian direktori (baseline)...", flush=True)
hasil_scan, t_scan = jalankan('scan')
print(f"    {len(kueri)} kueri dalam {t_scan:.2f} detik -> {t_scan/len(kueri)*1000:.2f} ms/kueri")

print("\n[2] Backfill index...", flush=True)
t0 = time.perf_counter()
with A.app.app_context():
    total, gagal = A.backfill_qr_record_index()
t_backfill = time.perf_counter() - t0
print(f"    {total} record terindeks, {gagal} dilewati, {t_backfill:.1f} detik")

with A.app.app_context():
    assert A.qr_record_index_ready(), "index seharusnya otoritatif setelah backfill"

print("\n[3] Mode index...", flush=True)
hasil_idx, t_idx = jalankan('index')
print(f"    {len(kueri)} kueri dalam {t_idx:.2f} detik -> {t_idx/len(kueri)*1000:.3f} ms/kueri")

# ------------------------------------------------------------- perbandingan
beda = []
for i, (a, b) in enumerate(zip(hasil_scan, hasil_idx)):
    if a != b:
        beda.append((i, kueri[i][0], a, b))

print("\n===== HASIL =====")
print(f"kueri dibandingkan : {len(kueri)}")
print(f"selisih ditemukan  : {len(beda)}")
if beda:
    for i, jenis, a, b in beda[:10]:
        print(f"  #{i} ({jenis})")
        print(f"    scan : files={a[2][:3]} exact={a[3]} orig_id={(a[1] or {}).get('id')}")
        print(f"    index: files={b[2][:3]} exact={b[3]} orig_id={(b[1] or {}).get('id')}")
else:
    print("  EKUIVALEN - index menghasilkan keluaran identik dengan pemindaian direktori")

print(f"\nkorpus             : {len(semua):,} record")
print(f"pemindaian direktori: {t_scan/len(kueri)*1000:8.3f} ms/kueri")
print(f"index               : {t_idx/len(kueri)*1000:8.3f} ms/kueri")
print(f"percepatan          : {t_scan/t_idx:8.1f}x")
print(f"backfill sekali     : {t_backfill:.1f} detik untuk {total:,} record")

json.dump({
    'n_korpus': len(semua), 'n_kueri': len(kueri), 'n_beda': len(beda),
    'ms_scan': t_scan / len(kueri) * 1000,
    'ms_index': t_idx / len(kueri) * 1000,
    'speedup': t_scan / t_idx,
    'backfill_detik': t_backfill, 'backfill_record': total,
}, open('hasil_index.json', 'w'), indent=2)
