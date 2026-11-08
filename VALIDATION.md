# Pemeriksaan paket — 8 November 2026

## Berhasil diperiksa dalam sesi ini

- Seluruh lima sel kode notebook dieksekusi berurutan di IPython pada salinan sementara, dengan pandas 2.2.3, NumPy 2.3.5, dan Matplotlib 3.10.8. Seluruh assertion lulus, empat grafik dihasilkan, dan isi metrics.json hasil baru sama persis dengan unggahan.
- 99.441 pesanan unik dan 112.650 item; jumlah uang pada tingkat item dan pesanan direkonsiliasi oleh notebook.
- SQL cube dijalankan di SQLite dari tabel pesanan analitik yang disertakan: jumlah pesanan, kelayakan, keterlambatan, dan nilai produk cocok untuk seluruh periode dan periode utama.
- 62 berkas JSON/PBIP/PBIR/PBISM berhasil diparse sebagai JSON. Ini bukan validasi terhadap skema Microsoft.
- 50 kontainer visual memiliki 67 referensi kolom/measure yang tersedia pada model. Model memuat 27 measure. Kolom input yang diminta model tersedia pada CSV.
- Sintaks skrip Python diperiksa tanpa menjalankan pipeline data mentah.

Jalankan pemeriksaan SQL dan referensi model dari akar proyek:

```bash
python src/verify_portfolio.py
```

Untuk analisis penuh, jalankan seluruh sel `notebooks/Analisis_Olist.ipynb` dari akar proyek atau folder notebooks. Notebook menulis ulang `results/`; simpan perubahan lokal sebelum menjalankannya.

## Batas verifikasi

- Power BI Desktop tidak dijalankan dalam pemeriksaan ini. Refresh Power Query, eksekusi DAX, rendering PBIR, dan perilaku kombinasi filter belum diuji ulang. Pernyataan di paket awal tentang dashboard yang pernah dibuka merupakan riwayat yang diberikan pemilik, bukan bukti pengujian sesi ini.
- Skrip build.py dan export_data.py membutuhkan ZIP sumber dengan SHA-256 tertentu. ZIP mentah tidak disertakan, sehingga regenerasi dari sumber belum diuji. Pengecekan SQL cube di atas menggunakan CSV gabungan, bukan rekonstruksi seluruh join sumber.
- `bi/dashboard_template.html` adalah template. HTML mandiri yang berfungsi dihasilkan build.py setelah data sumber tersedia; template bukan tautan dashboard siap pakai.
- Angka nilai produk bukan profit, pendapatan bersih Olist, ataupun kerugian akibat keterlambatan.

## Perbaikan portofolio berikutnya

1. Tambahkan screenshot asli ketiga halaman Power BI beserta kondisi filter, dan tabel pemeriksaan KPI/filter dari Desktop.
2. Sertakan petunjuk versi/berkas ZIP sumber yang benar, checksum, dan audit regenerasi saat ZIP tersedia.
3. Gunakan tabel tanggal dan dimensi bersama jika model diperluas untuk analisis waktu dan filter lintas fakta. Saat ini kategori item dan kategori utama pesanan sengaja memiliki makna/filter berbeda seperti dijelaskan README.
4. Tambahkan workbook Excel terpisah hanya bila ingin membuktikan kemampuan Power Query/PivotTable di Excel; paket ini sudah menunjukkan SQL, Python, dan Power BI, tetapi belum memuat bukti Excel.
