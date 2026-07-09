---
title: "BUKU PANDUAN PENGGUNA"
subtitle: "QR Code Security System | Digital Signature RSA-PSS 2048-bit dan ECDSA P-256"
author: "Panduan Operasional untuk Operator, Petugas Verifikasi, Auditor, dan Penguji"
date: "Edisi 1.0 | Juni 2026"
lang: id-ID
---

**Dokumen terkendali.** Gunakan versi terbaru yang disahkan oleh pengelola sistem.

**Klasifikasi:** Internal  
**Format cetak:** A4, bolak-balik, margin cermin  
**Sistem:** QR Code Security System  
**Versi manual:** 1.0  
**Tanggal penerbitan:** 19 Juni 2026

# Pendahuluan

## Tujuan Buku

Buku ini menjelaskan cara menggunakan QR Code Security System dari awal sampai selesai. Panduan mencakup login, navigasi, pembuatan QR tunggal dan massal, verifikasi melalui file/kamera HP/scanner USB, pemantauan job, dashboard, log, audit, profil keamanan, benchmark, serta modul pengujian.

Manual ditulis berdasarkan antarmuka dan source code aktif di `/opt/qrcode` pada 19 Juni 2026. Nama tombol dapat sedikit berbeda bila aplikasi diperbarui, tetapi alur utamanya tetap sama.

## Sasaran Pengguna

| Peran operasional | Aktivitas utama |
|---|---|
| Operator | Membuat QR, mengunduh hasil, memantau job massal. |
| Petugas verifikasi | Memindai QR, membaca status, menangani penolakan. |
| Petugas lapangan | Memindai QR melalui kamera HP. |
| Auditor/pengawas | Memeriksa dashboard, log generate, log verifikasi, dan audit log. |
| Penguji keamanan | Menjalankan modifikasi QR, benchmark, dan skenario testing dengan izin. |
| Administrator teknis | Mengelola akses, konfigurasi, retensi payload, backup, dan pemulihan. |

> **Catatan hak akses:** aplikasi menggunakan satu password akses yang dikonfigurasi melalui `AUTH_PASSWORD`. Peran pada tabel adalah pembagian tugas operasional, bukan akun atau role terpisah di dalam aplikasi. Jangan membagikan password kepada pihak yang tidak berwenang.

## Konvensi dalam Buku

| Penanda | Arti |
|---|---|
| **Tombol/Menu** | Elemen yang diklik pada layar. |
| `teks` | Nilai, nama field, route, nama file, atau alamat teknis. |
| **PENTING** | Informasi yang mencegah kesalahan operasional. |
| **PERINGATAN** | Tindakan yang dapat mengubah data, menghasilkan QR palsu, atau membebani server. |

## Peta Alur Pengguna

![Gambar 1. Alur kerja operator dari login sampai pemeriksaan log.](Gambar-Asli/manual_operator_workflow.png){width=15.5cm}

Alur normal adalah: login, pilih fitur di Home, buat atau verifikasi QR, baca hasil, lalu pastikan aktivitas tercatat pada log. Pengguna tidak perlu membuka folder server untuk menjalankan alur harian.

# Mengenal Sistem

## Fungsi Utama

QR Code Security System membuat QR yang dilindungi tanda tangan digital. Payload berisi data pengguna, algoritma, hash, timestamp, nonce, dan signature. Sistem menyediakan dua algoritma:

- **RSA-PSS 2048-bit**, pilihan awal pada form generator.
- **ECDSA P-256**, alternatif dengan signature lebih ringkas.

Saat QR diverifikasi, sistem memeriksa keterbacaan gambar, struktur payload, signature, integritas data, kesesuaian dengan data asal, umur payload, serta penggunaan nonce. Hasilnya bukan sekadar “QR terbaca”, melainkan klasifikasi keamanan.

## Status Verifikasi dan Keputusan

| Status pada layar | Makna | Keputusan operator |
|---|---|---|
| **Valid dan Authentik** | Signature valid, data sesuai, dan belum terindikasi digunakan ulang. | Terima sesuai SOP bisnis. |
| **Replay Attack** | QR asli pernah diverifikasi/digunakan sebelumnya. | Tolak penggunaan ulang; catat dan eskalasi. |
| **Data Telah Dimodifikasi** | Data berbeda dari rekaman asal. | Tolak; simpan bukti bila perlu investigasi. |
| **Data Palsu** | Signature/payload tidak sah atau tidak berasal dari sistem. | Tolak. |
| **Signature Invalid** | Verifikasi tanda tangan gagal. | Tolak; jangan menganggap QR valid hanya karena gambar terbaca. |
| **Tidak Ditemukan** | Data asal tidak ditemukan. | Periksa sumber QR dan waktu penerbitan. |
| **QR tidak terbaca/Error** | Decode gambar atau proses teknis gagal. | Ulangi dengan gambar lebih jelas; eskalasi bila berulang. |

> **PENTING:** status **Replay Attack** dapat muncul pada scan kedua QR yang sama. Sistem memang menggunakan nonce untuk mendeteksi pemakaian ulang.

## Persyaratan Penggunaan

- Browser modern: Chrome, Edge, Firefox, atau Safari versi yang masih didukung.
- Koneksi ke alamat aplikasi yang diberikan administrator.
- Password akses yang sah.
- Untuk kamera HP: izin kamera dan koneksi HTTPS.
- Untuk scanner USB: perangkat dalam mode *keyboard wedge* dan dapat mengirim Enter.
- File upload tunggal: PNG, JPG/JPEG, atau GIF, maksimal 10 MB per file.
- Hindari dua operator menggunakan QR yang sama pada saat bersamaan kecuali sedang menguji replay.

# Akses dan Login

## Membuka Aplikasi

1. Buka browser.
2. Masukkan alamat sistem, misalnya `https://rsa-pss.com/login` atau URL internal yang diberikan administrator.
3. Pastikan domain dan indikator HTTPS benar sebelum memasukkan password.
4. Jangan melanjutkan jika browser menampilkan peringatan sertifikat yang tidak dikenal; hubungi administrator.

![Gambar 2. Halaman login QR Code Security System.](manual-assets/00_login.jpg){width=15.5cm}

## Login

1. Klik field **Password Akses**.
2. Masukkan password tanpa membagikannya kepada orang lain.
3. Klik **Login ke Sistem**.
4. Setelah berhasil, sistem membuka halaman Home.

Login gagal dapat disebabkan password salah atau terlalu banyak percobaan. Endpoint login membatasi percobaan POST sebanyak 5 kali per menit. Tunggu sedikit sebelum mencoba kembali, lalu pastikan `Caps Lock` dan tata letak keyboard benar.

## Sesi dan Logout

Sesi login bersifat permanen selama periode yang dikonfigurasi aplikasi dan saat ini dibatasi sekitar 2 jam. Bila sesi berakhir, sistem mengarahkan pengguna ke login.

Untuk keluar:

1. Klik **Logout** di kanan atas Home.
2. Pastikan halaman login tampil kembali.
3. Pada komputer bersama, tutup seluruh jendela browser.

# Home dan Navigasi

## Struktur Halaman Home

Home adalah pusat navigasi. Bagian atas menampilkan ringkasan kemampuan sistem, bagian tengah menampilkan fitur utama, dan bagian bawah menampilkan akses cepat serta konfigurasi aktif.

![Gambar 3a. Bagian atas Home: ringkasan keamanan dan akses fitur utama.](manual-assets/01_home_index_01.jpg){width=15.5cm}

![Gambar 3b. Bagian tengah Home: scanner USB, kamera HP, dan akses cepat.](manual-assets/01_home_index_02.jpg){width=15.5cm}

![Gambar 3c. Bagian bawah Home: informasi sistem dan batas upload.](manual-assets/01_home_index_03.jpg){width=15.5cm}

## Daftar Menu

| Menu | Kegunaan |
|---|---|
| **Buka QR Generator** | Generate tunggal atau massal dari CSV. |
| **Buka Verifikasi** | Upload dan verifikasi QR tunggal/massal. |
| **Scanner Langsung** | Input dari scanner USB/perangkat keyboard. |
| **Buka Mobile Scan** | Kamera HP atau input URL/data manual. |
| **Dashboard** | Statistik operasional dan performa. |
| **Log Generate** | Riwayat pembuatan QR dan preview. |
| **Log Verifikasi** | Riwayat keputusan verifikasi dan detail performa. |
| **CSV Generator** | Membuat dataset CSV untuk proses massal/testing. |
| **Modifikasi QR** | Membuat QR tidak sah untuk simulasi terkontrol. |
| **Testing System** | Menjalankan skenario pengujian otomatis. |
| **Job Massal** | Memantau tugas generate/verifikasi di background. |
| **Audit Log** | Jejak login, download, cleanup, dan aksi penting. |
| **Benchmark** | Membandingkan RSA dan ECDSA. |

Halaman **Status Teknis Keamanan** tersedia melalui route `/security_profile`. Menu tersebut ditujukan untuk administrator/auditor.

# Membuat QR Tunggal

## Membuka Generator

Dari Home klik **Buka QR Generator**. Tab **Generate Tunggal** aktif secara default.

![Gambar 4. Form Generate Tunggal.](manual-assets/03_qr_generator.jpg){width=15.5cm}

## Mengisi Data

1. Isi **Nama Lengkap**. Gunakan nama sebagaimana tercatat pada data sumber.
2. Isi **User ID** dengan ID unik. Hindari spasi di awal/akhir.
3. Pilih algoritma:
   - **RSA 2048** untuk pilihan utama dan kompatibilitas alur default.
   - **ECDSA P-256** bila organisasi menetapkannya atau membutuhkan signature lebih ringkas.
4. Periksa kembali nama dan ID.
5. Klik **Generate QR Code** satu kali.

## Hasil Generate

Sistem membuat dan menyimpan:

- file QR PNG;
- data asli JSON;
- URL verifikasi pendek `/v/<token>`;
- timestamp, nonce, hash, dan signature;
- metrik waktu generate;
- baris aktivitas pada log generate.

Pada halaman hasil, periksa nama, ID, algoritma, ukuran/dimensi QR, serta tombol download. Uji pindai hanya bila memang akan digunakan; scan pertama dapat mengubah status nonce sehingga scan berikutnya terklasifikasi replay.

## Aturan Data yang Baik

- Gunakan User ID yang stabil dan unik.
- Jangan memasukkan password, nomor kartu, private key, atau rahasia lain ke field nama/ID.
- Jangan membuat ulang QR hanya untuk mengganti nama file. Pembuatan ulang menghasilkan nonce baru dan identitas QR baru.
- Bila terdapat salah ketik, buat QR baru dan tandai QR lama tidak digunakan.

# Membuat QR Massal dari CSV

## Menyiapkan CSV

File minimal harus memiliki header `nama,id`:

```csv
nama,id
Andi Saputra,USR0001
Siti Rahma,USR0002
```

Gunakan UTF-8, pemisah koma, satu pengguna per baris, dan ID unik. Periksa agar tidak ada baris kosong atau formula spreadsheet yang tidak dibutuhkan.

## Menggunakan CSV Generator

Halaman `/generate_csv` dapat membuat dataset uji tanpa aplikasi spreadsheet.

![Gambar 5. CSV Generator: Simple, Advanced, dan Massive Mode.](manual-assets/04_generate_csv.jpg){width=15.5cm}

### Simple Mode

1. Isi **Jumlah Data** (1 sampai 1.000.000).
2. Pilih **Random Names**, **Sequential Users**, atau **Event Participants**.
3. Klik **Preview Data** untuk melihat 10 baris pertama.
4. Klik **Generate & Download CSV**.

### Advanced Mode

1. Isi jumlah data, **Prefix Nama**, **Prefix ID**, dan **Start Number**.
2. Pilih kolom tambahan: email, phone, dan/atau department.
3. Klik **Generate Smart CSV**.

### Massive Mode

Mode ini ditujukan untuk pengujian ekstrem. Jumlah 10.000 sampai 100.000 lazim dipakai untuk uji performa; batas form mencapai 1.000.000 data. Jalankan hanya dengan persetujuan administrator karena file besar memakai CPU, memori, storage, dan waktu.

## Upload dan Generate Massal

1. Buka QR Generator dan pilih tab **Generate Massal**.
2. Pilih file CSV yang telah diperiksa.
3. Pilih algoritma tanda tangan.
4. Klik tombol generate massal.
5. Tunggu halaman progress. Jangan menutup browser bila halaman menyatakan proses masih dimulai.
6. Buka hasil setelah status selesai.
7. Unduh file satu per satu atau arsip ZIP melalui tombol yang tersedia.

## Membaca Progress dan Hasil

Progress menampilkan persentase, jumlah selesai, estimasi/kecepatan, dan status task. Hasil massal dapat memuat total sukses/gagal, waktu rata-rata, dimensi QR, serta link download.

Jika task dihentikan, hasil yang sudah selesai dapat tetap ada, tetapi jangan menganggap batch lengkap. Cocokkan jumlah output dengan jumlah baris input sebelum mendistribusikan QR.

# Verifikasi File QR

## Workspace Verifikasi

Dari Home klik **Buka Verifikasi**. Workspace memiliki tab **Verifikasi Tunggal** dan **Verifikasi Massal**.

![Gambar 6. Workspace upload verifikasi QR.](manual-assets/05_scanner_workspace.jpg){width=15.5cm}

## Verifikasi Tunggal

1. Pilih tab **Verifikasi Tunggal**.
2. Drag & drop gambar QR ke area upload, atau klik **Pilih File**.
3. Pastikan hanya satu file yang terpilih.
4. Klik **Verifikasi QR Code**.
5. Tunggu halaman hasil.
6. Baca status utama, lalu cocokkan nama, ID, algoritma, dan detail bila tersedia.
7. Terapkan keputusan pada tabel status di Bab “Mengenal Sistem”.

### Tips agar QR Terbaca

- Gunakan gambar fokus dengan kontras tinggi.
- Sisakan *quiet zone* putih di sekeliling QR.
- Hindari crop yang memotong modul QR.
- Jangan unggah screenshot yang terlalu kecil atau terkena pantulan cahaya.
- Bila gagal, gunakan file QR asli hasil download.

## Verifikasi Massal

1. Pilih tab **Verifikasi Massal**.
2. Pilih beberapa file PNG/JPG/JPEG/GIF.
3. Periksa daftar/jumlah file.
4. Mulai verifikasi massal.
5. Untuk batch besar, sistem membuat job async dan membuka halaman progress.
6. Tunggu status selesai atau pantau dari **Job Massal**.
7. Buka hasil dan ekspor laporan jika diperlukan.

![Gambar 7. Halaman progress verifikasi massal asynchronous.](manual-assets/16_verify_massal_async.jpg){width=15.5cm}

## Batas Upload Massal

Konfigurasi saat manual diterbitkan:

| Parameter | Nilai | Implikasi |
|---|---:|---|
| Maksimum per file | 10 MB | File lebih besar ditolak. |
| Maksimum request | 500 MB | Total semua file dan overhead multipart tidak boleh melampaui batas. |
| Maksimum multipart part | 20.000 | Satu file biasanya satu part. |
| Ekstensi | PNG, JPG, JPEG, GIF | File lain tidak diproses sebagai gambar QR. |

Batas efektif adalah nilai terkecil antara 20.000 file dan `500 MB / rata-rata ukuran file`. Untuk penggunaan stabil, pecah batch besar menjadi beberapa job dan beri nama folder sumber dengan jelas.

## Membaca Laporan Massal

Periksa total file, sukses decode, valid, replay, data palsu/error, success rate, serta waktu load/decode/verify/database. Untuk audit, jangan hanya menyimpan persentase; ekspor detail per file agar temuan dapat ditelusuri.

# Verifikasi Kamera HP

## Persiapan

1. Gunakan Chrome/Safari/Edge modern.
2. Pastikan HP dapat mengakses domain aplikasi.
3. Gunakan HTTPS; browser umumnya menolak kamera pada HTTP non-localhost.
4. Bersihkan lensa kamera dan atur pencahayaan.

## Memindai

1. Buka `/mobile_scan` atau klik **Buka Mobile Scan**.
2. Izinkan kamera ketika browser meminta izin.
3. Arahkan QR ke area kamera dan jaga perangkat tetap stabil.
4. Setelah terbaca, sistem menyelesaikan target scan dan membuka halaman verifikasi.
5. Baca status. Jangan kembali lalu memindai QR yang sama kecuali ingin menguji replay.

![Gambar 8. Scanner HP dan input manual.](manual-assets/06_scanner_hp_mobile.jpg){width=15.5cm}

## Input Manual

Bila kamera tidak tersedia:

1. Salin URL QR atau data QR lengkap.
2. Tempel pada field **Input manual**.
3. Jalankan tombol buka/verifikasi.
4. Pastikan URL mengarah ke domain sistem, terutama untuk QR dengan bentuk `/v/<token>`.

## Masalah Kamera

| Gejala | Penanganan |
|---|---|
| Izin kamera ditolak | Buka pengaturan situs browser, izinkan Camera, lalu muat ulang. |
| Layar kamera hitam | Tutup aplikasi lain yang memakai kamera; ganti kamera depan/belakang. |
| QR terbaca tetapi URL gagal | Pastikan koneksi dan `BASE_URL` saat QR dibuat menggunakan domain yang dapat diakses HP. |
| Scan berulang | Jauhkan QR setelah pembacaan pertama dan tunggu hasil tampil. |

# Verifikasi Scanner USB

## Cara Kerja

Scanner USB diperlakukan seperti keyboard. Perangkat menulis isi QR ke input dan biasanya mengirim Enter untuk memulai verifikasi.

![Gambar 9. Halaman Scanner Langsung/USB.](manual-assets/07_scanner_usb_verify_direct.jpg){width=15.5cm}

## Prosedur

1. Sambungkan scanner USB dan tunggu sistem operasi mengenalinya.
2. Buka `/verify_direct`.
3. Klik field **Scan QR Code di sini** sampai kursor aktif.
4. Pindai QR satu kali.
5. Jika scanner tidak mengirim Enter, klik tombol verifikasi pada halaman.
6. Baca hasil dan pastikan counter berhasil/gagal berubah dengan benar.
7. Pastikan input kembali kosong/fokus sebelum QR berikutnya.

## Uji Perangkat Sebelum Operasional

Buka editor teks, pindai QR uji, lalu pastikan data muncul utuh dan diakhiri Enter. Jika karakter terpotong, samakan layout keyboard perangkat dengan konfigurasi scanner atau turunkan kecepatan output scanner.

# Modifikasi QR untuk Pengujian

> **PERINGATAN:** fitur ini sengaja membuat QR palsu/tidak valid. Gunakan hanya pada lingkungan dan data uji yang berizin. Jangan mendistribusikan output sebagai QR resmi.

## Jenis Simulasi

- **Modifikasi Nama/ID:** mengubah field data.
- **Replay Attack:** menggunakan ulang payload/nonce.
- **Ubah Timestamp:** menguji kebijakan umur payload.
- **Corrupt Signature:** merusak signature untuk memastikan penolakan.
- **Batch Modifikasi:** menerapkan skenario melalui CSV.

![Gambar 10a. Halaman Modifikasi QR bagian upload dan batch.](manual-assets/08_modify_qr_01.jpg){width=15.5cm}

![Gambar 10b. Penjelasan jenis modifikasi pada halaman.](manual-assets/08_modify_qr_02.jpg){width=15.5cm}

## Prosedur Aman

1. Gunakan QR uji, bukan QR produksi aktif.
2. Catat tujuan dan penanggung jawab pengujian.
3. Upload QR asli melalui **Pilih QR Code yang valid**.
4. Pilih modifikasi dan isi nilai uji.
5. Terapkan modifikasi.
6. Verifikasi QR hasil dan pastikan sistem menolaknya dengan klasifikasi yang diharapkan.
7. Buka **Log Modifikasi** untuk menyimpan bukti.
8. Hapus output uji setelah masa penyimpanan berakhir sesuai SOP.

![Gambar 11a. Log modifikasi individual.](manual-assets/09_modification_logs_01.jpg){width=15.5cm}

![Gambar 11b. Ringkasan log modifikasi/batch.](manual-assets/09_modification_logs_02.jpg){width=15.5cm}

# Job Massal

Halaman `/jobs` menyatukan status task generate dan verifikasi massal.

![Gambar 12. Daftar Job Massal.](manual-assets/10_jobs_massal.jpg){width=15.5cm}

## Arti Status

| Status | Arti | Tindakan |
|---|---|---|
| Menunggu | Task telah dicatat tetapi belum aktif. | Tunggu dan muat ulang seperlunya. |
| Berjalan | Proses background aktif. | Jangan memulai duplikat tanpa alasan. |
| Selesai | Task berakhir normal. | Buka hasil dan cocokkan total. |
| Dihentikan | Pengguna/sistem menghentikan task. | Periksa hasil parsial dan alasan penghentian. |
| Error | Task gagal. | Baca pesan error, cek input, lalu eskalasi bila perlu. |

Gunakan ID task saat melaporkan masalah. ID memudahkan administrator menemukan metadata dan hasil task yang tepat.

# Dashboard dan Statistik

## Membuka Dashboard

Klik **Dashboard** pada Home atau buka `/dashboard`. Tunggu proses kalkulasi selesai bila data log besar.

![Gambar 13a. Dashboard: KPI generate dan verifikasi.](manual-assets/02_dashboard_01.jpg){width=15.5cm}

![Gambar 13b. Dashboard: statistik waktu dan distribusi data.](manual-assets/02_dashboard_02.jpg){width=15.5cm}

![Gambar 13c. Dashboard: analisis lanjutan dan metodologi.](manual-assets/02_dashboard_03.jpg){width=15.5cm}

## Interpretasi Metrik

| Metrik | Cara membaca |
|---|---|
| Total QR Generated | Jumlah catatan generate yang dihitung dari sumber data dashboard. |
| Total Verifikasi | Jumlah pemeriksaan yang tercatat. Satu QR dapat muncul lebih dari sekali. |
| Valid Rate | Proporsi hasil valid dari data yang dihitung, bukan jumlah QR unik. |
| Median | Waktu tipikal; lebih tahan terhadap pencilan. |
| P95 | 95% operasi berada pada/di bawah nilai ini; gunakan untuk menilai ekor latensi. |
| Ops/sec | Estimasi dari waktu operasi bila dijelaskan demikian; bukan otomatis hasil load test paralel. |
| Dimensi/ukuran QR | Membantu menilai dampak algoritma dan payload terhadap file. |

## Tindakan Administrator

Tombol reset/recalculate mengubah statistik atau state terkait. Sebelum menggunakannya:

1. Ekspor log yang diperlukan.
2. Pastikan tidak ada operasi massal aktif.
3. Catat alasan dan waktu tindakan.
4. Lakukan hanya dengan wewenang administrator.

# Log Generate, Verifikasi, dan Audit

## Log Generate

Log generate memuat waktu, nama, ID, sumber tunggal/massal, algoritma, file, metrik, dan preview QR bila file tersedia.

![Gambar 14a. Log Generate bagian filter dan tabel awal.](manual-assets/13_log_generate_01.jpg){width=15.5cm}

![Gambar 14b. Log Generate bagian tabel lanjutan/preview.](manual-assets/13_log_generate_02.jpg){width=15.5cm}

Gunakan filter tanggal, sumber, dan jumlah data per halaman. Ekspor Excel untuk audit. Jangan menghapus log sebelum backup dan persetujuan pemilik data.

## Log Verifikasi

Log verifikasi mendukung filter tanggal, status, sumber, serta pencarian nama/ID/file. Sumber dapat berupa tunggal, massal, massal async, direct/scanner, atau kamera HP.

![Gambar 15a. Log Verifikasi: filter dan tabel.](manual-assets/14_log_verifikasi_01.jpg){width=15.5cm}

![Gambar 15b. Log Verifikasi: lanjutan detail hasil.](manual-assets/14_log_verifikasi_02.jpg){width=15.5cm}

![Gambar 15c. Log Verifikasi: distribusi status dan performa.](manual-assets/14_log_verifikasi_03.jpg){width=15.5cm}

Untuk investigasi, catat waktu, sumber, status, nama/ID, nama file, detail perubahan, dan timing. Jangan menyimpulkan serangan hanya dari satu metrik performa; gunakan status kriptografis dan log terkait.

## Audit Log

Audit log mencatat waktu, aksi, actor, IP, user agent, dan detail. Data terbaru ditampilkan lebih dahulu dan dapat diunduh sebagai CSV.

![Gambar 16a. Audit Log bagian atas.](manual-assets/12_audit_log_01.jpg){width=15.5cm}

![Gambar 16b. Audit Log bagian bawah dan pagination.](manual-assets/12_audit_log_02.jpg){width=15.5cm}

Audit log berguna untuk menelusuri login berhasil/gagal, logout, download, cleanup payload, dan aksi administratif. Akses log harus dibatasi karena dapat memuat alamat IP dan user agent.

# Profil Keamanan

Halaman `/security_profile` adalah panel audit konfigurasi aktif.

![Gambar 17. Status Teknis Keamanan.](manual-assets/11_security_profile.jpg){width=15.5cm}

## Bagian yang Diperiksa

- Algoritma, ukuran kunci, hash, salt RSA-PSS, nonce, timestamp, dan kebijakan URL QR.
- Lokasi, ukuran, waktu perubahan, dan permission file kunci.
- Jumlah nonce unik dan total penggunaan nonce.
- Jumlah payload short URL dan masa retensi.
- Rate limit aktif.

Badge **Permission ketat** berarti mode file memenuhi pemeriksaan aplikasi. Badge **Perlu diperketat** harus ditindaklanjuti administrator; jangan mengubah permission tanpa memahami user service yang menjalankan aplikasi.

## Cleanup Payload Lama

Tombol **Cleanup Payload Lama** menghapus payload short URL yang melewati masa retensi (default 30 hari). Sebelum klik:

1. Pastikan kebijakan retensi telah disetujui.
2. Pastikan tidak ada QR aktif yang masih bergantung pada payload lama.
3. Siapkan backup bila kebijakan organisasi mensyaratkannya.
4. Konfirmasi aksi dan periksa audit log setelah selesai.

# Benchmark RSA dan ECDSA

Halaman `/benchmark` mengukur beberapa iterasi signing/verifikasi dan membandingkan waktu, stabilitas, ukuran signature, penggunaan memori, serta dampak pada QR.

![Gambar 18. Halaman benchmark algoritma.](manual-assets/15_benchmark.jpg){width=15.5cm}

## Menjalankan Benchmark

1. Pastikan server tidak sedang menjalankan batch besar.
2. Buka **Benchmark**.
3. Isi **Jumlah Iterasi** dengan nilai kecil untuk uji awal.
4. Jalankan benchmark dan tunggu selesai.
5. Bandingkan RSA dan ECDSA pada metrik yang sama.
6. Catat spesifikasi server, waktu, dan kondisi beban saat menyimpan hasil.

Hasil benchmark adalah karakteristik lingkungan saat pengujian, bukan jaminan performa semua perangkat. Lakukan beberapa run dan gunakan median/P95 bila tersedia.

# Testing System

> **PERINGATAN:** modul testing dapat menjalankan puluhan ribu operasi, membuat file/log, menembak endpoint nyata, dan meningkatkan beban server. Jalankan pada jadwal terkontrol dengan izin administrator.

## Dashboard Testing

![Gambar 19a. Dashboard Testing: skenario normal sampai stress test.](manual-assets/17_testing_dashboard_01.jpg){width=15.5cm}

![Gambar 19b. Dashboard Testing: calibration dan history.](manual-assets/17_testing_dashboard_02.jpg){width=15.5cm}

![Gambar 19c. Dashboard Testing: recent sessions dan server metrics.](manual-assets/17_testing_dashboard_03.jpg){width=15.5cm}

Dashboard menyediakan Normal Operations, Replay Attack, Data Tampering, Signature Forgery, Simulated Stress Test, Real HTTP Stress Test, Performance Calibration, Test History, Active Tests, serta Comprehensive Test.

## Prosedur Umum Pengujian

1. Pilih satu skenario.
2. Beri **Test Name** yang menjelaskan tujuan/tanggal.
3. Isi parameter dan cek batas minimum/maksimum.
4. Mulai dari volume rendah.
5. Klik mulai, lalu pantau progress dan server metrics.
6. Jangan menjalankan skenario serupa ganda kecuali rencana uji memerlukannya.
7. Hentikan test bila error meningkat, disk hampir penuh, atau layanan melambat.
8. Buka results dan unduh report.
9. Catat versi aplikasi dan konfigurasi agar hasil dapat direproduksi.

## Normal Operations

Mengukur signing dan verification dalam jumlah besar. Default 10.000 signing dan 10.000 verification; batas form 100 sampai 50.000 untuk masing-masing.

![Gambar 20. Konfigurasi Normal Operations.](manual-assets/18_testing_config_normal_operations.jpg){width=15.5cm}

## Replay Attack

Membuat sampel lalu mengulang verifikasi. Default 1.500 sampel dan 20 pengulangan; gunakan hasil untuk menilai konsistensi deteksi replay.

![Gambar 21. Konfigurasi Replay Attack.](manual-assets/19_testing_config_replay_attack.jpg){width=15.5cm}

## Data Tampering

Menguji perubahan, penambahan, dan penghapusan field. Default 50.000 operasi. Harapan utamanya adalah data yang berubah ditolak/diklasifikasikan dengan benar.

![Gambar 22. Konfigurasi Data Tampering.](manual-assets/20_testing_config_data_tampering.jpg){width=15.5cm}

## Signature Forgery

Menguji random, swapped, dan truncated signature dengan fokus RSA-PSS. Keberhasilan pengujian berarti signature palsu ditolak, bukan diterima.

![Gambar 23. Konfigurasi Signature Forgery.](manual-assets/21_testing_config_signature_forgery.jpg){width=15.5cm}

## Simulated Stress Test

Simulasi menghasilkan estimasi berdasarkan model/kalibrasi dan tidak identik dengan request HTTP nyata. Isi jumlah operasi dan level concurrent users yang dipisahkan koma.

![Gambar 24. Konfigurasi Simulated Stress Test.](manual-assets/22_testing_config_stress_test.jpg){width=15.5cm}

## Real HTTP Stress Test

Mode ini benar-benar mengirim request ke aplikasi. Target **Generate + Verify** membuat QR, menulis log, mengambil URL `/v/<token>`, dan memverifikasinya. Mulai dari default rendah: 20 request per level dan concurrent users `2,5,10`.

![Gambar 25. Konfigurasi Real HTTP Stress Test.](manual-assets/23_testing_config_real_http_stress_test.jpg){width=15.5cm}

Pilih Base URL publik untuk menguji Nginx/HTTPS, atau localhost untuk jalur aplikasi lokal. Jangan mengarahkan test ke server pihak lain. Perhatikan rate limit, timeout, pertumbuhan log, file QR, dan replay state.

## Test History

History menampilkan total, completed, running, failed, serta daftar session. Gunakan **View Results**, **Download Report**, atau delete sesuai kebijakan retensi.

![Gambar 26a. Test History: ringkasan dan sesi awal.](manual-assets/24_testing_history_01.jpg){width=15.5cm}

![Gambar 26b. Test History: daftar sesi lanjutan.](manual-assets/24_testing_history_02.jpg){width=15.5cm}

![Gambar 26c. Test History: detail sesi lanjutan.](manual-assets/24_testing_history_03.jpg){width=15.5cm}

![Gambar 26d. Test History: bagian akhir daftar.](manual-assets/24_testing_history_04.jpg){width=15.5cm}

## Comprehensive Test

Comprehensive Test menjalankan validasi beberapa skenario dalam satu rangkaian. Jalankan setelah setiap skenario dasar berhasil dan tersedia waktu pemeliharaan.

![Gambar 27. Comprehensive Scenario Validation.](manual-assets/25_testing_comprehensive_test.jpg){width=15.5cm}

## Performance Calibration

Calibration mengukur lingkungan aktual dan menyimpan benchmark untuk mendukung model performa. Pilih tier sesuai waktu yang tersedia; tier tinggi dapat berlangsung lama.

![Gambar 28a. Performance Calibration bagian konfigurasi.](manual-assets/26_testing_calibration_01.jpg){width=15.5cm}

![Gambar 28b. Performance Calibration bagian progress/hasil.](manual-assets/26_testing_calibration_02.jpg){width=15.5cm}

Jangan mematikan service selama calibration. Bila harus dihentikan, gunakan tombol stop agar state session lebih mudah ditelusuri.

# SOP Operasional Harian

## Checklist Sebelum Mulai

- [ ] Alamat dan sertifikat HTTPS benar.
- [ ] Login berhasil dengan akun/otorisasi yang sah.
- [ ] Tidak ada job error atau job lama yang masih berjalan tanpa penanggung jawab.
- [ ] Storage dan layanan dinyatakan sehat oleh administrator.
- [ ] Scanner/kamera telah diuji bila akan digunakan.
- [ ] Dataset input sudah diperiksa dan tidak mengandung data rahasia yang tidak perlu.

## SOP Penerbitan QR

1. Terima data dari sumber berwenang.
2. Validasi nama dan ID serta cek duplikasi.
3. Pilih tunggal atau massal.
4. Pilih algoritma sesuai kebijakan.
5. Generate dan tunggu sukses.
6. Cocokkan jumlah dan sampel output tanpa menghabiskan nonce produksi secara tidak sengaja.
7. Distribusikan melalui kanal yang disetujui.
8. Periksa log generate.

## SOP Verifikasi di Lokasi

1. Pastikan petugas login/halaman scanner siap.
2. Pindai QR satu kali.
3. Tunggu status final.
4. Cocokkan identitas dengan objek/orang bila proses bisnis mensyaratkan.
5. Terima hanya status **Valid dan Authentik**.
6. Tolak replay, data palsu, modified, signature invalid, dan tidak ditemukan.
7. Catat insiden serta waktu bila status tidak valid.
8. Jangan menghapus log sebagai cara memperbaiki status.

## SOP Akhir Shift

- [ ] Pastikan tidak ada job yang ditinggal tanpa penanggung jawab.
- [ ] Ekspor laporan shift bila diwajibkan.
- [ ] Catat error atau insiden beserta ID task/waktu.
- [ ] Logout.
- [ ] Amankan file CSV, ZIP QR, dan laporan sesuai klasifikasi data.

# Troubleshooting

## Tabel Masalah Umum

| Masalah | Penyebab yang mungkin | Tindakan pengguna |
|---|---|---|
| Tidak bisa login | Password salah, rate limit, sesi/browser bermasalah. | Cek keyboard, tunggu 1 menit, coba ulang satu kali; hubungi admin. |
| Redirect kembali ke login | Sesi berakhir. | Login kembali dan ulangi navigasi. |
| QR tidak terbaca | Blur, crop, refleksi, resolusi rendah. | Gunakan file asli/pencahayaan baik dan coba ulang. |
| Hasil replay pada scan pertama petugas | QR pernah dipindai saat QA/distribusi atau scan ganda. | Periksa log waktu/sumber; jangan reset nonce tanpa investigasi. |
| Upload ditolak | Ekstensi/ukuran salah atau request terlalu besar. | Gunakan format didukung, kecilkan/pecah batch. |
| Kamera tidak aktif | Izin ditolak atau bukan HTTPS. | Izinkan kamera dan gunakan domain HTTPS. |
| Scanner USB tidak mengirim | Fokus input hilang atau suffix Enter belum aktif. | Klik input, konfigurasi Enter, uji di editor teks. |
| Job berhenti/error | Input rusak, proses dihentikan, resource kurang. | Catat ID task, cek pesan, pecah batch, eskalasi. |
| Dashboard lambat | Log besar atau recalculation berjalan. | Tunggu, hindari refresh berulang, jalankan di luar jam sibuk. |
| HTTP 413 | Jumlah part atau total request melewati batas. | Kurangi jumlah/ukuran file per batch. |
| HTTP 429 | Rate limit tercapai. | Hentikan refresh/request otomatis dan tunggu window limit. |

## Halaman Error

![Gambar 29. Contoh halaman error/404.](manual-assets/27_error_404.jpg){width=15.5cm}

Saat melapor, sertakan waktu, URL/halaman, tindakan terakhir, pesan error, ID task, nama file (tanpa membocorkan data rahasia), dan screenshot. Jangan mengirim private key, password, isi `.env`, atau payload sensitif.

## Kapan Harus Eskalasi

Segera hubungi administrator jika banyak QR valid berubah menjadi invalid secara serentak, private key/permisson berubah tanpa jadwal, audit log hilang, storage penuh, error 5xx terus-menerus, atau ada indikasi akses tidak sah.

# Keamanan dan Tata Kelola Data

## Praktik Wajib Pengguna

- Gunakan hanya domain resmi.
- Jangan membagikan password atau menyimpannya di browser publik.
- Perlakukan file QR dan laporan sebagai data organisasi.
- Jangan mengubah file kunci RSA/ECDSA.
- Jangan menghapus log, nonce, statistik, payload, atau session test tanpa otorisasi.
- Gunakan fitur modifikasi hanya untuk pengujian berizin.
- Verifikasi integritas backup dan batasi akses arsip.
- Logout dari perangkat bersama.

## Pemisahan Data Produksi dan Uji

Gunakan prefix ID uji yang jelas, jadwal pengujian, serta folder/arsip terpisah. QR palsu hasil modifikasi harus diberi label **TEST/TIDAK BERLAKU** di luar gambar QR agar tidak tertukar dengan QR produksi.

## Backup Minimum untuk Administrator

Backup yang relevan mencakup `rsa_key.pem`, `ecdsa_key.pem`, `.env` melalui kanal rahasia, folder `logs`, data task, data payload yang masih aktif, serta QR/data asli sesuai kebijakan. Private key harus dienkripsi dan aksesnya dicatat.

# Referensi Cepat

## Route Penting

| Fungsi | Route |
|---|---|
| Login/Home | `/login`, `/` |
| QR Generator | `/qr_generator` |
| CSV Generator | `/generate_csv` |
| Upload Scanner | `/scanner` |
| Kamera HP | `/mobile_scan` |
| Scanner USB | `/verify_direct` |
| Modifikasi QR | `/modify_qr_page` |
| Job Massal | `/jobs` |
| Dashboard | `/dashboard` |
| Log Generate | `/log` |
| Log Verifikasi | `/log_verifikasi` |
| Audit Log | `/audit_log` |
| Profil Keamanan | `/security_profile` |
| Benchmark | `/benchmark` |
| Testing | `/testing/` |

## Ringkasan Keputusan Verifikasi

| Hasil | Terima? | Langkah berikutnya |
|---|---:|---|
| Valid dan Authentik | Ya | Lanjutkan proses bisnis. |
| Replay Attack | Tidak | Catat, tahan penggunaan ulang, investigasi. |
| Data Dimodifikasi/Palsu | Tidak | Simpan bukti dan eskalasi. |
| Signature Invalid | Tidak | Tolak dan periksa sumber. |
| Tidak Ditemukan | Tidak | Konfirmasi penerbit. |
| Error/tidak terbaca | Belum | Ulangi dengan input lebih baik; jangan langsung menerima. |

# Glosarium

| Istilah | Definisi ringkas |
|---|---|
| QR Code | Kode matriks dua dimensi yang menyimpan data/URL. |
| Payload | Isi data yang ditandatangani dan direpresentasikan oleh QR. |
| Digital signature | Bukti kriptografis integritas dan asal data menggunakan private key. |
| RSA-PSS | Skema signature RSA probabilistik yang digunakan sistem. |
| ECDSA P-256 | Algoritma signature kurva eliptik pada kurva P-256. |
| SHA-256 | Fungsi hash untuk menghasilkan ringkasan data. |
| Nonce | Nilai unik untuk membantu mendeteksi penggunaan ulang. |
| Replay attack | Penggunaan kembali payload/QR yang sebelumnya telah dipakai. |
| Tampering | Perubahan tidak sah pada data. |
| P95 | Persentil ke-95 dari distribusi waktu. |
| Async job | Pekerjaan background yang dipantau melalui ID dan progress. |
| Rate limit | Batas jumlah request dalam periode tertentu. |
| Audit log | Jejak tindakan penting untuk penelusuran. |

# Form Catatan Operasional

## Catatan Insiden Verifikasi

| Field | Isian |
|---|---|
| Nomor insiden |  |
| Tanggal dan waktu |  |
| Petugas |  |
| Lokasi/perangkat |  |
| Nama/ID yang tampil |  |
| Status verifikasi |  |
| Sumber scan | Upload / HP / USB / Massal |
| Nama file/ID task |  |
| Tindakan awal |  |
| Eskalasi kepada |  |
| Catatan penyelesaian |  |

## Riwayat Revisi Manual

| Versi | Tanggal | Ringkasan | Penyusun/Pengesah |
|---|---|---|---|
| 1.0 | 19 Juni 2026 | Penerbitan awal berdasarkan antarmuka aktif. |  |

## Persetujuan

| Peran | Nama | Tanggal | Tanda tangan |
|---|---|---|---|
| Penyusun |  |  |  |
| Pemeriksa |  |  |  |
| Pengesah |  |  |  |

**Akhir Buku Panduan Pengguna QR Code Security System**
