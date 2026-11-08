# Upload proyek Olist ke GitHub

1. Ekstrak ZIP dan buka folder Olist_PowerBI_Portfolio.
2. Buat repository GitHub kosong, misalnya olist-ecommerce-analysis.
3. Buka terminal pada folder yang berisi README.md dan jalankan perintah berikut. Ganti URL jika nama repository berbeda.

```bash
git init
git add .
git commit -m "Add Olist data analysis and Power BI portfolio"
git branch -M main
git remote add origin https://github.com/suryawinaldi/olist-ecommerce-analysis.git
git push -u origin main
```

Gunakan Git atau GitHub Desktop karena CSV gabungan berukuran sekitar 26 MB dan 41 MB. README menampilkan grafik notebook dan menyediakan akses file proyek. Untuk dashboard interaktif, unduh seluruh proyek, sesuaikan FolderData, lalu buka Olist.pbip di Power BI Desktop.

Dataset analitik gabungan disertakan. ZIP mentah Kaggle belum disertakan. Sumber dan cara regenerasi tercantum di README. Pertahankan atribusi dan ketentuan CC BY-NC-SA 4.0 untuk data Olist serta adaptasinya.
