# Uji Beban HTTP dari Host Terpisah

Berkas di folder ini mereproduksi pengujian beban yang dilaporkan pada subbab 3.7
dan 4.6 Laporan Akhir, serta subbab III.G naskah JAIC.

## Mengapa pembangkit beban harus di luar server

Menjalankan pembangkit beban pada host yang sama dengan aplikasi membuat keduanya
berebut prosesor, sehingga yang terukur adalah kompetisi sumber daya, bukan kapasitas
layanan. Tiga sesi pengujian awal penelitian ini gagal justru karena hal itu: angka
latensinya hanya mencerminkan waktu tunggu sampai batas waktu tercapai.

Skrip di sini karena itu dirancang dijalankan dari komputer terpisah.

## Isi

| Berkas | Fungsi |
|---|---|
| `uji_kalibrasi.js` | Kalibrasi pendahuluan, 50 VU selama 30 detik |
| `uji_beban.js` | Uji beban empat tingkat: 100, 500, 1.000, 1.500 VU |
| `buat_token.py` | Membangkitkan kumpulan token verifikasi sekali pakai |
| `lengkapi_rekaman_qr.py` | Menulis rekaman QR asli agar verifikasi menempuh jalur penuh |

## Urutan menjalankan

Ketiga langkah persiapan dijalankan **di server**, pada lingkungan staging yang
terpisah dari produksi:

```bash
sudo venv/bin/python data-penelitian/uji-beban/buat_token.py 120000
sudo venv/bin/python data-penelitian/uji-beban/lengkapi_rekaman_qr.py
sudo venv/bin/python -c "import app; app.backfill_qr_record_index()"
```

Langkah kedua tidak boleh dilewati. Tanpa rekaman QR asli, `find_original_qr_data()`
gagal dan verifikasi berhenti pada cabang "Data Tidak Ditemukan", melewatkan
pencatatan nonce, pemeriksaan replay, kedaluwarsa, dan monotonik — yaitu justru
bagian yang hendak diukur.

Langkah ketiga menandai index rekaman sebagai otoritatif. Tanpa itu pencarian jatuh
ke pemindaian direktori dan memakan 148,6 ms per verifikasi alih-alih 0,074 ms.

Berikutnya **di komputer penguji**:

```bash
scp <server>:/path/{token_uji.csv,uji_beban.js,uji_kalibrasi.js} .
k6 run uji_kalibrasi.js
k6 run uji_beban.js
```

## Syarat kesahihan

Kalibrasi wajib dijalankan lebih dulu. Pada ringkasannya, `dropped_iterations` harus
bernilai nol dan `http_req_failed` di bawah 1%. Bila ada iterasi yang dijatuhkan,
komputer penguji yang jenuh lebih dulu dan hasilnya tidak sah.

Pada uji beban, periksa penghitung `iterasi_jalur_replay`. Token bersifat sekali
pakai; bila iterasi melampaui jumlah token, indeksnya berputar dan sisa pengukuran
beralih ke jalur replay. Nilai nol berarti seluruh pengukuran murni jalur QR sah.

## Prasyarat lingkungan

Reverse proxy perlu `worker_connections` yang memadai beserta `worker_rlimit_nofile`.
Keduanya sempat menjadi penyebab laju kegagalan 45% dan 7,6% pada pengujian penelitian
ini, dan keduanya bukan batas aplikasi. Rate limit aplikasi juga perlu dilonggarkan
pada lingkungan uji, sebab nilai bakunya akan menghentikan pengujian setelah 1.000
permintaan sehingga laju kesalahan mencerminkan rate limiter.

## Hasil yang direproduksi

25.607 permintaan, throughput datar sekitar 105 permintaan per detik, laju kesalahan
0,00% pada 500 pengguna serentak. Waktu respons mengikuti hukum Little dengan selisih
1,4 sampai 7,0 persen. Data lengkapnya pada `../dataset-zenodo/stress-http-eksternal/`.
