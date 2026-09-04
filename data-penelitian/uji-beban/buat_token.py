"""Bangkitkan kumpulan token verifikasi di lingkungan staging untuk uji beban."""
import os,sys,json,base64,csv
from datetime import datetime,timedelta,timezone
BASE='/opt/qrcode-staging'
os.chdir(BASE); sys.path.insert(0,BASE)
from Crypto.Hash import SHA256
from Crypto.Signature import pss
import app as A
WIB=timezone(timedelta(hours=7))
N=int(sys.argv[1]) if len(sys.argv)>1 else 2000
NAMA=['Andi Pratama','Siti Rahayu','Budi Santoso','Dewi Lestari','Eko Wijaya']
tokens=[]
for i in range(N):
    data={'nama':NAMA[i%len(NAMA)],'id':f'UJI{i:07d}',
          'timestamp':datetime.now(WIB).isoformat(),'nonce':A.generate_qr_nonce(),
          'qr_modules':49,'qr_version':7}
    h=SHA256.new(json.dumps(data,sort_keys=True).encode())
    sig=base64.b64encode(pss.new(A.private_key,salt_bytes=8).sign(h)).decode()
    tok=A.save_verify_payload({'data':data,'signature':sig,'alg':'RSA'})
    tokens.append(tok)
    if (i+1)%500==0: print(f'  {i+1}/{N}',flush=True)
out=os.path.join(BASE,'token_uji.csv')
with open(out,'w',newline='') as f:
    w=csv.writer(f); w.writerow(['token'])
    for t in tokens: w.writerow([t])
print(f'{len(tokens)} token ditulis ke {out}')
print('contoh:',tokens[0])
