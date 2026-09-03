# Daftar Periksa Kepatuhan ISO/IEC 20248:2022 dan NIST SP 800-57

**Sistem:** QR Code Security System RSA-PSS v1.2.0
**Tanggal penilaian:** 3 September 2026
**Kegiatan:** Tabel 16 butir 6 pada Laporan Kemajuan — validasi kepatuhan beserta pendataan pengecualian

---

## 1. Cara Penilaian

Dokumen ini menilai sistem terhadap dua rujukan normatif dan memilah setiap aspek ke
dalam tiga status:

| Status | Arti |
|---|---|
| **Terpenuhi** | Diverifikasi pada kode yang berjalan atau pada hasil pengukuran. |
| **Terpenuhi sebagian** | Mekanisme ada, tetapi tidak seluruh syarat rujukan dipenuhi. |
| **Dikecualikan** | Sengaja tidak dipenuhi; alasan dan konsekuensinya dicatat. |

Kolom **Bukti** menunjuk berkas dan baris kode, keluaran pengukuran, atau berkas
konfigurasi yang dapat ditelusuri ulang. Aspek yang tidak dapat diverifikasi secara
langsung tidak dinyatakan terpenuhi.

Penilaian ini bersifat **penilaian mandiri** oleh tim peneliti dan bukan sertifikasi
pihak ketiga. Rujukan klausul disebut pada tingkat konsep, bukan nomor pasal, karena
penomoran pasal memerlukan salinan resmi standar yang tidak dilampirkan pada laporan.

---

## 2. ISO/IEC 20248:2022 — Struktur Meta Tanda Tangan Digital (DigiSig)

| No | Aspek | Status | Bukti | Catatan |
|---|---|---|---|---|
| 2.1 | Data pembawa (QR Code) berisi struktur yang dapat diverifikasi secara kriptografis | Terpenuhi | `app.py` pembangkitan payload dan `create_qr_with_url()` | Payload ditandatangani sebelum QR dibentuk |
| 2.2 | Tanda tangan digital atas data terstruktur | Terpenuhi | `app.py:3308` `pss.new(private_key, salt_bytes=8)` | RSASSA-PSS dengan SHA-256 |
| 2.3 | Kanonikalisasi data sebelum penandatanganan | Terpenuhi | `json.dumps(data, sort_keys=True)` pada jalur tanda tangan dan verifikasi | Urutan kunci deterministik di kedua sisi |
| 2.4 | Integritas seluruh field yang ditandatangani | Terpenuhi | Pengukuran empiris 50.000 operasi pemalsuan, deteksi 100% | Tujuh subjenis pemalsuan, seluruhnya tertolak |
| 2.5 | Penolakan tanda tangan yang tidak sah | Terpenuhi | Pengukuran empiris 4.000 percobaan pemalsuan tanda tangan, penolakan 100% | Empat jenis: acak, terpotong, tertukar, bit-flip |
| 2.6 | Pengikatan waktu pada struktur data | Terpenuhi | Field `timestamp` ISO 8601 zona WIB (UTC+7) ikut ditandatangani | |
| 2.7 | Perlindungan terhadap pemakaian ulang | Terpenuhi | `nonce_state` pada `logs/security_state.db`; pengukuran replay 100%, FNR 0% | Nonce 8 byte disajikan 16 karakter heksadesimal |
| 2.8 | Toleransi selisih jam penerbit dan verifikator | Terpenuhi | `QR_TIMESTAMP_DRIFT_SECONDS = 300`, `is_timestamp_from_future()` | Ditambahkan 3 September 2026 |
| 2.9 | Penegakan urutan waktu per identitas data | Terpenuhi | Tabel `nonce_timestamp_state`, `check_timestamp_monotonic()` | Ditambahkan 3 September 2026 |
| 2.10 | Masa berlaku struktur data | Terpenuhi | `QR_PAYLOAD_MAX_AGE_SECONDS` 604.800 detik; pengukuran kedaluwarsa 100% dengan kontrol negatif 0% | |
| 2.11 | Validasi struktur payload | Terpenuhi | `validate_payload_structure()` | Field wajib, tipe, dan field asing |
| 2.12 | **Verifikasi luring mandiri tanpa ketergantungan jaringan** | **Dikecualikan** | QR memuat URL pendek `/v/<token>`; payload disimpan di server | Lihat pengecualian E-1 |
| 2.13 | **Ukuran tanda tangan sesuai rekomendasi Lampiran C (≤512 bit)** | **Dikecualikan** | Tanda tangan RSA-PSS 2048 bit menghasilkan 256 byte | Lihat pengecualian E-2 |
| 2.14 | Distribusi kunci publik berbasis X.509/PKI yang dapat dioperasikan lintas pihak | Terpenuhi sebagian | Kunci publik tersedia di sisi server; tidak ada rantai sertifikat | Prasyarat bagi 2.12 |
| 2.15 | Interoperabilitas dengan verifier pihak ketiga | Terpenuhi sebagian | Format payload terdokumentasi pada `openapi.yaml`; verifier independen belum ada | |

**Rekapitulasi:** 11 terpenuhi, 2 terpenuhi sebagian, 2 dikecualikan.

---

## 3. NIST SP 800-57 Part 1 Rev. 5 — Rekomendasi Manajemen Kunci

| No | Aspek | Status | Bukti | Catatan |
|---|---|---|---|---|
| 3.1 | Kekuatan keamanan memadai untuk masa pakai yang direncanakan | Terpenuhi | RSA-2048 setara kekuatan keamanan 112 bit | Dapat diterima NIST hingga 2030 |
| 3.2 | Fungsi hash disetujui | Terpenuhi | SHA-256 pada seluruh jalur tanda tangan dan verifikasi | |
| 3.3 | Skema tanda tangan disetujui | Terpenuhi | RSASSA-PSS sesuai PKCS#1 v2.1 | Salt diadaptasi 32→8 byte |
| 3.4 | Pembangkitan bilangan acak untuk nonce | Terpenuhi | `secrets` pada `generate_qr_nonce()` | Sumber acak kriptografis |
| 3.5 | Pemisahan kunci privat dan publik | Terpenuhi | `rsa_key.pem` dan `ecdsa_key.pem` terpisah dari kode aplikasi | |
| 3.6 | Kendali akses berkas kunci | Terpenuhi | Mode 0640 pemilik `root`, grup `www-data` | Terverifikasi pada halaman Security Profile |
| 3.7 | Kunci privat tidak pernah meninggalkan server | Terpenuhi | Tidak ada rute yang menyajikan berkas kunci privat | Diperiksa atas 97 rute pada `openapi.yaml` |
| 3.8 | **Penyimpanan kunci privat pada modul kriptografis bersertifikat** | **Dikecualikan** | Kunci privat berupa berkas pada sistem berkas server | Lihat pengecualian E-3 |
| 3.9 | Prosedur rotasi kunci terdokumentasi | Terpenuhi sebagian | Belum ada prosedur rotasi tertulis maupun otomatis | Agenda lanjutan |
| 3.10 | Masa berlaku kunci ditetapkan | Terpenuhi sebagian | Masa berlaku payload ditetapkan; masa berlaku kunci belum | |
| 3.11 | Pemusnahan kunci yang tidak terpakai | Belum dinilai | Tidak ada kunci yang dipensiunkan sampai saat ini | Menjadi relevan setelah rotasi diterapkan |
| 3.12 | Algoritma pembanding tidak melemahkan algoritma utama | Terpenuhi | Payload `alg=RSA` hanya dinilai kunci RSA sejak 20 Agustus 2026 | Menutup pengelakan lintas algoritma |

**Rekapitulasi:** 8 terpenuhi, 2 terpenuhi sebagian, 1 dikecualikan, 1 belum dinilai.

---

## 4. Daftar Pengecualian

### E-1 — Verifikasi luring mandiri tidak tersedia

**Rujukan:** ISO/IEC 20248:2022, konsep DigiSig verifikasi mandiri.

**Keadaan.** QR Code memuat URL pendek `/v/<token>`, bukan payload bertanda tangan
secara utuh. Verifikasi karena itu menuntut ketersediaan server dan payload yang masih
berada dalam masa retensi.

**Alasan.** Memuat payload penuh ke dalam QR akan menaikkan versi QR jauh di atas
rentang yang menjadi tujuan efisiensi penelitian ini. Tanda tangan RSA-PSS 2048 bit
berukuran 256 byte, dan bersama data identitas akan mendorong QR melewati versi 10
sehingga keterbacaan pada media cetak menurun.

**Konsekuensi.** Klaim kemampuan verifikasi luring pada rencana awal tidak dapat
dipertahankan; keabsahan QR bergantung pada ketersediaan layanan.

**Prasyarat pemenuhan.** QR berpayload penuh, distribusi kunci publik berbasis
X.509/PKI, dan aplikasi verifier terpisah. Ketiganya tercatat sebagai agenda
pengembangan lanjutan pada Tabel 12 laporan kemajuan.

### E-2 — Ukuran tanda tangan melampaui rekomendasi Lampiran C

**Rujukan:** ISO/IEC 20248:2022 Lampiran C, rekomendasi ukuran tanda tangan ≤512 bit.

**Keadaan.** RSA-PSS 2048 bit menghasilkan tanda tangan 256 byte atau 2.048 bit,
empat kali rekomendasi tersebut.

**Alasan.** Keputusan desain yang disengaja dengan memprioritaskan kekuatan keamanan
112 bit. Rekomendasi Lampiran C dapat dipenuhi dengan ECDSA P-256 yang menghasilkan
tanda tangan 64 byte, dan modul pembanding pada prototipe membuktikannya menurunkan
QR ke versi 3–4. Namun RSA-PSS adalah objek penelitian ini, sehingga penggantian
algoritma akan meniadakan pertanyaan penelitiannya.

**Konsekuensi.** Kepatuhan penuh terhadap Lampiran C tidak dapat diklaim. Keterbatasan
ini dinyatakan eksplisit pada kedua naskah artikel.

### E-3 — Kunci privat tidak disimpan pada modul kriptografis bersertifikat

**Rujukan:** NIST SP 800-57 Part 1 Rev. 5, perlindungan kunci privat.

**Keadaan.** Kunci privat berupa berkas PEM pada sistem berkas server dengan mode 0640
milik `root` grup `www-data`.

**Alasan.** Pengadaan Hardware Security Module bersertifikasi FIPS 140-3 berada di luar
cakupan anggaran penelitian.

**Konsekuensi.** Perlindungan kunci bergantung pada kendali akses sistem operasi.
Kompromi tingkat root berarti kompromi kunci.

**Prasyarat pemenuhan.** Evaluasi dan pengadaan HSM bersertifikasi, tercatat sebagai
agenda lanjutan pada Tabel 12 laporan kemajuan.

---

## 5. Ringkasan

| Rujukan | Terpenuhi | Sebagian | Dikecualikan | Belum dinilai | Total |
|---|---|---|---|---|---|
| ISO/IEC 20248:2022 | 11 | 2 | 2 | 0 | 15 |
| NIST SP 800-57 | 8 | 2 | 1 | 1 | 12 |
| **Jumlah** | **19** | **4** | **3** | **1** | **27** |

Sistem memenuhi 19 dari 27 aspek yang dinilai. Tiga pengecualian seluruhnya bersifat
struktural: dua berasal dari pilihan algoritma yang menjadi objek penelitian, satu dari
batas anggaran. Tidak ada pengecualian yang berasal dari cacat implementasi.

Klaim yang dapat dipertahankan adalah **keselarasan dengan komponen inti** ISO/IEC
20248:2022 disertai pengecualian terdokumentasi, bukan kepatuhan penuh.

---

## 6. Bukti Pengukuran Pendukung

Pengukuran empiris 3 September 2026 melalui `data-penelitian/harness_empiris.py`,
63.500 operasi pada jalur verifikasi asli:

| Metrik | Hasil | Target proposal |
|---|---|---|
| Akurasi deteksi pemalsuan data (50.000 operasi) | 100% | 79,2% |
| Deteksi kategori kritis | 100% | — |
| Laju deteksi replay (4.500 verifikasi) | 100% | 95,8% |
| Laju negatif palsu replay | 0,0000% | ≤ 0,1% |
| Laju positif palsu replay | 0,0000% | — |
| Waktu deteksi rata-rata | 0,979 ms | ≤ 20,0 ms |
| Deteksi kedaluwarsa (5.000 payload) | 100% | — |
| Positif palsu kontrol negatif kedaluwarsa | 0,00% | — |
| Laju penolakan pemalsuan tanda tangan (4.000 percobaan) | 100% | 97,0% |
