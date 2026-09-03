#!/usr/bin/env python3
"""
Harness pengukuran empiris skenario keamanan QR Code RSA-PSS.

Berbeda dari modules/testing_controller.py yang membangkitkan hasil deteksi dari
laju terparameter, harness ini benar-benar memodifikasi payload lalu memanggil
jalur verifikasi asli pada app.py. Tidak ada satu pun keputusan deteksi yang
diundi; seluruhnya keluaran dari verifikasi tanda tangan RSA-PSS dan fungsi
classify_qr_verification().

Isolasi bukti: basis data status keamanan diarahkan ke berkas sementara sehingga
buku besar nonce produksi tidak tersentuh. Tidak ada penulisan ke
data/testing/testing_results.db maupun ke berkas log produksi.

Jalankan sebagai root (kunci privat bermode 0640 root:www-data):
    sudo -n /opt/qrcode/venv/bin/python data-penelitian/harness_empiris.py --operasi 5000
"""
import argparse, base64, copy, json, os, random, statistics, sys, tempfile, time
from datetime import datetime, timedelta, timezone

os.chdir('/opt/qrcode')
sys.path.insert(0, '/opt/qrcode')

from Crypto.Hash import SHA256
from Crypto.Signature import pss

import app as A   # memuat kunci produksi + seluruh fungsi verifikasi

WIB = timezone(timedelta(hours=7))   # sama dengan definisi di app.py

# ---------------------------------------------------------------- isolasi state
_tmpdb = tempfile.NamedTemporaryFile(prefix='harness_state_', suffix='.db', delete=False)
_tmpdb.close()
A.app.config['SECURITY_STATE_DB'] = _tmpdb.name
A.security_state_ready = False
assert A.init_security_state_db(), 'gagal menyiapkan basis data status terisolasi'

NAMA = ['Andi Pratama','Siti Rahayu','Budi Santoso','Dewi Lestari','Eko Wijaya',
        'Fitri Handayani','Gunawan Saputra','Hesti Kurnia','Irfan Maulana','Julia Anggraini']

SUBJENIS = ['field_modification','field_addition','field_removal','data_type_change',
            'timestamp_tampering','signature_injection','encryption_bypass']
BOBOT   = [0.40, 0.20, 0.15, 0.10, 0.08, 0.05, 0.02]
KRITIS  = {'signature_injection','encryption_bypass'}


def buat_payload(i, umur_hari=0):
    """Payload asli, ditandatangani dengan jalur kriptografi produksi.

    umur_hari > 0 menghasilkan payload yang sah secara kriptografis namun sudah
    lewat masa berlaku, dipakai menguji lapisan kedaluwarsa.
    """
    data = {
        'nama': random.choice(NAMA),
        'id': f'2026{i:07d}',
        'timestamp': (datetime.now(WIB) - timedelta(days=umur_hari)).isoformat(),
        'nonce': A.generate_qr_nonce(),
        'qr_modules': random.choice([45, 49, 53, 57]),
        'qr_version': random.choice([6, 7, 8, 9]),
    }
    hash_digest = SHA256.new(json.dumps(data, sort_keys=True).encode('utf-8'))
    signature = pss.new(A.private_key, salt_bytes=8).sign(hash_digest)
    return data, base64.b64encode(signature).decode('utf-8')


def verifikasi(data, signature_b64, alg='RSA', original=None):
    """Jalur verifikasi asli: RSA-PSS salt 8 byte + classify_qr_verification()."""
    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        return False, 'signature tidak dapat didekode', None
    hash_obj = SHA256.new(json.dumps(data, sort_keys=True).encode('utf-8'))
    if alg == 'RSA':
        try:
            pss.new(A.public_key, salt_bytes=8).verify(hash_obj, signature)
            sig_valid, sig_error = True, ''
        except (ValueError, TypeError):
            sig_valid, sig_error = False, 'signature tidak valid (RSA)'
    else:
        sig_valid, sig_error = False, 'signature tidak valid (algoritma tidak diketahui)'
    hasil = A.classify_qr_verification(data, sig_valid, sig_error,
                                       original_data_override=original)
    return sig_valid, sig_error, hasil


def rusak(data, signature_b64, jenis, donor):
    """Modifikasi nyata terhadap payload. Mengembalikan (data, signature, alg)."""
    d, sig, alg = copy.deepcopy(data), signature_b64, 'RSA'
    if jenis == 'field_modification':
        lain = [n for n in NAMA if n != d['nama']]
        d['nama'] = random.choice(lain)
    elif jenis == 'field_addition':
        d['level_akses'] = 'administrator'
    elif jenis == 'field_removal':
        d.pop('id', None)
    elif jenis == 'data_type_change':
        d['qr_version'] = str(d['qr_version'])
    elif jenis == 'timestamp_tampering':
        t = datetime.fromisoformat(d['timestamp']) + timedelta(days=random.randint(1, 400))
        d['timestamp'] = t.isoformat()
    elif jenis == 'signature_injection':
        sig = donor              # tanda tangan sah milik payload lain
    elif jenis == 'encryption_bypass':
        alg = 'NONE'             # upaya mengelak dengan algoritma tak dikenal
    return d, sig, alg


def uji_tampering(n):
    hasil = {'total': n, 'terdeteksi': 0, 'lolos': 0, 'per_subjenis': {}, 'waktu_ms': []}
    for s in SUBJENIS:
        hasil['per_subjenis'][s] = {'total': 0, 'terdeteksi': 0, 'lolos': 0}
    donor_data, donor_sig = buat_payload(999999)
    for i in range(n):
        asli, sig_asli = buat_payload(i)
        jenis = random.choices(SUBJENIS, weights=BOBOT, k=1)[0]
        d, sig, alg = rusak(asli, sig_asli, jenis, donor_sig)
        t0 = time.perf_counter()
        _, _, r = verifikasi(d, sig, alg, original=asli)
        dt = (time.perf_counter() - t0) * 1000
        hasil['waktu_ms'].append(dt)
        terdeteksi = not r['valid']          # sah hanya bila lolos seluruh lapisan
        b = hasil['per_subjenis'][jenis]
        b['total'] += 1
        if terdeteksi:
            hasil['terdeteksi'] += 1; b['terdeteksi'] += 1
        else:
            hasil['lolos'] += 1; b['lolos'] += 1
    return hasil


def uji_replay(n, ulangan=3):
    """Verifikasi berulang payload sah. Pemakaian ke-2 dst wajib ditandai replay."""
    h = {'percobaan_replay': 0, 'replay_terdeteksi': 0, 'negatif_palsu': 0,
         'verifikasi_pertama': 0, 'positif_palsu': 0, 'waktu_ms': []}
    for i in range(n):
        data, sig = buat_payload(2_000_000 + i)
        for k in range(ulangan):
            t0 = time.perf_counter()
            _, _, r = verifikasi(data, sig, 'RSA', original=data)
            h['waktu_ms'].append((time.perf_counter() - t0) * 1000)
            if k == 0:
                h['verifikasi_pertama'] += 1
                if r['is_replay']:
                    h['positif_palsu'] += 1      # segar tapi ditandai replay
            else:
                h['percobaan_replay'] += 1
                if r['is_replay']:
                    h['replay_terdeteksi'] += 1
                else:
                    h['negatif_palsu'] += 1      # serangan replay lolos
    return h


def uji_kedaluwarsa(n):
    """Payload bertanda tangan sah namun lewat masa berlaku 7 hari.

    Tanda tangan tetap valid dan data tidak diubah, sehingga deteksi sepenuhnya
    bergantung pada lapisan temporal — satu-satunya subjenis pada harness ini
    yang benar-benar dapat lolos.
    """
    h = {'total': n, 'terdeteksi': 0, 'lolos': 0, 'waktu_ms': [],
         'kontrol_negatif': {'total': 0, 'keliru_ditandai': 0}}
    for i in range(n):
        tua = random.random() < 0.5
        umur = random.randint(8, 400) if tua else random.randint(0, 6)
        data, sig = buat_payload(4_000_000 + i, umur_hari=umur)
        t0 = time.perf_counter()
        sig_valid, _, r = verifikasi(data, sig, 'RSA', original=data)
        h['waktu_ms'].append((time.perf_counter() - t0) * 1000)
        assert sig_valid, 'tanda tangan harus tetap sah pada skenario kedaluwarsa'
        if tua:
            h['total'] = h['total']
            if r['is_expired']:
                h['terdeteksi'] += 1
            else:
                h['lolos'] += 1
        else:
            h['kontrol_negatif']['total'] += 1
            if r['is_expired']:
                h['kontrol_negatif']['keliru_ditandai'] += 1
    h['total_kedaluwarsa'] = h['terdeteksi'] + h['lolos']
    return h


def uji_forgery(n):
    jenis = ['random_signature','truncated_signature','swapped_signature','bit_flip']
    h = {'total': n, 'ditolak': 0, 'diterima': 0, 'per_jenis': {j: {'total':0,'ditolak':0} for j in jenis},
         'waktu_ms': []}
    donor_data, donor_sig = buat_payload(888888)
    for i in range(n):
        data, sig = buat_payload(3_000_000 + i)
        j = random.choice(jenis)
        raw = base64.b64decode(sig)
        if j == 'random_signature':
            palsu = base64.b64encode(os.urandom(len(raw))).decode()
        elif j == 'truncated_signature':
            palsu = base64.b64encode(raw[:len(raw)//2]).decode()
        elif j == 'swapped_signature':
            palsu = donor_sig
        else:
            b = bytearray(raw); p = random.randrange(len(b)); b[p] ^= 1 << random.randrange(8)
            palsu = base64.b64encode(bytes(b)).decode()
        t0 = time.perf_counter()
        sig_valid, _, _ = verifikasi(data, palsu, 'RSA', original=data)
        h['waktu_ms'].append((time.perf_counter() - t0) * 1000)
        h['per_jenis'][j]['total'] += 1
        if not sig_valid:
            h['ditolak'] += 1; h['per_jenis'][j]['ditolak'] += 1
        else:
            h['diterima'] += 1
    return h


def ringkas(v):
    v = sorted(v); n = len(v)
    if not n: return {}
    return {'n': n, 'mean_ms': statistics.mean(v), 'median_ms': statistics.median(v),
            'sd_ms': statistics.pstdev(v), 'min_ms': v[0], 'max_ms': v[-1],
            'p90_ms': v[int(n*0.90)], 'p95_ms': v[int(n*0.95)], 'p99_ms': v[int(n*0.99)],
            'proporsi_le_20ms': sum(1 for x in v if x <= 20) / n * 100}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--operasi', type=int, default=5000, help='operasi pemalsuan data')
    ap.add_argument('--replay', type=int, default=1500, help='sampel replay (x3 verifikasi)')
    ap.add_argument('--forgery', type=int, default=2000)
    ap.add_argument('--kedaluwarsa', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=20260824)
    ap.add_argument('--keluaran', default='data-penelitian/hasil-empiris')
    a = ap.parse_args()
    random.seed(a.seed)
    os.makedirs(a.keluaran, exist_ok=True)
    mulai = datetime.now()

    print(f'[1/4] Pemalsuan data: {a.operasi} operasi ...', flush=True)
    tam = uji_tampering(a.operasi)
    print(f'[2/4] Replay: {a.replay} sampel x 3 verifikasi ...', flush=True)
    rep = uji_replay(a.replay)
    print(f'[3/4] Kedaluwarsa: {a.kedaluwarsa} payload sah ...', flush=True)
    exp = uji_kedaluwarsa(a.kedaluwarsa)
    print(f'[4/4] Pemalsuan tanda tangan: {a.forgery} percobaan ...', flush=True)
    forg = uji_forgery(a.forgery)

    akurasi = tam['terdeteksi'] / tam['total'] * 100
    kritis_tot = sum(tam['per_subjenis'][s]['total'] for s in KRITIS)
    kritis_det = sum(tam['per_subjenis'][s]['terdeteksi'] for s in KRITIS)
    fnr = rep['negatif_palsu'] / rep['percobaan_replay'] * 100 if rep['percobaan_replay'] else 0.0
    hasil = {
        'metadata': {
            'harness': 'empiris', 'versi': '1.0', 'seed': a.seed,
            'mulai': mulai.isoformat(), 'selesai': datetime.now().isoformat(),
            'catatan': 'Seluruh keputusan deteksi berasal dari verifikasi RSA-PSS dan '
                       'classify_qr_verification(); tidak ada laju terparameter.',
        },
        'pemalsuan_data': {
            **{k: v for k, v in tam.items() if k != 'waktu_ms'},
            'akurasi_deteksi_persen': akurasi,
            'deteksi_kategori_kritis_persen': (kritis_det/kritis_tot*100) if kritis_tot else None,
            'waktu_deteksi': ringkas(tam['waktu_ms']),
        },
        'replay': {
            **{k: v for k, v in rep.items() if k != 'waktu_ms'},
            'laju_deteksi_persen': rep['replay_terdeteksi']/rep['percobaan_replay']*100 if rep['percobaan_replay'] else 0,
            'fnr_persen': fnr,
            'fpr_persen': rep['positif_palsu']/rep['verifikasi_pertama']*100 if rep['verifikasi_pertama'] else 0,
            'waktu_deteksi': ringkas(rep['waktu_ms']),
        },
        'kedaluwarsa': {
            **{k: v for k, v in exp.items() if k != 'waktu_ms'},
            'laju_deteksi_persen': exp['terdeteksi']/exp['total_kedaluwarsa']*100 if exp['total_kedaluwarsa'] else None,
            'fpr_kontrol_negatif_persen': (exp['kontrol_negatif']['keliru_ditandai']/exp['kontrol_negatif']['total']*100)
                                           if exp['kontrol_negatif']['total'] else None,
            'waktu_deteksi': ringkas(exp['waktu_ms']),
        },
        'pemalsuan_tanda_tangan': {
            **{k: v for k, v in forg.items() if k != 'waktu_ms'},
            'laju_penolakan_persen': forg['ditolak']/forg['total']*100,
            'waktu_verifikasi': ringkas(forg['waktu_ms']),
        },
    }
    for s, b in tam['per_subjenis'].items():
        b['laju_deteksi_persen'] = b['terdeteksi']/b['total']*100 if b['total'] else None

    stamp = mulai.strftime('%Y%m%d_%H%M%S')
    path = os.path.join(a.keluaran, f'hasil_empiris_{stamp}.json')
    with open(path, 'w') as f:
        json.dump(hasil, f, indent=2, ensure_ascii=False)

    W = ringkas(tam['waktu_ms'])
    print('\n' + '='*64)
    print('HASIL PENGUKURAN EMPIRIS'.center(64))
    print('='*64)
    print(f"Akurasi deteksi pemalsuan data : {akurasi:.2f}%   (target proposal 79,2%)")
    print(f"Deteksi kategori kritis        : {kritis_det/kritis_tot*100:.2f}%" if kritis_tot else "")
    print(f"Waktu deteksi rata-rata        : {W['mean_ms']:.3f} ms   (target proposal 20,0 ms)")
    print(f"   median {W['median_ms']:.3f} | p95 {W['p95_ms']:.3f} | <=20 ms {W['proporsi_le_20ms']:.1f}%")
    print(f"Laju deteksi replay            : {hasil['replay']['laju_deteksi_persen']:.2f}%   (target proposal 95,8%)")
    print(f"FNR replay                     : {fnr:.4f}%   (target proposal <= 0,1%)")
    print(f"FPR replay                     : {hasil['replay']['fpr_persen']:.4f}%")
    print(f"Deteksi kedaluwarsa            : {hasil['kedaluwarsa']['laju_deteksi_persen']:.2f}%  "
          f"(kontrol negatif keliru: {hasil['kedaluwarsa']['fpr_kontrol_negatif_persen']:.2f}%)")
    print(f"Laju penolakan forgery         : {hasil['pemalsuan_tanda_tangan']['laju_penolakan_persen']:.2f}%   (target proposal 97,0%)")
    print('-'*64)
    print('Laju deteksi per subjenis pemalsuan data:')
    for s, b in sorted(tam['per_subjenis'].items(), key=lambda x: -(x[1]['laju_deteksi_persen'] or 0)):
        if b['total']:
            tanda = ' [kritis]' if s in KRITIS else ''
            print(f"   {s:<22} {b['terdeteksi']:>6}/{b['total']:<6} {b['laju_deteksi_persen']:>7.2f}%{tanda}")
    print('='*64)
    print(f'Hasil lengkap: {path}')
    os.unlink(_tmpdb.name)


if __name__ == '__main__':
    main()
