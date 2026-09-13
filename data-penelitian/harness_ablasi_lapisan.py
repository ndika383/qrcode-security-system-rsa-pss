#!/usr/bin/env python3
"""
Ablasi per lapisan atas kampanye pengukuran empiris (harness_empiris.py).

Kampanye empiris 4 September 2026 melaporkan deteksi 100% pada seluruh subjenis,
tetapi tidak memisahkan lapisan mana yang menangkap serangan. Harness ini
menjalankan ulang KEEMPAT skenario yang sama, dengan seed dan alokasi subjenis
yang identik, sebanyak tiga kali dengan verifikator berbeda:

  full         jalur produksi: verifikasi RSA-PSS lalu classify_qr_verification()
  kriptografi  hanya verifikasi RSA-PSS salt 8 byte (setara verifikator luring
               yang hanya memegang kunci publik; tanpa basis data, tanpa waktu)
  aplikasi     classify_qr_verification() dengan tanda tangan DIANGGAP sah:
               pembandingan rekaman asli, validasi struktur, buku besar nonce,
               kedaluwarsa, drift dan monotonik timestamp

Tiap mode memakai basis data status keamanan sementara yang baru, sehingga
buku besar nonce satu mode tidak memengaruhi mode lain dan basis data produksi
tidak tersentuh. Verifikasi tidak mengonsumsi aliran acak, jadi alokasi subjenis
ketiga mode identik dengan kampanye 4 September; mode full karenanya sekaligus
menjadi uji reproduksi terhadap empiris_per_subjenis.csv.

Selain itu dicatat indikator validasi struktur saja (validate_payload_structure)
per operasi pemalsuan data, tanpa status apa pun.

Jalankan sebagai root (kunci privat bermode 0640 root:www-data):
    sudo -n /opt/qrcode/venv/bin/python data-penelitian/harness_ablasi_lapisan.py
"""
import argparse, base64, json, os, random, sys, tempfile
from datetime import datetime

sys.path.insert(0, '/opt/qrcode/data-penelitian')
import harness_empiris as H          # memuat app, kunci produksi, dan isolasi state
A = H.A

from Crypto.Hash import SHA256
from Crypto.Signature import pss

MODE = ['full', 'kriptografi', 'aplikasi']


def state_baru():
    """Arahkan basis data status keamanan ke berkas sementara yang baru."""
    tmp = tempfile.NamedTemporaryFile(prefix='ablasi_state_', suffix='.db', delete=False)
    tmp.close()
    A.app.config['SECURITY_STATE_DB'] = tmp.name
    A.security_state_ready = False
    A.reset_security_state_conn()
    assert A.init_security_state_db(), 'gagal menyiapkan basis data status terisolasi'
    return tmp.name


def cek_rsa(data, signature_b64, alg):
    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        return False, 'signature tidak dapat didekode'
    if alg != 'RSA':
        return False, 'signature tidak valid (algoritma tidak diketahui)'
    h = SHA256.new(json.dumps(data, sort_keys=True).encode('utf-8'))
    try:
        pss.new(A.public_key, salt_bytes=8).verify(h, signature)
        return True, ''
    except (ValueError, TypeError):
        return False, 'signature tidak valid (RSA)'


STRUKTUR = {}   # subjenis -> [total, terdeteksi_struktur]


def pasang_verifikator(mode):
    def full(data, sig, alg='RSA', original=None):
        ok, err = cek_rsa(data, sig, alg)
        return ok, err, A.classify_qr_verification(data, ok, err, original_data_override=original)

    def kriptografi(data, sig, alg='RSA', original=None):
        ok, err = cek_rsa(data, sig, alg)
        return ok, err, {'valid': ok, 'is_replay': False, 'is_expired': False}

    def aplikasi(data, sig, alg='RSA', original=None):
        return True, '', A.classify_qr_verification(data, True, '', original_data_override=original)

    H.verifikasi = {'full': full, 'kriptografi': kriptografi, 'aplikasi': aplikasi}[mode]


def indikator_struktur(n, seed):
    """Validasi struktur saja, per subjenis, pada alokasi yang sama."""
    random.seed(seed)
    hasil = {s: {'total': 0, 'terdeteksi': 0} for s in H.SUBJENIS}
    _, donor_sig = H.buat_payload(999999)
    for i in range(n):
        asli, sig_asli = H.buat_payload(i)
        jenis = random.choices(H.SUBJENIS, weights=H.BOBOT, k=1)[0]
        d, _, _ = H.rusak(asli, sig_asli, jenis, donor_sig)
        hasil[jenis]['total'] += 1
        if A.validate_payload_structure(d):
            hasil[jenis]['terdeteksi'] += 1
    return hasil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--operasi', type=int, default=50000)
    ap.add_argument('--replay', type=int, default=1500)
    ap.add_argument('--forgery', type=int, default=4000)
    ap.add_argument('--kedaluwarsa', type=int, default=5000)
    ap.add_argument('--kontrol-tampering', type=int, default=2500)
    ap.add_argument('--kontrol-forgery', type=int, default=500)
    ap.add_argument('--seed', type=int, default=20260824)
    ap.add_argument('--keluaran', default='data-penelitian/hasil-ablasi')
    a = ap.parse_args()
    os.makedirs(a.keluaran, exist_ok=True)
    mulai = datetime.now()
    keluaran = {'metadata': {'harness': 'ablasi_lapisan', 'versi': '1.0', 'seed': a.seed,
                             'mulai': mulai.isoformat(), 'argumen': vars(a)}, 'mode': {}}
    sementara = []

    for mode in MODE:
        print(f'== mode {mode}', flush=True)
        sementara.append(state_baru())
        pasang_verifikator(mode)
        random.seed(a.seed)
        rng_kontrol = random.Random(a.seed + 1)
        tam = H.uji_tampering(a.operasi, a.kontrol_tampering, rng_kontrol)
        rep = H.uji_replay(a.replay)
        exp = H.uji_kedaluwarsa(a.kedaluwarsa)
        # Pada mode aplikasi uji_forgery menghitung penolakan dari sig_valid yang
        # dipaksa True, sehingga penolakan 0 berarti lapisan aplikasi saja tidak
        # menangkap tanda tangan palsu atas data yang tidak diubah.
        forg = H.uji_forgery(a.forgery, a.kontrol_forgery, rng_kontrol)
        for h in (tam, rep, exp, forg):
            h.pop('waktu_ms', None)
        keluaran['mode'][mode] = {'pemalsuan_data': tam, 'replay': rep,
                                  'kedaluwarsa': exp, 'pemalsuan_tanda_tangan': forg}
        print(json.dumps({s: b for s, b in tam['per_subjenis'].items()}), flush=True)
        print('replay', rep['replay_terdeteksi'], '/', rep['percobaan_replay'],
              '| kedaluwarsa', exp['terdeteksi'], '/', exp['total_kedaluwarsa'],
              '| forgery ditolak', forg['ditolak'], '/', forg['total'],
              '| kontrol', tam['kontrol_negatif'], exp['kontrol_negatif'], forg['kontrol_negatif'], flush=True)

    print('== indikator struktur', flush=True)
    keluaran['struktur_saja'] = indikator_struktur(a.operasi, a.seed)
    keluaran['metadata']['selesai'] = datetime.now().isoformat()

    path = os.path.join(a.keluaran, f'hasil_ablasi_{mulai.strftime("%Y%m%d_%H%M%S")}.json')
    with open(path, 'w') as f:
        json.dump(keluaran, f, indent=2, ensure_ascii=False)
    print('Hasil:', path)
    for p in sementara + [H._tmpdb.name]:
        try:
            os.unlink(p)
        except OSError:
            pass


if __name__ == '__main__':
    main()
