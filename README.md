# Logbook-UKP-Internship-Dokter
Tool desktop GUI untuk mengotomatisasi pengisian logbook UKP Puskesmas dari e-Puskesmas ke Portal logbook Internsip Dokter Indonesia - Kemkes RI. Menggunakan **Python + Tkinter + Selenium**.

> **Fungsi utama:** Scrape data pasien dari e-Puskesmas → Enrich anamnesis pakai AI Gemini → Auto input ke logbook UKP Kemkes RI.

## PR saat ini (Bantuin beresin dong ges hehe)

1. Pilih diagnosis dan diganosis banding. Kan sekarang masih manual tuh.

   **potensi solusinya:**
   ```python
    def select_diagnosis(driver, search_text):
        # 1. Klik container untuk membuka dropdown
        trigger = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".options-multi-diagnosis"))
        )
        trigger.click()
        
        # 2. Tunggu input search muncul di dalam dropdown yang baru terbuka
        # Dropdown biasanya memiliki class 'absolute' dan 'z-50'
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".options-multi-diagnosis input[placeholder='search']"))
        )
        
        # 3. Masukkan teks diagnosis
        search_input.clear()
        search_input.send_keys(search_text)
        
        # 4. Tekan Enter untuk trigger filtering (beberapa komponen butuh ini)
        search_input.send_keys(Keys.ENTER)
        
        # Tunggu sebentar agar animasi filtering selesai
        time.sleep(1)
        
        # 5. Pilih opsi pertama yang muncul yang mengandung teks yang kita cari
        # Kita cari div di dalam dropdown yang teksnya cocok
        options_xpath = f"//div[contains(@class, 'options-multi-diagnosis')]//div[contains(text(), '{search_text}')]"
        first_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, options_xpath))
        )
        first_option.click()
    ```
Tapi gw belum nyoba dan masih sibuk isip dulu

# Cara pakai:
# select_diagnosis(driver, "Insulin-dependent")
# select_diagnosis(driver, "Other atopic dermatitis")
## 📦 Fitur

| Tab | Fungsi | Output |
|-----|--------|--------|
| **Tab 1** | Scrape data pasien dari e-Puskesmas (status "Sudah Diperiksa") | CSV mentah |
| **Tab 2** | Generate paragraf anamnesis via Google Gemini AI | CSV + anamnesis ter-enrich |
| **Tab 3** | Auto input ke form logbook UKP Kemkes RI | Submit ke web |

---

## ⚙️ Persiapan & Instalasi

### 1. Install Python

Pastikan Python 3.8+ sudah terinstall. Cek dengan:
```bash
python --version
```

### 2. Install Dependencies

```bash
pip install selenium webdriver-manager pandas beautifulsoup4
```

Atau kalau mau pakai Edge atau browser lain silakan sesuaikan web-driver. 

### 3. Chrome & ChromeDriver

Pastikan Google Chrome sudah terinstall. Webdriver-manager akan otomatis download ChromeDriver yang sesuai.

---

## 🔧 Konfigurasi Awal

Buka file `input_borang_isip.py` dan cari bagian **KONFIGURASI** di awal file:

```python
# ============================================================
# KONFIGURASI
# ============================================================
DEBUG_PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL_PKM = "https://internsip-logbook.kemkes.go.id/peserta/ukpPkm"
URL_E_PUSKESMAS = "https://kotakediri.epuskesmas.id/pelayanan?status_periksa=3"
```

### Yang mungkin perlu diubah:

| Variable | Keterangan |
|----------|------------|
| `CHROME_PATH` | **Wajib disesuaikan** dengan lokasi Chrome di komputermu. Cek di `C:\Program Files\Google\Chrome\Application\chrome.exe` atau `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe` |
| `URL_E_PUSKESMAS` | Ganti dengan URL e-Puskesmas kotamu. Contoh: `https://<kota>.epuskesmas.id/pelayanan?status_periksa=3` |
| `URL_PKM` | URL logbook UKP Kemkes RI. Biasanya sama, tapi bisa disesuaikan |
| `DEBUG_PORT` | Port untuk Chrome Debug Mode. Biarkan `9222` kecuali ada konflik |

---

## 🚀 Cara Pakai

### 1. Buka Chrome Debug Mode

**Cara 1: Via tombol di aplikasi**
- Jalankan program, klik tombol **"🚀 Buka Chrome Debugger"**

**Cara 2: Via command line**
```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium\AutomationProfile"
```

> ⚠️ **PENTING:** Chrome Debugger HARUS terbuka SEBELUM menjalankan proses apapun di aplikasi.

---

### 2. Tab 1: Ambil Data Pasien

**Tujuan:** Scrape data pasien dari e-Puskesmas

**Langkah:**
1. Di Chrome Debugger, login ke e-Puskesmas
2. Pilih poli & tanggal
3. Pastikan halaman daftar pasien dengan status **"Sudah Diperiksa"** sudah terbuka
4. Di aplikasi:
   - Tentukan folder output
   - Klik **"▶️ MULAI SCRAPING"**
5. Tunggu hingga selesai
6. File CSV akan tersimpan di folder output

**Output:** `data_ukp_<tanggal>.csv`

---

### 3. Tab 2: Enrich Anamnesis

**Tujuan:** Generate anamnesis pakai AI Gemini

**Langkah:**
1. Di Chrome Debugger, buka `https://gemini.google.com`
2. Login ke akun Google-mu
3. Di aplikasi:
   - Pilih file CSV hasil Tab 1 sebagai input
   - Tentukan nama file output
   - Klik **"▶️ MULAI PENYUSUNAN ANAMNESIS"**
4. Tunggu proses selesai (bisa agak lama tergantung jumlah data)

**Output:** CSV dengan kolom `anamnesis` yang sudah di-generate AI

---

### 4. Tab 3: Auto Input UKP

**Tujuan:** Input data otomatis ke logbook UKP Kemkes RI

**Langkah:**
1. Di Chrome Debugger, buka `https://internsip-logbook.kemkes.go.id/peserta/ukpPkm`
2. Login ke akun Kemkes RI-mu
3. Di aplikasi:
   - Pilih file CSV hasil Tab 2
   - Klik **"▶️ JALANKAN AUTO INPUT UKP"**
4. Untuk setiap data:
   - Form akan terisi otomatis
   - Muncul popup: **"Siap Submit"**
   - Lo **cek manual** semua isian
   - Klik **"Kirim Data"** atau **"Simpan Sebagai Draf"**
   - Tekan OK di popup untuk lanjut ke data berikutnya

---

## 📁 Struktur CSV

| Kolom | Keterangan |
|-------|------------|
| `nama_dokter` | Nama dokter pemeriksa |
| `no_rekam_medis` | Nomor rekam medis |
| `sumber_data` | Sumber data (Rawat Jalan) |
| `tanggal_pelayanan` | Tanggal pelayanan |
| `inisial_pasien` | Inisial pasien (3 huruf kapital) |
| `jenis_kelamin` | Laki-laki / Perempuan |
| `kategori_pasien` | Bayi-Anak / Dewasa / Lansia |
| `berat_badan` | Berat badan (kg) |
| `tinggi_badan` | Tinggi badan (cm) |
| `anamnesis` | Anamnesis (keluhan) - di-generate AI |
| `fisik` | Pemeriksaan fisik |
| `penunjang` | Pemeriksaan penunjang |
| `diagnosis` | Diagnosis |
| `tata_laksana_farmako` | Obat-obatan |
| `tata_laksana_nonfarmako` | Non-farmakoterapi |
| `monitoring` | Monitoring dan evaluasi |
| `status_rujukan` | Rujuk / Tidak rujuk |
| `keterangan_CKG` | Status CKG |

---

## 🔧 Troubleshooting

| Masalah | Kemungkinan Penyebab & Solusi |
|---------|-------------------------------|
| **"Driver Error"** | Chrome Debugger belum dibuka. Buka dulu lewat tombol atau command line. |
| **"Pastikan Chrome sudah dibuka di mode debugging"** | Path Chrome salah atau port `9222` dipakai aplikasi lain. Cek `CHROME_PATH`. |
| **Gemini tidak ngerespon / gagal generate** | Belum login Gemini. Login manual dulu di Chrome Debugger. |
| **Gagal input di Tab 3** | Belum login logbook UKP. Login manual dulu. Atau URL berbeda (`URL_PKM`). |
| **Tiba-tiba error di tengah jalan** | Refresh halaman atau koneksi internet bermasalah. Stop proses, refresh, ulangi dari data terakhir. |
| **Pasien tidak terbaca** | Pastikan di e-Puskesmas statusnya "Sudah Diperiksa" (warna hijau). |
| **Pagination (nomor halaman) error** | Cek apakah URL e-Puskesmas-mu punya struktur pagination yang sama. |

---

## 📝 Catatan Penting

1. **Jangan close Chrome Debugger** selama proses berjalan
2. **Login manual dulu** ke e-Puskesmas, Gemini, dan logbook UKP
3. Tab 3 butuh **supervisi manual** (lo tetap harus cek & klik submit sendiri)
4. Untuk Tab 1, pastikan halaman daftar pasien **sudah di-filter** sesuai poli dan tanggal
5. Program hanya untuk **otomatisasi input**, bukan menggantikan verifikasi medis

---

## 📂 Struktur Folder

```
project/
├── input_borang_isip.py          # Main program
├── README.md             # This file
└── data/                 # Folder output CSV, tapi bebas sih mau taruh mana aja
    ├── data_ukp_250626.csv
    └── data_ukp_250626_enriched.csv
```

---

## 📜 License

Made with 🫘 by **yaqinkdr** • 2026


```

---

**File `requirements.txt`-nya sekalian (kalo mau pakai, tapi enak pakai pip):**

```txt
selenium
webdriver-manager
pandas
beautifulsoup4
```

**Disclaimer:** Aplikasi ini adalah alat bantu pribadi untuk otomatisasi input data di lingkungan kerja penulis. Tidak terafiliasi dengan **Kementerian Kesehatan RI**, **e-Puskesmas**, atau **Infokes**. Penggunaan di luar tanggung jawab pribadi sepenuhnya ada pada pengguna.
---
