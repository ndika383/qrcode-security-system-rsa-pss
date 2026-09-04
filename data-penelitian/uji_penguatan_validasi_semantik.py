"""Uji regresi penguatan validasi semantik — dijalankan terisolasi dari produksi."""
import os, sys, json, base64, tempfile, copy
from datetime import datetime, timedelta, timezone
os.chdir('/opt/qrcode'); sys.path.insert(0,'/opt/qrcode')
from Crypto.Hash import SHA256
from Crypto.Signature import pss
import app as A

t=tempfile.NamedTemporaryFile(prefix='uji_',suffix='.db',delete=False); t.close()
A.app.config['SECURITY_STATE_DB']=t.name; A.security_state_ready=False
if hasattr(A,'reset_security_state_conn'): A.reset_security_state_conn()
assert A.init_security_state_db()
WIB=timezone(timedelta(hours=7))

def buat(umur_hari=0, geser_detik=0, extra=None, hapus=None):
    d={'nama':'Uji Regresi','id':'2026000001',
       'timestamp':(datetime.now(WIB)-timedelta(days=umur_hari)+timedelta(seconds=geser_detik)).isoformat(),
       'nonce':A.generate_qr_nonce(),'qr_modules':49,'qr_version':7}
    if extra: d.update(extra)
    if hapus: d.pop(hapus,None)
    sig=pss.new(A.private_key,salt_bytes=8).sign(SHA256.new(json.dumps(d,sort_keys=True).encode()))
    return d, base64.b64encode(sig).decode()

def verif(d,sig,original=None):
    try: raw=base64.b64decode(sig)
    except Exception: return {'valid':False,'message':'decode gagal'}
    h=SHA256.new(json.dumps(d,sort_keys=True).encode())
    try:
        pss.new(A.public_key,salt_bytes=8).verify(h,raw); ok,err=True,''
    except (ValueError,TypeError): ok,err=False,'signature tidak valid (RSA)'
    return A.classify_qr_verification(d,ok,err,original_data_override=original if original is not None else d)

KASUS=[]
def cek(nama,syarat,detail=''):
    KASUS.append((nama,syarat,detail)); print(f"  {'LULUS' if syarat else 'GAGAL'}  {nama}" + (f"  -> {detail}" if detail else ''))

print("### A. Regresi: QR sah harus tetap diterima")
for i,umur in enumerate([0,1,3,6]):
    d,s=buat(umur_hari=umur); r=verif(d,s)
    cek(f"QR sah umur {umur} hari diterima", r['valid'] is True, r['message'])

print("\n### B. Replay tetap terdeteksi")
d,s=buat(); verif(d,s); r=verif(d,s)
cek("verifikasi kedua ditandai replay", r['is_replay'] is True, r['message'])

print("\n### C. Timestamp masa depan ditolak (baru)")
d,s=buat(geser_detik=3600); r=verif(d,s)
cek("timestamp +1 jam ditolak", r['valid'] is False, r['message'])
d,s=buat(geser_detik=120); r=verif(d,s)
cek("timestamp +2 menit (dalam toleransi 300 s) diterima", r['valid'] is True, r['message'])

print("\n### D. Kedaluwarsa tetap terdeteksi")
d,s=buat(umur_hari=30); r=verif(d,s)
cek("QR umur 30 hari kedaluwarsa", r['is_expired'] is True, r['message'])

print("\n### E. Struktur payload (baru)")
d,s=buat(extra={'level_akses':'admin'}); asli,_=buat()
r=verif(d,s,original=asli)
cek("field asing terdeteksi", r['valid'] is False, r['message'][:90])
d,s=buat(hapus='id'); r=verif(d,s,original=asli)
cek("field wajib hilang terdeteksi", r['valid'] is False, r['message'][:90])

print("\n### F. Pemalsuan data tetap terdeteksi")
asli,sig=buat(); ubah=copy.deepcopy(asli); ubah['nama']='Penyerang'
r=verif(ubah,sig,original=asli)
cek("nama diubah terdeteksi", r['valid'] is False, r['message'][:90])

print("\n### G. Monotonik per nonce (baru)")
d,s=buat()
mono1,_=A.check_timestamp_monotonic(d['nonce'],d['timestamp'])
lebih_tua=(datetime.now(WIB)-timedelta(days=2)).isoformat()
mono2,pertama=A.check_timestamp_monotonic(d['nonce'],lebih_tua)
cek("timestamp lebih tua pada nonce sama ditolak", mono1 is True and mono2 is False, f"pertama={pertama[:19]}")

gagal=[k for k,ok,_ in KASUS if not ok]
print("\n"+"="*60)
print(f"TOTAL {len(KASUS)} kasus | LULUS {len(KASUS)-len(gagal)} | GAGAL {len(gagal)}")
if gagal: print("Gagal:",gagal)
os.unlink(t.name)
sys.exit(1 if gagal else 0)
