from pathlib import Path
from html import escape


OUT = Path(__file__).resolve().parent


CSS = """
.bg{fill:#f8fafc}.title{font:700 30px Arial,sans-serif;fill:#0f172a}.subtitle{font:400 16px Arial,sans-serif;fill:#475569}
.box{fill:#fff;stroke:#2563eb;stroke-width:3;rx:14}.soft{fill:#eff6ff;stroke:#1d4ed8;stroke-width:3;rx:14}
.green{fill:#f0fdf4;stroke:#16a34a;stroke-width:3;rx:14}.orange{fill:#fff7ed;stroke:#ea580c;stroke-width:3;rx:14}
.pink{fill:#fdf2f8;stroke:#db2777;stroke-width:3;rx:14}.red{fill:#fee2e2;stroke:#dc2626;stroke-width:3;rx:14}
.yellow{fill:#fef9c3;stroke:#ca8a04;stroke-width:3;rx:14}.gray{fill:#f1f5f9;stroke:#64748b;stroke-width:3;rx:14}
.phone{fill:#111827;stroke:#020617;stroke-width:3;rx:34}.screen{fill:#f8fafc;stroke:#cbd5e1;stroke-width:2;rx:24}
.label{font:700 16px Arial,sans-serif;fill:#111827}.small{font:400 13px Arial,sans-serif;fill:#374151}.tiny{font:400 11px Arial,sans-serif;fill:#475569}
.flow{stroke:#334155;stroke-width:2.3;fill:none;marker-end:url(#arrow)}.dash{stroke:#64748b;stroke-width:2;fill:none;stroke-dasharray:6 6;marker-end:url(#arrow)}
.lane{fill:#e0f2fe;stroke:#0284c7;stroke-width:2;rx:18;opacity:.55}.lane2{fill:#ffedd5;stroke:#fb923c;stroke-width:2;rx:18;opacity:.55}
"""


def t(x, y, lines, cls="label", anchor="middle", gap=20):
    if isinstance(lines, str):
        lines = [lines]
    out = [f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{cls}">']
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else gap
        out.append(f'<tspan x="{x}" dy="{dy}">{escape(str(line))}</tspan>')
    out.append('</text>')
    return ''.join(out)


def rect(x, y, w, h, cls="box"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{cls}"/>'


def line(x1, y1, x2, y2, cls="flow"):
    return f'<path d="M{x1} {y1} L{x2} {y2}" class="{cls}"/>'


def curve(path, cls="flow"):
    return f'<path d="{path}" class="{cls}"/>'


def diamond(cx, cy, w, h, cls="yellow"):
    pts = f'{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}'
    return f'<polygon points="{pts}" class="{cls}"/>'


def header(title, subtitle):
    return [t(0, 0, ''), t(0, 0, '')][0] if False else [
        t(0, 0, ''),
    ]


def save(name, w, h, title, subtitle, body):
    marker = '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#334155"/></marker>'
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<defs>', f'<style>{CSS}</style>', marker, '</defs>',
        f'<rect class="bg" width="{w}" height="{h}"/>',
        t(w/2, 44, title, 'title'),
        t(w/2, 72, subtitle, 'subtitle'),
        *body,
        '</svg>'
    ]
    (OUT / name).write_text('\n'.join(svg), encoding='utf-8')


def labeled_box(x, y, w, h, title, detail=None, cls='box'):
    body = [rect(x, y, w, h, cls), t(x+w/2, y+30, title, 'label')]
    if detail:
        body.append(t(x+w/2, y+56, detail, 'small', gap=18))
    return body


def business_crypto():
    b=[]
    boxes=[
        (70,150,190,90,'Input Bisnis',['Nama','ID','kebutuhan validasi'],'soft'),
        (310,150,190,90,'Data QR',['timestamp','nonce','qr metadata'],'box'),
        (550,150,190,90,'Canonical JSON',['sort_keys=True','format stabil'],'box'),
        (790,150,190,90,'Hash SHA-256',['digest data'],'box'),
        (1030,150,190,90,'Digital Signature',['RSA-PSS / ECDSA','private key'],'orange'),
        (1030,360,190,90,'Payload QR',['data + signature','metadata alg'],'green'),
        (790,360,190,90,'QR Code',['PNG / URL pendek','/v/<token>'],'green'),
        (550,360,190,90,'Verifikasi Lapis 1',['verify signature','integritas'],'soft'),
        (310,360,190,90,'Verifikasi Lapis 2',['original data','nonce replay'],'orange'),
        (70,360,190,90,'Status Akhir',['valid / replay','data palsu'],'pink'),
    ]
    for bx in boxes: b += labeled_box(*bx)
    for x1,y1,x2,y2 in [(260,195,310,195),(500,195,550,195),(740,195,790,195),(980,195,1030,195),(1125,240,1125,360),(1030,405,980,405),(790,405,740,405),(550,405,500,405),(310,405,260,405)]: b.append(line(x1,y1,x2,y2))
    b += [rect(285,560,710,110,'gray'), t(640,594,'Makna desain kriptograf','label'), t(640,624,['Signature membuktikan autentisitas dan integritas.','Nonce state membuktikan QR belum pernah dipakai ulang.'],'small')]
    save('analisis_crypto_architecture.svg',1280,740,'Arsitektur Kebutuhan Bisnis dan Kriptograf','Alur dari data bisnis sampai status verifikasi QR',b)


def business_compare():
    b=[]
    b += [rect(90,130,500,430,'soft'), t(340,165,'RSA-PSS 2048-bit','label'), t(340,200,['Kuat dan matang untuk tanda tangan digital','Ukuran signature besar','Cocok sebagai baseline keamanan sistem','Saat ini memakai SHA-256 dan salt 8 byte'],'small',gap=28)]
    b += [rect(690,130,500,430,'green'), t(940,165,'ECDSA P-256','label'), t(940,200,['Signature lebih ringkas untuk QR','Perlu nonce internal algoritma yang aman','Cocok untuk payload kecil dan mobile scan','Alternatif ketika ukuran QR menjadi masalah'],'small',gap=28)]
    b += [rect(250,610,780,90,'orange'), t(640,642,'Rekomendasi Sistem','label'), t(640,670,['RSA-PSS tetap menjadi mode utama. ECDSA dapat dipertahankan sebagai opsi efisiensi ukuran QR.','Keduanya perlu key_id, rotasi kunci, dan certificate chain untuk roadmap kepatuhan.'],'small',gap=22)]
    save('analisis_rsa_ecdsa_comparison.svg',1280,760,'Perbandingan RSA-PSS dan ECDSA P-256','Kajian algoritma untuk QR Code bertanda tangan digital',b)


def business_iso():
    b=[]
    stages=[('Kondisi Saat Ini',['payload custom','RSA-PSS/ECDSA','nonce replay online'],'soft'),('Gap Kepatuhan',['belum DigSig resmi','belum X.509/PKI','offline verify belum penuh'],'yellow'),('Target Penguatan',['envelope DigSig','certificate chain','schema data carrier'],'orange'),('ISO Alignment',['offline integrity','issuer trust','interoperability'],'green')]
    x=80
    for title, detail, cls in stages:
        b += labeled_box(x,180,240,150,title,detail,cls)
        x += 300
    for x1 in [320,620,920]: b.append(line(x1,255,x1+60,255))
    b += [rect(190,470,900,120,'gray'), t(640,506,'Status Pernyataan yang Aman','label'), t(640,536,['Sistem sudah mengarah ke prinsip ISO/IEC 20248:2022, tetapi belum dapat diklaim fully compliant.','Klaim penuh membutuhkan DigSig envelope resmi, X.509/PKI, dan verifikasi offline penuh.'],'small',gap=24)]
    save('analisis_iso20248_gap_roadmap.svg',1280,760,'Roadmap ISO/IEC 20248:2022 Alignment','Peta gap dari implementasi saat ini menuju kepatuhan yang lebih kuat',b)


def business_replay():
    b=[]
    b += labeled_box(70,150,210,90,'QR Asli',['signature valid','data original'],'green')
    b += labeled_box(350,150,210,90,'Scan Pertama',['nonce usage=1','status valid'],'green')
    b += labeled_box(630,150,210,90,'Scan Kedua',['nonce usage>1','status replay'],'yellow')
    b += labeled_box(910,150,210,90,'Scan Berikutnya',['count bertambah','tetap replay'],'yellow')
    for x1 in [280,560,840]: b.append(line(x1,195,x1+70,195))
    b += labeled_box(70,390,210,90,'QR Diubah',['nama/id/timestamp','berbeda'],'red')
    b += labeled_box(350,390,210,90,'Banding Original',['changed_fields','terdeteksi'],'orange')
    b += labeled_box(630,390,210,90,'Klasifikasi',['data palsu','bukan replay'],'red')
    b += labeled_box(910,390,210,90,'Log Verifikasi',['status + detail','audit trail'],'gray')
    for x1 in [280,560,840]: b.append(line(x1,435,x1+70,435))
    b += [rect(230,590,820,70,'soft'), t(640,620,'Aturan utama: replay hanya sah untuk QR asli dengan signature valid dan data exact match.','label')]
    save('analisis_replay_mitigation.svg',1280,740,'Mitigasi Replay Attack','Perbedaan alur QR asli yang dipakai ulang dan QR yang datanya dimodifikasi',b)


def storage_arch():
    b=[]
    b += labeled_box(500,130,280,95,'Flask Application',['controller','crypto','QR processing'],'orange')
    stores=[(80,310,'SQLite Nonce State',['security_state.db','nonce_state'],'green'),(380,310,'CSV Event Logs',['generate','verifikasi','audit'],'green'),(680,310,'JSON Task/Payload',['task_results','verify_payloads'],'soft'),(980,310,'PNG/File Storage',['qr','uploads','qr_massal'],'soft'),(380,520,'QR Stats JSON',['qr_stats.json','dashboard summary'],'gray'),(680,520,'Rotating App Log',['app.log','app.log.1-10'],'gray')]
    for x,y,title,det,cls in stores: b += labeled_box(x,y,220,90,title,det,cls)
    for x in [190,490,790,1090,490,790]: b.append(curve(f'M640 225 C640 270 {x} 270 {x} 310' if x in [190,490,790,1090] else f'M640 225 C640 430 {x} 455 {x} 520'))
    b += [rect(260,660,760,70,'yellow'), t(640,690,'Storage hybrid dipilih agar mudah dioperasikan, tetapi log produksi sebaiknya dimigrasikan ke SQLite/PostgreSQL.','label')]
    save('storage_architecture_overview.svg',1280,780,'Arsitektur Basis Data dan Log Storage','Pemetaan storage hybrid pada QR Code Security System',b)


def storage_nonce_lock():
    b=[]
    b += labeled_box(80,140,210,80,'Request A',['scan QR','nonce N'],'soft')
    b += labeled_box(80,360,210,80,'Request B',['scan QR sama','nonce N'],'soft')
    b += labeled_box(380,140,240,80,'SQLite Atomic Upsert',['INSERT ON CONFLICT','usage_count + 1'],'green')
    b += labeled_box(700,140,210,80,'Usage Count',['1 = valid','>1 = replay'],'yellow')
    b += labeled_box(380,360,240,80,'File Lock Fallback',['used_nonces.txt.lock','exclusive create'],'orange')
    b += labeled_box(700,360,210,80,'Backup Append',['used_nonces.txt','audit fallback'],'gray')
    for y in [180,400]:
        b.append(line(290,y,380,y)); b.append(line(620,y,700,y))
    b += [rect(250,570,780,90,'red'), t(640,604,'Catatan Risiko','label'), t(640,632,'File lock belum memiliki stale-lock recovery berbasis PID/timestamp, sehingga perlu diperkuat untuk produksi multi-worker.','small')]
    save('storage_nonce_file_locking.svg',1280,760,'Skema File-Locking dan Atomic Nonce Usage','Desain replay-state utama memakai SQLite, file-lock menjadi fallback/backup',b)


def storage_logging():
    b=[]
    left=[('Generate QR',['data','sign','qr','save']),('Verifikasi QR',['load','decode','verify','db'])]
    y=150
    for title, steps in left:
        b += labeled_box(70,y,220,95,title,steps,'soft')
        y += 190
    b += labeled_box(380,210,220,95,'Timer',['time.perf_counter','6 decimal seconds'],'orange')
    b += labeled_box(700,130,230,95,'CSV Generate Log',['subprocess timing','file size/dimensi'],'green')
    b += labeled_box(700,330,230,95,'CSV Verify Log',['status keamanan','load/decode/verify/db'],'green')
    b += labeled_box(1010,230,220,95,'Dashboard',['mean median','p95 p99 grade'],'yellow')
    b.append(line(290,195,380,245)); b.append(line(290,385,380,265)); b.append(line(600,245,700,175)); b.append(line(600,265,700,375)); b.append(line(930,175,1010,260)); b.append(line(930,375,1010,290))
    b += [rect(260,560,760,80,'gray'), t(640,590,'High-resolution logging mencatat durasi subproses, bukan hanya total waktu.','label'), t(640,615,'Data ini dipakai untuk dashboard performa, p95/p99, outlier, dan evaluasi response time.','small')]
    save('storage_high_resolution_logging.svg',1280,740,'Arsitektur High-Resolution Logging','Alur timer detail dari proses generate/verifikasi menuju dashboard performa',b)


def storage_target_schema():
    b=[]
    tables=[('nonce_state',['PK nonce','first_used_at','last_used_at','usage_count'],'orange'),('generate_events',['event_id','qr_data_id','timing','file metadata'],'green'),('verify_events',['event_id','status_code','changed_fields','timing'],'green'),('audit_events',['event_id','actor','action','detail_json'],'gray')]
    x=100
    for title, fields, cls in tables:
        b += labeled_box(x,170,240,220,title,fields,cls); x += 300
    b += [rect(210,530,860,90,'soft'), t(640,563,'Target Desain Produksi','label'), t(640,592,'CSV menjadi format export, sedangkan event log utama pindah ke SQLite/PostgreSQL dengan index dan event_id.','small')]
    save('storage_target_database_schema.svg',1280,720,'Target Database-Backed Event Log','Skema penguatan dari CSV log menuju database event terstruktur',b)


def ui_dashboard():
    b=[]
    b += [rect(90,110,1100,85,'soft'), t(640,143,'Dashboard QR Code Security','label'), t(640,168,'[Home]  [Verifikasi]  [CSV Generator]','small')]
    x=90
    for title in ['Total QR','Total Verifikasi','Median Generate','P95 Verify']:
        b += labeled_box(x,230,245,95,title,['angka utama','badge/progress'],'green'); x += 285
    b += labeled_box(90,370,690,170,'Performa Generate QR',['Total QR','QR/detik','KB/QR'],'box')
    b += labeled_box(820,370,370,170,'Statistik Dimensi QR',['avg','min / max'],'box')
    b += labeled_box(90,580,1100,120,'Analisis Waktu + File + Performa',['generate vs verify','statistik file','grade dan metodologi'],'orange')
    save('ui_dashboard_wireframe.svg',1280,780,'Wireframe Dashboard Operasional','Struktur visual dashboard untuk monitoring statistik dan performa',b)


def ui_scanner():
    b=[]
    b += [rect(90,105,1100,80,'soft'), t(640,137,'Verifikasi QR Code','label'), t(640,162,'[Home]     Verifikasi keaslian dan integritas QR Code','small')]
    b += [rect(90,215,1100,55,'gray'), t(290,250,'Tab: Verifikasi Tunggal','label'), t(590,250,'Tab: Verifikasi Massal','label')]
    b += labeled_box(110,310,670,190,'Upload Area',['drag & drop file QR','pilih file','format PNG/JPG'],'box')
    b += labeled_box(830,310,330,190,'Action Panel',['[Verifikasi QR]','[Pilih File]','info validasi'],'orange')
    b += labeled_box(110,550,1050,140,'Result Card',['badge status: valid / replay / data palsu','data QR + timing + signature','shortcut scanner HP / USB / log / dashboard'],'green')
    save('ui_scanner_workspace_wireframe.svg',1280,760,'Wireframe Scanner Workspace','Rancangan workspace verifikasi QR tunggal dan massal',b)


def ui_mobile():
    b=[]
    b += [rect(465,105,350,610,'phone'), rect(485,130,310,560,'screen')]
    b += [rect(510,155,260,50,'soft'), t(640,185,'Home | Scanner HP','label')]
    b += [rect(520,225,240,210,'gray'), t(640,310,'Preview Kamera','label'), rect(575,275,130,130,'box')]
    b += [rect(520,455,110,46,'green'), t(575,484,'Mulai','small'), rect(650,455,110,46,'red'), t(705,484,'Stop','small')]
    b += [rect(520,520,240,52,'yellow'), t(640,552,'Status scan / kamera','small')]
    b += [rect(520,590,240,50,'box'), t(640,620,'Input manual + Buka','small')]
    b += [rect(160,260,230,100,'orange'), t(275,295,'Prioritas UX','label'), t(275,323,['kamera di atas','fallback manual'],'small')]
    b.append(line(390,310,520,310))
    save('ui_mobile_scanner_wireframe.svg',1280,780,'Wireframe Mobile Scanner HP','Preview kamera ditempatkan di atas agar siap dipakai di lapangan',b)


def ui_flow():
    b=[]
    actors=[('Admin',['Dashboard','Log','Generate']),('Operator',['Scanner File','Massal','USB']),('Petugas HP',['Mobile Scan','Redirect hasil']),('Auditor',['Log Generate','Log Verifikasi','Audit Log'])]
    x=80
    for title, pages in actors:
        b += labeled_box(x,170,240,180,title,pages,'soft'); x += 300
    b += labeled_box(410,500,460,100,'Prinsip UX Bersama',['status jelas','navigasi Home konsisten','detail teknis setelah ringkasan'],'orange')
    for x in [200,500,800,1100]: b.append(line(x,350,640,500))
    save('ui_user_flow_overview.svg',1280,720,'Peta Alur Pengguna UI/UX','Hubungan persona dengan halaman utama sistem',b)


def sdd_architecture():
    b=[]
    b += labeled_box(70,140,220,100,'Browser',['admin/operator','desktop/mobile'],'soft')
    b += labeled_box(390,140,230,100,'Flask App',['routes','templates','services'],'orange')
    b += labeled_box(720,95,220,85,'Crypto Engine',['RSA-PSS','ECDSA SHA-256'],'green')
    b += labeled_box(720,220,220,85,'QR Engine',['qrcode','decode QR'],'green')
    b += labeled_box(1020,80,200,80,'SQLite',['nonce_state'],'yellow')
    b += labeled_box(1020,190,200,80,'JSON/PNG',['payload','QR artifact'],'soft')
    b += labeled_box(1020,300,200,80,'CSV Logs',['generate','verify','audit'],'gray')
    for y in [190]: b.append(line(290,y,390,y))
    b.append(line(620,170,720,137)); b.append(line(620,190,720,262)); b.append(line(940,137,1020,120)); b.append(line(940,262,1020,230)); b.append(line(620,220,1020,340))
    b += [rect(245,500,790,90,'gray'), t(640,535,'Pola arsitektur: server-side rendered Flask monolith dengan storage hybrid.','label'), t(640,562,'Task massal diproses via background thread dan snapshot JSON.','small')]
    save('sdd_system_architecture.svg',1280,700,'Arsitektur Sistem Tingkat Tinggi','Komponen aplikasi, engine, dan storage utama',b)


def sdd_generate_flow():
    b=[]
    steps=['Input nama/ID','Bentuk data + nonce','Canonical JSON','SHA-256','Sign RSA/ECDSA','Buat payload URL','Render QR PNG','Simpan + log']
    x=40
    for i,s in enumerate(steps):
        b += labeled_box(x,220,135,95,str(i+1)+'. '+s,None,'green' if i in [5,6,7] else 'soft')
        if i < len(steps)-1: b.append(line(x+135,267,x+160,267))
        x += 155
    b += [rect(260,470,760,80,'orange'), t(640,503,'Output: QR PNG, JSON original, payload token, log_generate.csv, dan statistik dashboard.','label')]
    save('sdd_flowchart_generate_qr.svg',1280,650,'Flowchart Generate QR Tunggal','Urutan proses dari input bisnis sampai QR tersimpan',b)


def sdd_dfd_l2_generate():
    b=[]
    b += labeled_box(50,250,160,70,'Admin',None,'soft')
    procs=[('1.1 Validasi','input'),('1.2 Data QR','timestamp nonce'),('1.3 Hash & Sign','private key'),('1.4 Payload URL','token'),('1.5 Render QR','PNG'),('1.6 Simpan Log','CSV/JSON')]
    x=280
    for title,det in procs:
        b += labeled_box(x,230,145,90,title,det,'orange'); x += 165
    stores=[('Private Key',420,430),('Data JSON',750,430),('QR PNG',930,430),('Generate Log',1110,430)]
    for title,x,y in stores: b += labeled_box(x,y,135,70,title,None,'green')
    b.append(line(210,285,280,275))
    for x in [425,590,755,920,1085]: b.append(line(x,275,x+20,275))
    b.append(line(520,430,520,320)); b.append(line(1115,320,820,430)); b.append(line(1115,320,995,430)); b.append(line(1115,320,1175,430))
    save('sdd_dfd_level_2_generate.svg',1280,650,'DFD Level 2 - Generate QR','Aliran data pada proses pembuatan QR bertanda tangan digital',b)


def sdd_dfd_l2_verify():
    b=[]
    nodes=[('Input QR','file / HP / USB'),('Decode Payload','image/token/url'),('Lapis 1 Crypto','verify signature'),('Lapis 2 State','original + nonce'),('Klasifikasi','valid/replay/palsu'),('Render + Log','hasil + CSV')]
    x=70
    for title,det in nodes:
        b += labeled_box(x,190,170,90,title,det,'orange' if 'Lapis' in title else 'soft')
        if x<940: b.append(line(x+170,235,x+200,235))
        x += 205
    stores=[('Public Key',440,390),('Data Original',650,390),('Nonce SQLite',860,390),('Verify Log CSV',1070,390)]
    for title,x,y in stores: b += labeled_box(x,y,160,70,title,None,'green')
    b.append(line(525,390,560,280)); b.append(line(730,390,765,280)); b.append(line(940,390,970,280)); b.append(line(1150,390,1115,280))
    save('sdd_dfd_level_2_verify.svg',1280,650,'DFD Level 2 - Verifikasi QR','Aliran data verifikasi dengan pemisahan crypto dan state',b)


def sdd_dash_log():
    b=[]
    b += labeled_box(80,210,190,80,'Admin/Auditor',None,'soft')
    b += labeled_box(380,130,210,80,'Baca Generate Log',None,'orange')
    b += labeled_box(380,290,210,80,'Baca Verify Log',None,'orange')
    b += labeled_box(690,210,210,80,'Hitung Statistik',['mean median','p95 p99'],'yellow')
    b += labeled_box(1010,130,190,80,'Dashboard',None,'green')
    b += labeled_box(1010,290,190,80,'Export / Filter',None,'green')
    b += labeled_box(380,480,210,70,'Audit Log CSV',None,'gray')
    b.append(line(270,250,380,170)); b.append(line(270,250,380,330)); b.append(line(590,170,690,240)); b.append(line(590,330,690,260)); b.append(line(900,250,1010,170)); b.append(line(900,250,1010,330)); b.append(line(485,480,1010,330))
    save('sdd_dfd_level_2_dashboard_log.svg',1280,680,'DFD Level 2 - Dashboard dan Log','Aliran data dari CSV log menuju dashboard, filter, dan export',b)


def sdd_replay_classification():
    b=[]
    b += labeled_box(60,210,190,80,'Payload + Signature',None,'soft')
    b += [diamond(360,250,180,90), t(360,246,['Original','ditemukan?'],'label',gap=18)]
    b += [diamond(610,250,180,90), t(610,246,['Exact','match?'],'label',gap=18)]
    b += [diamond(860,250,180,90), t(860,246,['Signature','valid?'],'label',gap=18)]
    b += [diamond(1110,250,180,90), t(1110,246,['Nonce','used?'],'label',gap=18)]
    b += labeled_box(260,430,190,75,'Data Palsu',None,'red')
    b += labeled_box(520,430,190,75,'Data Dimodifikasi',None,'red')
    b += labeled_box(770,430,190,75,'Signature Invalid',None,'red')
    b += labeled_box(1020,430,190,75,'Replay Attack',None,'yellow')
    b += labeled_box(1020,90,190,75,'Valid Authentik',None,'green')
    for x1,x2 in [(250,270),(450,520),(700,770),(950,1020)]: b.append(line(x1,250,x2,250))
    b.append(line(1110,205,1110,165)); b.append(line(1110,295,1110,430)); b.append(line(860,295,860,430)); b.append(line(610,295,610,430)); b.append(line(360,295,360,430))
    save('sdd_flowchart_replay_classification.svg',1280,650,'Flowchart Klasifikasi Replay dan Data Palsu','Aturan keputusan agar data palsu tidak keliru menjadi replay',b)


def sdd_massal_hp_usb_sqlite():
    # Massal
    b=[]
    steps=['Upload banyak file','Validasi file','>5 file?','Task async / direct','Loop verifikasi 2-lapis','Ringkasan hasil','Log per file']
    x=80
    for i,s in enumerate(steps):
        b += labeled_box(x,220,145,90,s,None,'yellow' if '?' in s else 'soft')
        if i<len(steps)-1: b.append(line(x+145,265,x+175,265))
        x += 175
    save('sdd_flowchart_verify_massal.svg',1360,620,'Flowchart Verifikasi Massal','Direct untuk batch kecil, async task untuk file banyak',b)
    # HP
    b=[]; steps=['Buka /mobile_scan','Izin kamera','QR terbaca','Resolve target','Redirect URL','Verifikasi 2-lapis','Render hasil']
    x=70
    for i,s in enumerate(steps):
        b += labeled_box(x,220,150,90,s,None,'green' if i in [5,6] else 'soft')
        if i<len(steps)-1: b.append(line(x+150,265,x+180,265))
        x += 180
    b += labeled_box(430,430,420,70,'Fallback: input manual jika kamera gagal',None,'orange')
    save('sdd_flowchart_mobile_scanner.svg',1360,620,'Flowchart Kamera HP','Alur mobile scanner dari preview kamera sampai hasil verifikasi',b)
    # USB
    b=[]; steps=['Buka /verify_direct','Input fokus','Scanner kirim Enter','Decode string','Verifikasi 2-lapis','JSON hasil','Siap scan lagi']
    x=70
    for i,s in enumerate(steps):
        b += labeled_box(x,220,150,90,s,None,'green' if i in [4,5] else 'soft')
        if i<len(steps)-1: b.append(line(x+150,265,x+180,265))
        x += 180
    save('sdd_flowchart_usb_scanner.svg',1360,620,'Flowchart Scanner USB / Direct Scanner','Alur front-desk untuk scan berulang dengan input fokus otomatis',b)
    # SQLite ERD
    b=[]
    b += labeled_box(220,180,300,210,'nonce_state',['PK nonce','first_used_at','last_used_at','usage_count'],'orange')
    b += labeled_box(760,180,300,170,'security_metadata',['PK key','value','updated_at'],'orange')
    b += [rect(340,500,600,80,'gray'), t(640,532,'SQLite fisik saat ini hanya menyimpan state keamanan replay dan metadata migrasi.','label')]
    save('sdd_erd_sqlite.svg',1280,680,'ERD Fisik SQLite Saat Ini','Tabel security_state.db yang dipakai untuk replay-state nonce',b)


def deployment_architecture():
    b=[]
    b += labeled_box(60,150,190,90,'Client',['Browser desktop','Kamera HP / scanner'],'soft')
    b += labeled_box(330,150,210,90,'DNS',['rsa-pss.com','A record -> IP server'],'gray')
    b += labeled_box(620,120,230,120,'Nginx',['reverse proxy','SSL/TLS termination','upload limit 500M'],'green')
    b += labeled_box(940,150,230,90,'Gunicorn WSGI',['127.0.0.1:5000','wsgi:app'],'orange')
    b += labeled_box(940,330,230,90,'Flask App',['routes/templates','crypto + QR logic'],'soft')
    b += labeled_box(620,500,230,90,'Local Storage',['PNG / JSON / CSV','SQLite nonce_state'],'yellow')
    b += labeled_box(300,500,230,90,'systemd',['qrcode.service','restart + journal'],'gray')
    b += labeled_box(60,500,190,90,'Certbot',['Let\'s Encrypt','renewal otomatis'],'green')
    b.append(line(250,195,330,195)); b.append(line(540,195,620,180)); b.append(line(850,180,940,195)); b.append(line(1055,240,1055,330)); b.append(line(1055,420,735,500)); b.append(line(415,500,940,195)); b.append(line(155,500,620,180))
    b += [rect(220,660,840,70,'gray'), t(640,690,'Publik hanya membuka HTTP/HTTPS ke Nginx. Gunicorn tetap bind lokal 127.0.0.1.','label')]
    save('deployment_architecture_nginx_gunicorn_ssl.svg',1280,780,'Arsitektur Deployment Produksi','Nginx sebagai reverse proxy + SSL/TLS, Gunicorn sebagai WSGI server, Flask sebagai aplikasi',b)


def deployment_request_flow():
    b=[]
    steps=[('1. HTTPS Request','client -> rsa-pss.com'),('2. TLS Handshake','sertifikat Let\'s Encrypt'),('3. Nginx Proxy','header X-Forwarded-*'),('4. Gunicorn','worker/thread WSGI'),('5. Flask App','route + business logic'),('6. Storage','log / QR / SQLite'),('7. Response','HTML/JSON/file')]
    x=45
    for i,(title,det) in enumerate(steps):
        b += labeled_box(x,220,155,100,title,det,'green' if i in [1,2] else ('orange' if i in [3,4] else 'soft'))
        if i < len(steps)-1:
            b.append(line(x+155,270,x+180,270))
        x += 180
    b += [rect(250,470,780,90,'yellow'), t(640,503,'Header proxy penting','label'), t(640,532,'Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host, X-Forwarded-Port.','small')]
    save('deployment_request_flow_ssl.svg',1320,700,'Alur Request HTTPS Produksi','Perjalanan request dari browser sampai Flask dan kembali ke client',b)


def deployment_systemd_runtime():
    b=[]
    b += labeled_box(70,160,220,90,'systemctl',['enable --now','restart/status'],'gray')
    b += labeled_box(370,160,250,90,'qrcode.service',['User=www-data','WorkingDirectory=/opt/qrcode'],'orange')
    b += labeled_box(700,160,230,90,'Environment',['.env','HOST/PORT/BASE_URL'],'soft')
    b += labeled_box(1010,160,210,90,'Gunicorn',['workers=1','threads=4','timeout=300'],'green')
    b += labeled_box(1010,350,210,90,'wsgi.py',['start scheduler','import app'],'soft')
    b += labeled_box(700,350,230,90,'Flask app',['app.py','cleanup scheduler'],'soft')
    b += labeled_box(370,350,250,90,'Logs',['journalctl','logs/app.log'],'gray')
    for x1,x2 in [(290,370),(620,700),(930,1010)]: b.append(line(x1,205,x2,205))
    b.append(line(1115,250,1115,350)); b.append(line(1010,395,930,395)); b.append(line(700,395,620,395)); b.append(line(495,350,495,250))
    b += [rect(230,560,820,82,'red'), t(640,592,'Catatan penting','label'), t(640,620,'Jangan menaikkan workers di atas 1 jika scheduler internal belum dipisah, agar cleanup tidak berjalan dobel.','small')]
    save('deployment_systemd_gunicorn_runtime.svg',1280,740,'Runtime systemd dan Gunicorn','Service production menjalankan Gunicorn wsgi:app sebagai user www-data',b)


def deployment_tls_renewal():
    b=[]
    b += labeled_box(80,160,210,90,'DNS Ready',['A record','domain -> server'],'soft')
    b += labeled_box(360,160,210,90,'Nginx HTTP',['port 80','server_name valid'],'green')
    b += labeled_box(640,160,210,90,'Certbot',['--nginx','request cert'],'orange')
    b += labeled_box(920,160,210,90,'Let\'s Encrypt',['validasi domain','issue certificate'],'green')
    b += labeled_box(640,380,210,90,'Nginx HTTPS',['port 443','redirect HTTP'],'green')
    b += labeled_box(920,380,210,90,'Auto Renewal',['certbot timer','renewal test'],'gray')
    for x1,x2 in [(290,360),(570,640),(850,920)]: b.append(line(x1,205,x2,205))
    b.append(curve('M1025 250 C1025 320 790 340 745 380'))
    b.append(line(850,425,920,425))
    b += [rect(260,590,760,70,'yellow'), t(640,620,'Setelah SSL aktif: BASE_URL=https://rsa-pss.com/, REQUIRE_HTTPS=True, TRUST_PROXY_HEADERS=True.','label')]
    save('deployment_ssl_tls_certbot_flow.svg',1280,740,'Alur Setup SSL/TLS dengan Certbot','Dari DNS dan Nginx HTTP menuju sertifikat HTTPS dan renewal otomatis',b)


def deployment_checklist():
    b=[]
    cols=[('1. Server',['Ubuntu 24.04','user sudo','DNS domain']),('2. App',['/opt/qrcode','venv','requirements']),('3. Runtime',['.env','systemd','Gunicorn']),('4. Edge',['Nginx','SSL/TLS','Firewall']),('5. Verify',['curl local','curl HTTPS','journal/log'])]
    x=55
    for title,items in cols:
        b += labeled_box(x,170,220,260,title,items,'green')
        x += 245
    b += [rect(220,550,840,85,'gray'), t(640,583,'Kriteria selesai','label'), t(640,612,'Aplikasi hanya bind lokal, domain HTTPS aktif, QR baru memakai BASE_URL publik, log service bersih.','small')]
    save('deployment_production_checklist.svg',1280,720,'Checklist Deployment Produksi','Urutan validasi instalasi, konfigurasi, reverse proxy, SSL/TLS, dan monitoring',b)


def manual_documentation_map():
    b=[]
    b += labeled_box(500,120,280,95,'Dokumentasi 3.4',['User Manual','Dokumen Teknis','Serah Terima Source Code'],'orange')
    nodes=[
        (70,300,'Panduan Pengguna',['login','generate','verifikasi'],'green'),
        (360,300,'Panduan Admin',['dashboard','log','audit'],'green'),
        (650,300,'Panduan Teknis',['struktur kode','config','operasi'],'soft'),
        (940,300,'Serah Terima',['source','env','key','backup'],'yellow'),
        (360,520,'Lampiran SOP',['troubleshooting','checklist','kontak'],'gray'),
        (650,520,'Bukti Penerimaan',['uji fungsi','sign-off','catatan risiko'],'pink'),
    ]
    for x,y,title,items,cls in nodes:
        b += labeled_box(x,y,230,110,title,items,cls)
        b.append(line(640,215,x+115,y))
    save('manual_documentation_map.svg',1280,760,'Peta Dokumentasi Teknis dan User Manual','Struktur dokumen 3.4 untuk penggunaan, operasi, dan serah terima source code',b)


def manual_operator_workflow():
    b=[]
    steps=[('Login','masuk admin'),('Home','pilih fitur'),('Generate QR','tunggal / CSV'),('Verifikasi','file / massal'),('Scanner HP/USB','scan langsung'),('Hasil','valid / replay / palsu'),('Log','audit hasil')]
    x=45
    for i,(title,det) in enumerate(steps):
        b += labeled_box(x,220,155,100,title,det,'green' if i in [2,3,4] else 'soft')
        if i < len(steps)-1:
            b.append(line(x+155,270,x+180,270))
        x += 180
    b += [rect(260,500,760,82,'yellow'), t(640,532,'Aturan operasional','label'), t(640,560,'Scan pertama QR asli menghasilkan valid; scan ulang QR yang sama menghasilkan replay attack.','small')]
    save('manual_operator_workflow.svg',1320,720,'Alur Penggunaan Operator','Urutan penggunaan sistem dari login sampai pencatatan log verifikasi',b)


def manual_admin_audit_workflow():
    b=[]
    b += labeled_box(70,160,220,100,'Admin',['dashboard','reset statistik','job massal'],'soft')
    b += labeled_box(370,110,230,90,'Dashboard',['KPI','P95','valid rate'],'green')
    b += labeled_box(370,260,230,90,'Log Generate',['preview QR','export Excel'],'green')
    b += labeled_box(680,260,230,90,'Log Verifikasi',['filter sumber','status keamanan'],'green')
    b += labeled_box(990,260,230,90,'Audit Log',['aksi admin','IP/user agent'],'gray')
    b += labeled_box(680,450,230,90,'Laporan',['CSV/Excel','bukti pengujian'],'yellow')
    b.append(line(290,200,370,155)); b.append(line(290,210,370,305)); b.append(line(600,305,680,305)); b.append(line(910,305,990,305)); b.append(line(795,350,795,450)); b.append(line(1105,350,795,450)); b.append(line(485,350,795,450))
    b += [rect(245,610,790,70,'gray'), t(640,640,'Audit trail dibaca dari log generate, log verifikasi, dan audit log untuk kebutuhan pemeriksaan.','label')]
    save('manual_admin_audit_workflow.svg',1280,760,'Alur Admin dan Audit','Monitoring dashboard, pembacaan log, export, dan audit trail',b)


def manual_source_handover_package():
    b=[]
    items=[
        ('Source Code',['app.py','routes/modules','templates/static'],'soft'),
        ('Konfigurasi',['.env.example','nginx','systemd'],'orange'),
        ('Kunci & Secret',['rsa_key.pem','ecdsa_key.pem','.env produksi'],'red'),
        ('Data & Log',['logs','static/data','data/task_*'],'green'),
        ('Dokumentasi',['SDD','deployment','manual'],'yellow'),
    ]
    x=45
    for title,det,cls in items:
        b += labeled_box(x,190,220,165,title,det,cls)
        x += 245
    b += [rect(180,500,920,110,'gray'), t(640,535,'Prinsip serah terima','label'), t(640,565,['Source code diserahkan bersama dependency, konfigurasi contoh, dokumentasi, dan checklist uji.','Secret produksi dan private key diserahkan melalui kanal aman, bukan ditempel di laporan publik.'],'small',gap=22)]
    save('manual_source_handover_package.svg',1280,730,'Paket Serah Terima Source Code','Komponen yang harus diserahkan dari pengembang kepada pemilik sistem',b)


def manual_acceptance_checklist():
    b=[]
    cols=[('Fungsi Utama',['generate QR','verify QR','mobile scan']),('Keamanan',['signature','replay','data palsu']),('Operasi',['dashboard','log','export']),('Deployment',['systemd','nginx','ssl']),('Serah Terima',['source','dokumen','backup'])]
    x=55
    for title,items in cols:
        b += labeled_box(x,170,220,250,title,items,'green')
        x += 245
    b += [rect(225,540,830,90,'yellow'), t(640,573,'Kriteria penerimaan','label'), t(640,602,'Seluruh fungsi kritis diuji, dokumen tersedia, source code bisa dijalankan ulang, dan risiko tersisa dicatat.','small')]
    save('manual_acceptance_checklist.svg',1280,720,'Checklist Serah Terima dan Penerimaan Sistem','Poin pemeriksaan akhir untuk user manual, teknis, deployment, dan source code',b)


def main():
    business_crypto(); business_compare(); business_iso(); business_replay()
    storage_arch(); storage_nonce_lock(); storage_logging(); storage_target_schema()
    ui_dashboard(); ui_scanner(); ui_mobile(); ui_flow()
    sdd_architecture(); sdd_generate_flow(); sdd_dfd_l2_generate(); sdd_dfd_l2_verify(); sdd_dash_log(); sdd_replay_classification(); sdd_massal_hp_usb_sqlite()
    deployment_architecture(); deployment_request_flow(); deployment_systemd_runtime(); deployment_tls_renewal(); deployment_checklist()
    manual_documentation_map(); manual_operator_workflow(); manual_admin_audit_workflow(); manual_source_handover_package(); manual_acceptance_checklist()


if __name__ == '__main__':
    main()
