"""Evaluasi sensitivitas ambang QR_PAYLOAD_MAX_AGE_SECONDS.

Dijalankan di sandbox terisolasi: seluruh path (static/data, logs/security_state.db,
logs/used_nonces.txt) relatif terhadap cwd sandbox, sehingga basis data produksi
dan penyimpanan nonce produksi tidak tersentuh.
"""
import json
import os
import sqlite3
import time
import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy import stats
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pss

import app as A

# ---------------------------------------------------------------- konfigurasi
STRATA_HARI = [0.5, 2.0, 5.0, 8.17, 10.0, 20.0, 40.0]
N_GENUINE = 100
N_MODIF = 10
N_REPLAY = 10
AMBANG = [("1 hari", 86_400), ("7 hari", 604_800), ("30 hari", 2_592_000)]

DATA_DIR = A.app.config['DATA_FOLDER']
DB_PATH = A.app.config['SECURITY_STATE_DB']
NONCE_LOG = A.app.config['NONCE_LOG']

rsa_key = RSA.import_key(open('rsa_key.pem').read())
rsa_pub = rsa_key.publickey()


def canon(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sign(payload):
    return pss.new(rsa_key, salt_bytes=8).sign(SHA256.new(canon(payload)))


def verify(payload, signature):
    """Kembalikan (valid, durasi_detik)."""
    t0 = time.perf_counter()
    try:
        pss.new(rsa_pub, salt_bytes=8).verify(SHA256.new(canon(payload)), signature)
        ok = True
    except (ValueError, TypeError):
        ok = False
    return ok, time.perf_counter() - t0


def buat_payload(uid, nama, umur_hari):
    ts = datetime.now(timezone.utc) - timedelta(days=umur_hari)
    return {
        "nama": nama,
        "id": uid,
        "timestamp": ts.astimezone().isoformat(),
        "nonce": os.urandom(A.get_qr_nonce_bytes()).hex(),
        "qr_modules": 49,
        "qr_version": 8,
    }


def simpan_record(payload):
    suffix = hashlib.sha256(canon(payload)).hexdigest()[:8]
    path = os.path.join(DATA_DIR, f"qr_{payload['id']}_{suffix}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)


def reset_nonce_store():
    """Kondisi awal identik tiap taraf; tanpa ini taraf ke-2 dst. jadi replay."""
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH, timeout=20)
        try:
            conn.execute("DELETE FROM nonce_state")
            conn.commit()
        finally:
            conn.close()
    if os.path.exists(NONCE_LOG):
        open(NONCE_LOG, 'w').close()


def kategori(hasil):
    """Petakan pesan klasifikasi ke kategori analisis."""
    if hasil['valid']:
        return 'valid'
    if hasil['is_replay']:
        return 'replay'
    if hasil['is_expired']:
        return 'kedaluwarsa'
    if 'Dimodifikasi' in hasil['message']:
        return 'dimodifikasi'
    return 'lainnya'


# ------------------------------------------------------------------- korpus
print("Membangun korpus uji...", flush=True)
korpus = []
seq = 0
for umur in STRATA_HARI:
    for arm, n in (('genuine', N_GENUINE), ('modifikasi', N_MODIF), ('replay', N_REPLAY)):
        for _ in range(n):
            seq += 1
            uid = f"SENS{seq:06d}"
            payload = buat_payload(uid, f"Subjek Uji {seq}", umur)
            signature = sign(payload)
            simpan_record(payload)          # rekaman asli selalu yang disimpan

            uji = dict(payload)
            if arm == 'modifikasi':
                uji['nama'] = f"Subjek Diubah {seq}"   # rusak setelah ditandatangani

            korpus.append({
                'umur_hari': umur, 'arm': arm,
                'payload_uji': uji, 'signature': signature,
            })

print(f"Korpus: {len(korpus)} payload, {len(STRATA_HARI)} strata umur", flush=True)

# --------------------------------------------------------------- eksperimen
baris = []
for label, detik in AMBANG:
    reset_nonce_store()
    A.app.config['QR_PAYLOAD_MAX_AGE_SECONDS'] = detik
    print(f"\nTaraf ambang = {label} ({detik} detik)", flush=True)

    with A.app.app_context():
        # priming untuk arm replay: verifikasi pertama tidak dicatat sebagai data
        for item in korpus:
            if item['arm'] == 'replay':
                A.classify_qr_verification(item['payload_uji'], True, "")

        for item in korpus:
            sig_ok, t_verify = verify(item['payload_uji'], item['signature'])
            t0 = time.perf_counter()
            hasil = A.classify_qr_verification(item['payload_uji'], sig_ok, "")
            t_decision = time.perf_counter() - t0

            baris.append({
                'ambang': label, 'ambang_detik': detik,
                'umur_hari': item['umur_hari'], 'arm': item['arm'],
                'kategori': kategori(hasil), 'pesan': hasil['message'],
                'signature_valid': sig_ok,
                'verify_time': t_verify, 'decision_time': t_decision,
            })

    n_valid = sum(1 for b in baris if b['ambang'] == label and b['kategori'] == 'valid')
    print(f"  diterima sebagai valid: {n_valid}", flush=True)

# ------------------------------------------ mikrobenchmark is_payload_expired
print("\nMikrobenchmark is_payload_expired()...", flush=True)
sampel = korpus[0]['payload_uji']
mikro = {}
with A.app.app_context():
    for label, detik in AMBANG:
        A.app.config['QR_PAYLOAD_MAX_AGE_SECONDS'] = detik
        for _ in range(2000):
            A.is_payload_expired(sampel)          # pemanasan
        t0 = time.perf_counter()
        for _ in range(20000):
            A.is_payload_expired(sampel)
        mikro[label] = (time.perf_counter() - t0) / 20000

# ------------------------------------------------------------------ analisis
KATEGORI = ['valid', 'kedaluwarsa', 'replay', 'dimodifikasi']
labels = [l for l, _ in AMBANG]

tabel = {l: {k: 0 for k in KATEGORI} for l in labels}
for b in baris:
    tabel[b['ambang']][b['kategori']] += 1

# H1 - khi-kuadrat pada tabel kontingensi penuh
obs = np.array([[tabel[l][k] for k in KATEGORI] for l in labels])
kolom_aktif = obs[:, obs.sum(axis=0) > 0]
chi2, p_chi, dof, _ = stats.chi2_contingency(kolom_aktif)
n_total = kolom_aktif.sum()
cramers_v = np.sqrt(chi2 / (n_total * (min(kolom_aktif.shape) - 1)))

# H2 - ANOVA pada decision_time
kelompok = [np.array([b['decision_time'] for b in baris if b['ambang'] == l]) for l in labels]
f_stat, p_anova = stats.f_oneway(*kelompok)
grand = np.concatenate(kelompok)
ss_between = sum(len(g) * (g.mean() - grand.mean()) ** 2 for g in kelompok)
eta2 = ss_between / ((grand - grand.mean()) ** 2).sum()

# ANOVA pembanding pada verify_time (RSA-PSS, jelas tidak terkait ambang)
kelompok_v = [np.array([b['verify_time'] for b in baris if b['ambang'] == l]) for l in labels]
f_v, p_v = stats.f_oneway(*kelompok_v)

# kurva penerimaan arm genuine
kurva = {}
for l in labels:
    kurva[l] = {}
    for u in STRATA_HARI:
        sub = [b for b in baris if b['ambang'] == l and b['umur_hari'] == u and b['arm'] == 'genuine']
        kurva[l][u] = sum(1 for b in sub if b['kategori'] == 'valid') / len(sub)

# false rejection rate arm genuine
frr = {}
for l in labels:
    sub = [b for b in baris if b['ambang'] == l and b['arm'] == 'genuine']
    frr[l] = sum(1 for b in sub if b['kategori'] == 'kedaluwarsa') / len(sub)

hasil_akhir = {
    'n_payload': len(korpus),
    'n_klasifikasi': len(baris),
    'strata_hari': STRATA_HARI,
    'tabel_kontingensi': tabel,
    'h1': {'chi2': chi2, 'dof': dof, 'p': p_chi, 'cramers_v': cramers_v},
    'h2_decision_time': {
        'F': f_stat, 'p': p_anova, 'eta_squared': eta2,
        'mean_ms': {l: float(g.mean() * 1000) for l, g in zip(labels, kelompok)},
        'sd_ms': {l: float(g.std(ddof=1) * 1000) for l, g in zip(labels, kelompok)},
    },
    'verify_time_rsa': {
        'F': f_v, 'p': p_v,
        'mean_ms': {l: float(g.mean() * 1000) for l, g in zip(labels, kelompok_v)},
    },
    'mikrobenchmark_expiry_us': {l: v * 1e6 for l, v in mikro.items()},
    'kurva_penerimaan': kurva,
    'false_rejection_rate': frr,
}

with open('hasil_sensitivitas.json', 'w', encoding='utf-8') as f:
    json.dump(hasil_akhir, f, indent=2, ensure_ascii=False)

print("\n===== RINGKASAN =====")
print(json.dumps(hasil_akhir, indent=2, ensure_ascii=False, default=float))
