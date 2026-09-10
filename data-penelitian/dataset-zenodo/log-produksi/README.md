# Log produksi layanan verifikasi QR Code

Dua berkas ini adalah log operasional layanan produksi pada domain www.rsa-pss.com,
dan menjadi sumber angka pada Tabel 4 serta Subbab 3.1 naskah efisiensi.

## Isi

| Berkas | Baris | Cakupan |
|---|---|---|
| `log_generate.csv.gz` | 105.000 | Setiap pembangkitan QR Code, 29 Juli – 7 September 2026 |
| `log_verifikasi.csv.gz` | 102.180 | Setiap verifikasi, periode yang sama |

Keduanya CSV terkompresi gzip. Buka dengan `gunzip`, atau langsung:

```python
import gzip, csv
with gzip.open('log_generate.csv.gz', 'rt') as f:
    rows = list(csv.DictReader(f))
```

## Kolom yang dipakai naskah

`log_generate.csv` memecah latensi pembangkitan menjadi tahap: `Waktu Data`,
`Waktu Sign`, `Waktu QR`, `Waktu Save`, dan `Total Waktu`, seluruhnya dalam detik.
Kolom `Ukuran File (KB)` memuat ukuran berkas PNG QR Code yang benar-benar
diterbitkan.

`log_verifikasi.csv` memecah latensi verifikasi menjadi `Waktu Load`,
`Waktu Decode`, `Waktu Verify`, `Waktu DB`, dan `Total Waktu`.

## Cara mereproduksi angka naskah

```bash
# Ukuran berkas QR: rata-rata 0,35 KB pada rentang 0,31-0,39
zcat log_generate.csv.gz | awk -F, 'NR>1{s+=$8;n++; if($8<min||n==1)min=$8; if($8>max)max=$8}
  END{printf "n=%d min=%.2f max=%.2f rata=%.2f KB\n",n,min,max,s/n}'
```

## Catatan privasi

Seluruh identitas pada log bersifat sintetis: 100.000 baris bernama "Test User N"
dan 5.000 baris bernama "User N", dengan ID berpola `test_NNNNNNNN` dan
`user_NNNNNN`. Tidak ada data pribadi orang sungguhan.

## Periode pengukuran

Naskah membedakan dua periode karena jalur penyimpanan dioptimasi di antaranya.
Baris berstempel 2026-07 mencerminkan konfigurasi sebelum optimasi, dan 2026-09
sesudahnya. Tahap kriptografis nyaris tidak berubah antarperiode; yang berubah
adalah tahap penyimpanan dan basis data.
