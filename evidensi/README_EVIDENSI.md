# INDEX SCREENSHOT EVIDENSI VISUAL
# Untuk Lampiran Paper Jurnal SINTA 2
# Lokasi: /opt/qrcode/evidensi/

---

## DAFTAR SCREENSHOT

| No | File | Ukuran | Evidence | Lokasi Kode |
|---|---|---|---|---|
| **1** | `app_line_1166.png` | 21.1 KB | RSA-PSS Signing (salt 8-byte) | `app.py` baris 1164-1171 |
| **2** | `app_line_1369.png` | 18.9 KB | RSA-PSS Verification (salt 8-byte) | `app.py` baris 1367-1373 |
| **3** | `app_line_1179.png` | 27.3 KB | DigiSig Envelope (ISO/IEC 20248) | `app.py` baris 1177-1187 |
| **4** | `app_line_1151.png` | 20.5 KB | Nonce + Timestamp Generation | `app.py` baris 1149-1155 |
| **5** | `app_line_1396.png` | 51.6 KB | Dual-Layer Verification | `app.py` baris 1397-1416 |
| **6** | `app_line_428.png` | 29.9 KB | Nonce Checking Function | `app.py` baris 429-443 |
| **7** | `app_line_1207.png` | 36.3 KB | Temporal Decomposition (6 Timers) | `app.py` baris 1205-1219 |
| **8** | `app_line_1227.png` | 36.8 KB | CSV Logging (14 Columns) | `app.py` baris 1225-1238 |
| **9** | `app_line_79.png` | 36.1 KB | Rate Limiting (Redis) | `app.py` baris 80-93 |
| **10** | `realistic_performance_line_12.png` | 30.0 KB | Multi-Scenario Benchmarks | `realistic_performance.py` baris 10-22 |

---

## CARA MENGGUNAKAN DI PAPER

### Opsi 1: Lampiran Appendix
```
Appendix A: Code Evidence
Figure A1. RSA-PSS Signing Implementation (see app_line_1166.png)
Figure A2. Dual-Layer Verification Logic (see app_line_1396.png)
...
```

### Opsi 2: Inline di Section Methods
```
Figure 3. RSA-PSS signing implementation with modified 8-byte salt 
(see app_line_1166.png). The pss.new() function is called with 
salt_bytes=8 parameter instead of the standard 32 bytes.
```

### Opsi 3: Footnote dengan Screenshot Reference
```
The RSA-PSS implementation uses salt_bytes=8 parameter^a.
^a See screenshot evidence: app_line_1166.png
```

---

## DESKRIPSI SETIAP SCREENSHOT

### 1. RSA-PSS Signing (app_line_1166.png)
**Menunjukkan:** Implementasi signing RSA-PSS dengan salt 8-byte
**Highlight:** `signer = pss.new(private_key, salt_bytes=8)`
**Novelty:** Modifikasi salt dari standar 32-byte menjadi 8-byte

### 2. RSA-PSS Verification (app_line_1369.png)
**Menunjukkan:** Verifikasi signature dengan parameter konsisten
**Highlight:** `verifier = pss.new(public_key, salt_bytes=8)`
**Novelty:** Konsistensi parameter salt antara signing dan verification

### 3. DigiSig Envelope (app_line_1179.png)
**Menunjukkan:** Struktur JSON payload sesuai ISO/IEC 20248:2022
**Highlight:** Fields: data, signature, alg, metadata
**Novelty:** Compliance dengan standar internasional

### 4. Nonce + Timestamp Generation (app_line_1151.png)
**Menunjukkan:** Pembuatan nonce 4-byte dan timestamp ISO 8601
**Highlight:** `"nonce": secrets.token_hex(4)` dan `datetime.now(wib).isoformat()`
**Novelty:** Timezone awareness (WIB/UTC+7)

### 5. Dual-Layer Verification (app_line_1396.png)
**Menunjukkan:** Logika verifikasi 2 lapisan (crypto + temporal)
**Highlight:** Nonce check + timestamp validation + signature verification
**Novelty:** Integrasi 3 layer keamanan dalam satu pipeline

### 6. Nonce Checking Function (app_line_428.png)
**Menunjukkan:** Fungsi is_nonce_used() dengan file locking
**Highlight:** File-based nonce tracking dengan atomic locking
**Novelty:** Lightweight replay prevention tanpa database

### 7. Temporal Decomposition (app_line_1207.png)
**Menunjukkan:** 6 timer terpisah untuk analisis performa
**Highlight:** data_timer, sign_timer, qr_timer, save_timer, total_timer
**Novelty:** Granularitas mikrodetik untuk bottleneck analysis

### 8. CSV Logging (app_line_1227.png)
**Menunjukkan:** Logging komprehensif 14 kolom
**Highlight:** 14 kolom dengan waktu mikrodetik
**Novelty:** Detailed performance tracking untuk research

### 9. Rate Limiting (app_line_79.png)
**Menunjukkan:** Rate limiting dengan Redis backend
**Highlight:** Flask-Limiter dengan Redis storage
**Novelty:** Production-ready abuse prevention

### 10. Multi-Scenario Benchmarks (realistic_performance_line_12.png)
**Menunjukkan:** Benchmark parameters dari IEEE/ACM/NIST
**Highlight:** REALISTIC_BENCHMARKS dictionary dengan 5 skenario
**Novelty:** Calibrated testing framework

---

## TOTAL UKURAN FILE

```
10 screenshots = 308.5 KB
Lokasi: /opt/qrcode/evidensi/
Format: PNG dengan syntax highlighting
Background: Dark theme (#1e1e1e)
Font: Consolas/Courier New monospace
```

---

## REKOMENDASI UNTUK PAPER

**Gambar yang WAJIB dilampirkan:**
1. ✅ RSA-PSS Signing (app_line_1166.png) - Buktikan novelty salt 8-byte
2. ✅ Dual-Layer Verification (app_line_1396.png) - Buktikan anti-replay
3. ✅ Temporal Decomposition (app_line_1207.png) - Buktikan 6 timers
4. ✅ Multi-Scenario Benchmarks (realistic_performance_line_12.png) - Buktikan testing framework

**Gambar opsional (jika halaman cukup):**
- DigiSig Envelope (app_line_1179.png) - Compliance evidence
- CSV Logging (app_line_1227.png) - Research rigor evidence

---

*Dibuat: 11 April 2026*
*Script: create_code_screenshots.py*
*Total: 10 screenshots, 308.5 KB*
