"""Tulis rekaman QR asli agar verifikasi menempuh jalur lengkap.

Tanpa rekaman ini, find_original_qr_data() gagal dan verifikasi berhenti pada
cabang "Data Tidak Ditemukan" — melewatkan pencatatan nonce, pemeriksaan replay,
kedaluwarsa, dan monotonik. Justru bagian itu yang hendak diukur uji beban.
"""
import os,sys,json,secrets,csv
BASE='/opt/qrcode-staging'
os.chdir(BASE); sys.path.insert(0,BASE)
import app as A
data_dir=A.app.config['DATA_FOLDER']
os.makedirs(data_dir,exist_ok=True)
tokens=[r['token'] for r in csv.DictReader(open(os.path.join(BASE,'token_uji.csv')))]
ok=gagal=0
for i,tok in enumerate(tokens):
    p=A.load_verify_payload(tok)
    if not p: gagal+=1; continue
    d=p.get('data') if isinstance(p,dict) else None
    if not d: gagal+=1; continue
    uid=str(d.get('id','')).strip()
    fn=f"qr_{uid}_{secrets.token_hex(4)}.json"
    A.save_qr_record(os.path.join(data_dir,fn), d)
    ok+=1
    if (i+1)%20000==0: print(f'  {i+1}/{len(tokens)}',flush=True)
print(f'rekaman ditulis: {ok} | gagal: {gagal}')
