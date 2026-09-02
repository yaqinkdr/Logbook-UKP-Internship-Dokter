import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import subprocess
import os
import time
import json
import csv
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup

# ============================================================
# KONFIGURASI
# ============================================================
DEBUG_PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL_PKM = "https://internsip-logbook.kemkes.go.id/peserta/ukpPkm"
URL_E_PUSKESMAS = "https://kotakediri.epuskesmas.id/pelayanan?status_periksa=3"

SYSTEM_INSTRUCTION = """Susun anamnesis rekam medis dari data yang saya berikan. Output hanya 1 paragraf ringkas PLAIN TEXT berisi keluhan utama, onset, gambaran keluhan, saat apa berkurang, saat apa bertambah, riwayat alergi, pengobatan, serta faktor risiko relevan jika ada terkait penyakit atau komplikasinya. Untuk penyakit akut, Riwayat Penyakit Dahulu dianggap (-) kecuali terdapat komorbid kronis yang diberikan dalam data sampaikan dengan BAHASA awam. Boleh karang sesuai teori karena semua pasien sesuai teori. JANGAN ada bold, JANGAN beri aku bertanyaan atau saran karena aku tidak konsultasi. JANGAN menulis ulang diagnosis. JANGAN pakai kata lapor atau turunannya, pakai mengeluh. Aku butuh kamu agar catatanku lengkap saat waktuku mengetik terbatas."""

class UKPLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Borang PKM otomatis - Vibe code by yaqinkdr 2026")
        self.root.geometry("880x700")
        
        self.stop_flag = False
        self.active_thread = None
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[12, 4])
        
        self.setup_ui()

    def setup_ui(self):
        # Top Frame
        top_frame = ttk.LabelFrame(self.root, text=" ⚙️ KONTROL CHROME DEBUGGING MODE ", padding=10)
        top_frame.pack(fill="x", padx=15, pady=10)
        ttk.Label(top_frame, text="Buka Chrome khusus untuk otomatisasi:").pack(side="left", padx=5)
        ttk.Button(top_frame, text="🚀 Buka Chrome Debugger", command=self.start_chrome_debug).pack(side="right", padx=5)

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.tab1 = ttk.Frame(self.notebook, padding=10)
        self.tab2 = ttk.Frame(self.notebook, padding=10)
        self.tab3 = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(self.tab1, text=" 📥 1. AMBIL DATA PASIEN ")
        self.notebook.add(self.tab2, text=" 🤖 2. ENRICH ANAMNESIS ")
        self.notebook.add(self.tab3, text=" 📤 3. AUTO INPUT UKP ")
        
        self.setup_tab1()
        self.setup_tab2()
        self.setup_tab3()
        
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=5)
        status_bar.pack(fill="x", side="bottom")

    def start_chrome_debug(self):
        cmd = f'"{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT} --user-data-dir="C:\\selenium\\AutomationProfile"'
        try:
            subprocess.Popen(cmd, shell=True)
            self.set_status("✅ Chrome Debugger dibuka.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka Chrome:\n{e}")

    def get_driver(self):
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
        try:
            return webdriver.Chrome(options=options)
        except Exception as e:
            messagebox.showerror("Driver Error", f"Pastikan Chrome sudah dibuka di mode debugging!\n{e}")
            return None

    def log(self, tab_num, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        def _write():
            if tab_num == 1 and hasattr(self, 'log_t1'):
                self.log_t1.insert(tk.END, full_msg); self.log_t1.see(tk.END)
            elif tab_num == 2 and hasattr(self, 'log_t2'):
                self.log_t2.insert(tk.END, full_msg); self.log_t2.see(tk.END)
            elif tab_num == 3 and hasattr(self, 'log_t3'):
                self.log_t3.insert(tk.END, full_msg); self.log_t3.see(tk.END)
        self.root.after(0, _write)

    def set_status(self, text):
        self.status_var.set(text)

    def rem_tangan_popup(self, tab_num, message):
        self.log(tab_num, "🛑 REM TANGAN AKTIF - Menunggu user...")
        messagebox.showinfo(f"Tab {tab_num} - Siapkan Halaman", message)

    def _navigate_to_page(self, driver, target_page):
        self.log(1, f"Navigasi ke halaman {target_page}...")
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(0.3)
        
        # Coba langsung
        try:
            page_btn = driver.find_element(By.XPATH, f"//li[contains(@class, 'clickable')]/span[text()='{target_page}'] | //a[text()='{target_page}']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", page_btn)
            time.sleep(0.5)
            
            # ✅ TAMBAHKAN: Tunggu sampe halaman aktif
            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.CSS_SELECTOR, ".pagination li.active span").text == str(target_page)
            )
            
            self.log(1, f"Berhasil ke halaman {target_page} (langsung)")
            return True
        except:
            pass
        
        # Kalo target > 7
        if target_page > 7:
            triggers = list(range(7, target_page, 2))
            
            for trigger in triggers:
                try:
                    trigger_btn = driver.find_element(By.XPATH, f"//li[contains(@class, 'clickable')]/span[text()='{trigger}'] | //a[text()='{trigger}']")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger_btn)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", trigger_btn)
                    self.log(1, f"   Trigger {trigger}")
                    time.sleep(1.0)  # Tunggu pagination refresh
                except:
                    self.log(1, f"   Trigger {trigger} gagal")
                    return False
            
            # Terakhir klik target
            try:
                page_btn = driver.find_element(By.XPATH, f"//li[contains(@class, 'clickable')]/span[text()='{target_page}'] | //a[text()='{target_page}']")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_btn)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", page_btn)
                time.sleep(0.5)
                
                # ✅ TAMBAHKAN: Tunggu sampe halaman aktif
                WebDriverWait(driver, 5).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, ".pagination li.active span").text == str(target_page)
                )
                
                self.log(1, f"Berhasil ke halaman {target_page} (trigger)")
                return True
            except:
                self.log(1, f"Gagal klik target {target_page}")
                return False
        
        return False
    def click_checkbox_by_order(self, driver, order=1):
        """Centang checkbox Tata Laksana"""
        try:
            checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox' and not(@disabled)]")
            if len(checkboxes) >= order:
                checkbox = checkboxes[order - 1]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                if not checkbox.is_selected():
                    driver.execute_script("arguments[0].click();", checkbox)
                    time.sleep(0.4)
                return True
        except:
            pass
        return False
        
    def fill_text_by_placeholder_order(self, driver, placeholder, text, order=1):
        """Isi input berdasarkan urutan (untuk field dengan placeholder sama di tatalaksana)"""
        try:
            elems = WebDriverWait(driver, 10).until(
                lambda d: d.find_elements(By.XPATH, f"//input[@placeholder='{placeholder}']")
            )
            if len(elems) >= order:
                elem = elems[order - 1]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                elem.clear()
                if text and text != "AWAS_KOSONG":
                    elem.send_keys(str(text))
                time.sleep(0.4)
                return True
        except:
            pass
        return False 
        
    def fill_text_by_placeholder(self, driver, placeholder, text):
        try:
            elem = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//input[@placeholder='{placeholder}']"))
            )
            elem.clear()
            if text and text != "AWAS_KOSONG":
                elem.send_keys(str(text))
            time.sleep(0.3)
            return True
        except:
            return False

    def fill_textarea_by_contains(self, driver, partial_placeholder, text):
        try:
            elem = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//textarea[contains(@placeholder, '{partial_placeholder}')]"))
            )
            elem.clear()
            if text and text != "AWAS_KOSONG":
                elem.send_keys(str(text))
            time.sleep(0.3)
            return True
        except:
            return False

    def select_dropdown_by_label(self, driver, label, value):
        try:
            btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, f"//label[contains(text(), '{label}')]/following::button[1]"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            btn.click()
            time.sleep(0.6)
            option = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//li//span[text()='{value}']"))
            )
            option.click()
            time.sleep(0.4)
            return True
        except:
            return False

    def click_tambah_data(self, driver):
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Tambah Data UKP']/.. | //a[contains(., 'Tambah Data')]"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            btn.click()
            time.sleep(3)
            return True
        except:
            self.log(3, "  ⚠️ Gagal klik tombol Tambah Data")
            return False
            
    def get_final_ai_response(self, driver):
        """
        Fungsi Polling Pintar untuk memantau streaming teks Gemini sampai benar-benar selesai mengetik.
        """
        last_text = ""
        stable_count = 0
        max_retries = 30 # Beri batas toleransi pengecekan (30 kali cek)
        
        self.log(2, "  ⏳ Memulai pemantauan streaming jawaban Gemini...")
        
        for i in range(max_retries):
            try:
                # Cari semua container sesuai temuan diagnostik selector Anda
                responses = driver.find_elements(By.CSS_SELECTOR, 'div[id^="model-response-message-content"]')
                
                if responses:
                    current_text = responses[-1].text.strip()
                    
                    # Jika teks sudah muncul dan panjangnya sama dengan pengecekan sebelumnya
                    if current_text and current_text == last_text:
                        stable_count += 1
                        # Jika teks tidak berubah selama 3x pengecekan berturut-turut (sekitar 3 detik)
                        if stable_count >= 3:
                            self.log(2, "  ✨ Gemini selesai mengetik (Respons Stabil).")
                            return current_text
                    else:
                        # Jika teks masih bertambah/berubah, reset counter stabilitas
                        stable_count = 0
                        last_text = current_text
                        
            except Exception as e:
                # Abaikan error selagi streaming karena DOM Gemini sangat dinamis saat me-render Markdown
                pass
                
            # Berikan jeda 1 detik di setiap putaran untuk melihat perkembangan perubahan teks
            time.sleep(1.0)
            
        # Fallback jika mentok mencapai batas waktu maksimal, kembalikan teks terakhir yang tertangkap
        return last_text if last_text else None
    # ====================== TAB 1 ======================
    def setup_tab1(self):
        f_config = ttk.LabelFrame(self.tab1, text=" Konfigurasi Scraping e-Puskesmas ", padding=10)
        f_config.pack(fill="x", pady=5)
        
        ttk.Label(f_config, text="Output Folder:").grid(row=0, column=0, sticky="w", pady=5)
        self.t1_output_dir = tk.StringVar(value=r"C:\Users\HP\Downloads\Temp")
        ttk.Entry(f_config, textvariable=self.t1_output_dir, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(f_config, text="Browse", command=lambda: self.t1_output_dir.set(filedialog.askdirectory())).grid(row=0, column=2)
        
        f_actions = ttk.Frame(self.tab1, padding=5)
        f_actions.pack(fill="x", pady=5)
        
        self.btn_start_t1 = ttk.Button(f_actions, text="▶️ MULAI SCRAPING", command=self.start_tab1_process)
        self.btn_start_t1.pack(side="left", padx=5)
        self.btn_stop_t1 = ttk.Button(f_actions, text="⏹️ STOP", state="disabled", command=self.stop_process)
        self.btn_stop_t1.pack(side="left", padx=5)
        
        self.log_t1 = scrolledtext.ScrolledText(self.tab1, height=20, font=("Consolas", 9))
        self.log_t1.pack(fill="both", expand=True, pady=5)

    def start_tab1_process(self):
        self.stop_flag = False
        self.btn_start_t1.config(state="disabled")
        self.btn_stop_t1.config(state="normal")
        threading.Thread(target=self._run_tab1_thread, daemon=True).start()

    # ====================== HELPER FUNCTIONS ======================
    def extract_number_from_text(self, text):
        if not text or text == "AWAS_KOSONG":
            return "AWAS_KOSONG"
        match = re.search(r'(\d+[.,]?\d*)', text.replace(',', '.'))
        return match.group(1) if match else "AWAS_KOSONG"

    def ekstrak_berat_tinggi(self, soup):
        berat = "AWAS_KOSONG"
        tinggi = "AWAS_KOSONG"
        try:
            table = soup.select_one("table#table_data_periksafisik")
            if table:
                tbody = table.find('tbody')
                if tbody:
                    first_row = tbody.find('tr')
                    if first_row:
                        cols = first_row.find_all('td')
                        thead = table.find('thead')
                        if thead:
                            header_row = thead.find('tr')
                            if header_row:
                                headers = header_row.find_all('td')
                                for i, th in enumerate(headers):
                                    text = th.get_text(strip=True)
                                    if "Tinggi Badan" in text and i < len(cols):
                                        tinggi = self.extract_number_from_text(cols[i].get_text(strip=True))
                                    if "Berat Badan" in text and i < len(cols):
                                        berat = self.extract_number_from_text(cols[i].get_text(strip=True))
            
            # Fallback
            if berat == "AWAS_KOSONG":
                bb = self.get_text_by_label(soup, "Berat Badan")
                berat = self.extract_number_from_text(bb)
            if tinggi == "AWAS_KOSONG":
                tb = self.get_text_by_label(soup, "Tinggi Badan")
                tinggi = self.extract_number_from_text(tb)
        except:
            pass
        return berat, tinggi

    def get_text_by_label(self, soup, label, default="AWAS_KOSONG"):
        try:
            for td in soup.find_all('td'):
                if label in td.get_text(strip=True):
                    next_td = td.find_next_sibling('td')
                    if next_td:
                        text = next_td.get_text(strip=True)
                        if text:
                            return text
        except:
            pass
        return default

    def ekstrak_ckg(self, soup):
        try:
            pkg_div = soup.select_one("#content_pelayanan_pkg")
            if pkg_div:
                text = pkg_div.get_text()
                if "Tandai sudah CKG" in text:
                    return "Belum"
                if pkg_div.select("table tbody tr"):
                    return "Sudah"
        except:
            pass
        return "AWAS_KOSONG"

    def ekstrak_td(self, soup):
        """Ekstrak Sistole dan Diastole"""
        sistole = "AWAS_KOSONG"
        diastole = "AWAS_KOSONG"
        try:
            # Dari tabel header
            table = soup.select_one("table#table_data_periksafisik")
            if table:
                thead = table.find('thead')
                if thead:
                    headers = [th.get_text(strip=True) for th in thead.find_all(['td', 'th'])]
                    tbody_row = table.select_one("tbody tr")
                    if tbody_row:
                        cols = tbody_row.find_all('td')
                        for i, h in enumerate(headers):
                            if i < len(cols):
                                text = cols[i].get_text(strip=True)
                                if any(x in h for x in ["Sistole"]):
                                    sistole = self.extract_number_from_text(text)
                                elif any(x in h for x in ["Diastole"]):
                                    diastole = self.extract_number_from_text(text)

            # Fallback label
            if sistole == "AWAS_KOSONG":
                sistole = self.extract_number_from_text(self.get_text_by_label(soup, "Sistole"))
            if diastole == "AWAS_KOSONG":
                diastole = self.extract_number_from_text(self.get_text_by_label(soup, "Diastole"))
        except:
            pass
        return sistole, diastole
        
    def ekstrak_rr_nadi(self, soup):
        """Ekstrak RR dan Nadi"""
        rr = "AWAS_KOSONG"
        nadi = "AWAS_KOSONG"
        try:
            # Dari tabel header
            table = soup.select_one("table#table_data_periksafisik")
            if table:
                thead = table.find('thead')
                if thead:
                    headers = [th.get_text(strip=True) for th in thead.find_all(['td', 'th'])]
                    tbody_row = table.select_one("tbody tr")
                    if tbody_row:
                        cols = tbody_row.find_all('td')
                        for i, h in enumerate(headers):
                            if i < len(cols):
                                text = cols[i].get_text(strip=True)
                                if any(x in h for x in ["Detak Nadi"]):
                                    nadi = self.extract_number_from_text(text)
                                elif any(x in h for x in ["Nafas"]):
                                    rr = self.extract_number_from_text(text)

            # Fallback label
            if nadi == "AWAS_KOSONG":
                nadi = self.extract_number_from_text(self.get_text_by_label(soup, "Detak Nadi"))
            if rr == "AWAS_KOSONG":
                rr = self.extract_number_from_text(self.get_text_by_label(soup, "Nafas"))
        except:
            pass
        return nadi, rr
        
    def ekstrak_fisik(self, soup):
        """Fisik lengkap dengan TD yang benar"""
        try:
            sistole, diastole = self.ekstrak_td(soup)
            
            td = f"{sistole}/{diastole}" if sistole != "AWAS_KOSONG" and diastole != "AWAS_KOSONG" else "120/80"
            
            nadi, rr = self.ekstrak_rr_nadi(soup)

            template = f"""GCS: E4 V5 M6 TD: {td} mmHg N: {nadi} x/m RR: {rr} x/m Suhu: 36.6 °C Spo2: 99 %
K/L: a(-), i(-), c(-), d(-), pupil isokor 3 mm/3 mm, RC (+/+)
Tho: Simetris, retraksi (-)
Cor: S1-S2 normal, murmur (-), gallop (-)
Pul: Ves/Ves, ronkhi (-), wheezing (-)
Abd: BU (+), turgor baik, nyeri tekan (-)
Eks: Akral hangat, CRT < 2 detik, edema (-)"""
            
            return template
        except:
            return "AWAS_KOSONG"
            
    def ekstrak_penunjang(self, soup):
        """Ekstrak hasil laboratorium dari tabel 'Pemeriksaan Detail Laboratorium'"""
        try:
            # Cari header tabel
            headers = soup.find_all(string=lambda text: text and "Pemeriksaan Detail Laboratorium" in text)
            
            if not headers:
                # Fallback: cari teks di seluruh halaman
                if "Pemeriksaan Detail Laboratorium" not in soup.get_text():
                    return "Tidak dilakukan"
            
            # Ambil tabel setelah header
            table = None
            for header in headers:
                parent = header.find_parent()
                if parent:
                    table = parent.find_next("table")
                    if table:
                        break
            
            if not table:
                return "Tidak dilakukan"

            rows = table.find_all("tr")
            results = []

            # Skip header row, ambil data mulai baris ke-2
            for row in rows[1:]:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    nama_pemeriksaan = cols[0].get_text(strip=True)
                    hasil = cols[2].get_text(strip=True)
                    if nama_pemeriksaan and hasil and hasil not in ["-", ""]:
                        results.append(f"{nama_pemeriksaan}: {hasil}")

            if results:
                return ", ".join(results[:15])  # batasi maksimal 15 item
            else:
                return "Tidak dilakukan"

        except Exception as e:
            self.log(1, f"  ⚠️ Gagal ekstrak penunjang: {e}")
            return "Tidak dilakukan"

    def _run_tab1_thread(self):
        self.log(1, "🔄 Menghubungkan ke browser...")
        driver = self.get_driver()
        if not driver:
            self.root.after(0, lambda: self.btn_start_t1.config(state="normal"))
            self.root.after(0, lambda: self.btn_stop_t1.config(state="disabled"))
            return
        
        driver.get(URL_E_PUSKESMAS)
        
        self.rem_tangan_popup(1, "Silakan login manual, pilih poli & tanggal, pastikan halaman daftar pasien (status Sudah Diperiksa) siap.\n\nKlik OK setelah siap.")
        
        self.log(1, "Mengambil data...")

        all_data = []
        page = 1

        while not self.stop_flag:
            self.log(1, f"📄 Memproses Halaman {page}...")
            time.sleep(2)
            
            rows = driver.find_elements(By.CSS_SELECTOR, "table.datatable tbody tr.success")
            self.log(1, f"🔍 Ditemukan {len(rows)} pasien.")

            if not rows:
                break

            for idx in range(len(rows)):
                if self.stop_flag: break
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "table.datatable tbody tr.success")
                    row = rows[idx]
                    
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
                    time.sleep(0.3)
                    ActionChains(driver).double_click(row).perform()

                    WebDriverWait(driver, 12).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table#table_data_anamnesa"))
                    )
                    time.sleep(1.5)

                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')

                    json_data = None
                    try:
                        match = re.search(r'const modelForPelayanan = ({.*?});', html, re.DOTALL)
                        if match:
                            json_data = json.loads(match.group(1))
                    except:
                        pass

                    record = {
                        'nama_dokter': 'AWAS_KOSONG', 'no_rekam_medis': 'AWAS_KOSONG',
                        'sumber_data': 'Rawat Jalan', 'tanggal_pelayanan': 'AWAS_KOSONG',
                        'inisial_pasien': 'AWAS_KOSONG', 'jenis_kelamin': 'AWAS_KOSONG',
                        'kategori_pasien': 'Dewasa', 'berat_badan': 'AWAS_KOSONG',
                        'tinggi_badan': 'AWAS_KOSONG', 'anamnesis': 'AWAS_KOSONG',
                        'fisik': 'AWAS_KOSONG', 'penunjang': 'Tidak dilakukan',
                        'diagnosis': 'AWAS_KOSONG', 'tata_laksana_farmako': 'AWAS_KOSONG',
                        'tata_laksana_nonfarmako': 'Kontrol dan konsultasi',
                        'monitoring': 'Keluhan dan kondisi umum',
                        'status_rujukan': 'Tidak rujuk', 'keterangan_CKG': 'AWAS_KOSONG'
                    }

                    # JSON Parsing (tetap seperti asli)
                    if json_data:
                        pendaftaran = json_data.get('pendaftaran', {})
                        pasien = pendaftaran.get('pasien', {})
                        record['no_rekam_medis'] = pasien.get('id', 'AWAS_KOSONG')
                        raw_tgl = pendaftaran.get('tanggal', '')
                        if raw_tgl: 
                            record['tanggal_pelayanan'] = raw_tgl.split()[0].replace('-', '/')
                        nama = pasien.get('nama', '')
                        if nama: 
                            record['inisial_pasien'] = nama[:3].upper()
                        record['jenis_kelamin'] = pasien.get('jenis_kelamin', 'AWAS_KOSONG')
                        umur = pendaftaran.get('umur_tahun', 30)
                        record['kategori_pasien'] = 'Bayi-Anak' if umur < 18 else ('Lansia' if umur > 60 else 'Dewasa')
                    record['berat_badan'], record['tinggi_badan'] = self.ekstrak_berat_tinggi(soup)
                    record['fisik'] = self.ekstrak_fisik(soup)
                    record['penunjang'] = self.ekstrak_penunjang(soup)
                    record['keterangan_CKG'] = self.ekstrak_ckg(soup)
                    doc_cell = soup.select_one("table#table_data_diagnosa tbody tr td:nth-child(3)")
                    if doc_cell: 
                        record['nama_dokter'] = doc_cell.get_text(strip=True)

                    keluhan = soup.select_one("table#table_data_anamnesa tbody tr td:nth-child(5)")
                    kel_tambah = soup.select_one("table#table_data_anamnesa tbody tr td:nth-child(6)")
                    if keluhan:
                        k_text = keluhan.get_text(strip=True)
                        kt_text = kel_tambah.get_text(strip=True) if kel_tambah else ""
                        record['anamnesis'] = f"{k_text} | {kt_text}" if kt_text else k_text

                    diag_rows = soup.select("table#table_data_diagnosa tbody tr")
                    diags = [r.find_all('td')[5].get_text(strip=True) for r in diag_rows if len(r.find_all('td')) >= 6]
                    if diags: 
                        record['diagnosis'] = " | ".join(diags)
                        
                    res_td = soup.select_one("table#table_data_resep tbody tr td:last-child")
                    if res_td:
                        items = []
                        for strong in res_td.find_all("strong"):
                            # Extract name and strip quantity in parentheses
                            name = strong.get_text(strip=True).split('(')[0].strip()
                            
                            # Traverse siblings for dosage, ignoring metadata labels
                            next_node = strong.next_sibling
                            dosage = ""
                            while next_node and next_node.name != 'strong':
                                import bs4 # Pastikan bs4.NavigableString dikenali
                                if isinstance(next_node, bs4.NavigableString):
                                    text = next_node.strip()
                                    # Filter kata-kata boilerplate bawaan web
                                    if text and "Jumlah Permintaan" not in text and "Keterangan" not in text:
                                        dosage = text.replace("|", "").strip()
                                        if dosage: break
                                next_node = next_node.next_sibling
                            
                            # Gabungkan nama obat dan dosis (contoh: "Paracetamol 500mg")
                            items.append(f"{name} {dosage}".strip())
                        
                        # Output akhir jadi rapi dengan koma
                        record['tata_laksana_farmako'] = ", ".join(items)

                    self.log(1, f"  📥 Sukses: {record['nama_dokter']} - {record['inisial_pasien']}")
                    all_data.append(record)

                    # Simpan halaman saat ini
                    current_page = page

                    # Kembali
                    try:
                        btn_back = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Lihat Semua')]")))
                        btn_back.click()
                    except:
                        driver.back()
                    time.sleep(1.5)

                    # Navigasi balik ke halaman yang benar
                    self.log(1, f"  🔄 Kembali ke halaman {current_page}...")
                    if current_page > 1:
                        self._navigate_to_page(driver, current_page)
                        time.sleep(1)
                except Exception as ex:
                    self.log(1, f"  ❌ Error pasien {idx+1}: {ex}")
                    try: driver.back()
                    except: pass
            # === LOGIKA PERPINDAHAN HALAMAN (PAGINATION) BADAK ===
            try:
                next_page_num = page + 1
                if self._navigate_to_page(driver, next_page_num):
                    page += 1
                    self.log(1, f"Pindah ke halaman {page}")
                else:
                    self.log(1, f"Halaman {page} adalah halaman terakhir.")
                    break
                
            except Exception as e_page:
                # Jika tombol halaman berikutnya gak ketemu, artinya kita sudah mentok di halaman terakhir!
                self.log(1, f"🏁 [INFO] Tidak bisa pindah ke halaman {page + 1}. {e_page} Kemungkinan sudah mencapai halaman terakhir atau tombol habis.")
                break # Keluar dari loop maraton karena halaman sudah habis!
        # Save CSV (tetap sama seperti asli)
        if all_data:
            if all_data:
                tgl_pelayanan = all_data[0].get('tanggal_pelayanan', '')
                if tgl_pelayanan and tgl_pelayanan != "AWAS_KOSONG":
                # Ambil tanggal pertama
                    file_tgl = tgl_pelayanan.replace('/', '').replace('-', '')[:8]  # contoh: 200625
                else:
                    file_tgl = datetime.now().strftime("%d%m%y")
        
                out_file = os.path.join(self.t1_output_dir.get(), f"data_ukp_{file_tgl}.csv")
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            
            fieldnames = [k for k in record.keys()]
            with open(out_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(all_data)
            self.log(1, f"💾 Sukses menyimpan {len(all_data)} data!")

        self.root.after(0, lambda: self.btn_start_t1.config(state="normal"))
        self.root.after(0, lambda: self.btn_stop_t1.config(state="disabled"))

    # ============================================================
    # TAB 2 LAYOUT & LOGIC (ENRICH ANAMNESIS VIA COPILOT)
    # ============================================================
    def setup_tab2(self):
        f_config = ttk.LabelFrame(self.tab2, text=" Konfigurasi AI Copilot Paragraf Rekam Medis ", padding=10)
        f_config.pack(fill="x", pady=5)
        
        ttk.Label(f_config, text="File Data Mentah (CSV):").grid(row=0, column=0, sticky="w", pady=5)
        self.t2_input_csv = tk.StringVar()
        ttk.Entry(f_config, textvariable=self.t2_input_csv, width=55).grid(row=0, column=1, padx=5)
        ttk.Button(f_config, text="Pilih", command=lambda: self.t2_input_csv.set(filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")]))).grid(row=0, column=2)
        
        ttk.Label(f_config, text="File Output Hasil (CSV):").grid(row=1, column=0, sticky="w", pady=5)
        self.t2_output_csv = tk.StringVar()
        ttk.Entry(f_config, textvariable=self.t2_output_csv, width=55).grid(row=1, column=1, padx=5)
        ttk.Button(f_config, text="Pilih", command=lambda: self.t2_output_csv.set(filedialog.asksaveasfilename(filetypes=[("CSV Files", "*.csv")]))).grid(row=1, column=2)
        
        ttk.Label(f_config, text="System Prompt AI:").grid(row=2, column=0, sticky="nw", pady=5)
        self.txt_prompt = scrolledtext.ScrolledText(f_config, height=4, width=52, font=("Segoe UI", 9))
        self.txt_prompt.grid(row=2, column=1, columnspan=2, padx=5, pady=5)
        self.txt_prompt.insert(tk.END, SYSTEM_INSTRUCTION)
        
        f_actions = ttk.Frame(self.tab2, padding=5)
        f_actions.pack(fill="x", pady=5)
        
        self.btn_start_t2 = ttk.Button(f_actions, text="▶️ MULAI PENYUSUNAN ANAMNESIS", command=self.start_tab2_process)
        self.btn_start_t2.pack(side="left", padx=5)
        
        self.btn_stop_t2 = ttk.Button(f_actions, text="⏹️ STOP", state="disabled", command=self.stop_process)
        self.btn_stop_t2.pack(side="left", padx=5)
        
        self.log_t2 = scrolledtext.ScrolledText(self.tab2, height=15, font=("Consolas", 9))
        self.log_t2.pack(fill="both", expand=True, pady=5)

    def start_tab2_process(self):
        if not self.t2_input_csv.get() or not self.t2_output_csv.get():
            messagebox.showwarning("File Kosong", "Tentukan file input dan output terlebih dahulu!")
            return
        self.stop_flag = False
        self.btn_start_t2.config(state="disabled")
        self.btn_stop_t2.config(state="normal")
        self.active_thread = threading.Thread(target=self._run_tab2_thread)
        self.active_thread.daemon = True
        self.active_thread.start()

    def _run_tab2_thread(self):
        self.log(2, "🔄 Menghubungkan ke browser...")
        driver = self.get_driver()
        if not driver:
            self.root.after(0, lambda: self.btn_start_t2.config(state="normal"))
            return
            
        self.log(2, "🌐 Membuka Google Gemini...")
        driver.get("https://gemini.google.com") # Sesuaikan URL ke Gemini
        
        self.rem_tangan_popup(2, 
            "Pastikan Google Gemini sudah terbuka dan siap.\n"
            "Login jika perlu.\n\nKlik OK setelah halaman Gemini siap digunakan."
        )

        self.log(2, "⚡ Memulai proses enrich anamnesis via Gemini...")

        # Baca CSV
        rows = []
        try:
            with open(self.t2_input_csv.get(), mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames
                rows = list(reader)
        except Exception as e:
            self.log(2, f"❌ Gagal membaca file CSV: {e}")
            self.root.after(0, lambda: self.btn_start_t2.config(state="normal"))
            return

        sys_instruction = self.txt_prompt.get("1.0", tk.END).strip()

        for idx, row in enumerate(rows):
            if self.stop_flag:
                break

            diagnosis = row.get('diagnosis', '')
            anamnesis_ori = row.get('anamnesis', '')
            inisial = row.get('inisial_pasien', 'Unknown')
            self.log(2, f"🤖 Memproses pasien ke-{idx+1}/{len(rows)} → {inisial}")

            full_prompt = f"{sys_instruction}\nDiagnosis: {diagnosis}\nKeluhan: {anamnesis_ori}"
            try:
                # === KIRIM PROMPT (VERSI COBA IKUTI CARA TEMP.PY - BEBAS TRUSTEDHTML) ===
                self.log(2, "  ⏳ Menunggu chatbox Gemini dapat diklik...")
                
                # Gunakan selector tunggal yang terbukti berhasil di temp.py
                chatbox_selector = 'div[role="textbox"]'
                time.sleep(2.0)
                
                # Tunggu sampai element benar-benar siap berinteraksi
                text_area = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, chatbox_selector))
                )
                
                # Klik area textbox terlebih dahulu untuk memicu fokus/event listener bawaan web
                text_area.click()
                time.sleep(0.5)
                
                # JALUR AMAN: Bersihkan isi teks lama pakai simulasi keyboard (Bukan innerHTML)
                text_area.send_keys(Keys.CONTROL + "a")
                time.sleep(0.2)
                text_area.send_keys(Keys.BACKSPACE)
                time.sleep(0.3)
                
                # Gunakan send_keys biasa (seperti temp.py) agar framework mendeteksi ketikan organik
                text_area.send_keys(full_prompt)
#  Cari dan klik tombol kirim berdasarkan aria-label temuan Anda
                self.log(2, "  🚀 Mengirim prompt ke Gemini...")
                send_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send'], button[aria-label*='Kirim']")
                send_button.click()
                time.sleep(2) 
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
                # 2. Panggil fungsi di atas untuk memantau aliran teks secara real-time
                response_text = self.get_final_ai_response(driver)

                # 3. Validasi hasil akhir
                if response_text and len(response_text) > 20:
                    row['anamnesis'] = response_text
                    self.log(2, f"  ✅ Berhasil enrich anamnesis ({len(response_text)} karakter)")
                else:
                    self.log(2, "  ❌ Gagal menangkap respons yang valid dari streaming Gemini, mempertahankan teks asli.")

            except Exception as ex:
                self.log(2, f"  ❌ Error saat memproses pasien {inisial}: {ex}")

            # Simpan progress setiap baris
            try:
                with open(self.t2_output_csv.get(), mode='w', newline='', encoding='utf-8') as f_out:
                    writer = csv.DictWriter(f_out, fieldnames=fieldnames, delimiter=';', quoting=csv.QUOTE_ALL)
                    writer.writeheader()
                    writer.writerows(rows)
            except:
                pass

            time.sleep(3)

        self.log(2, f"💾 Proses Tab 2 selesai! File disimpan: {self.t2_output_csv.get()}")
        

   # ====================== TAB 3 =====================    #
    def setup_tab3(self):
        f_config = ttk.LabelFrame(self.tab3, text=" Konfigurasi Auto Input Logbook UKP ", padding=10)
        f_config.pack(fill="x", pady=5)
        
        ttk.Label(f_config, text="File CSV Lengkap:").grid(row=0, column=0, sticky="w", pady=5)
        self.t3_input_csv = tk.StringVar()
        ttk.Entry(f_config, textvariable=self.t3_input_csv, width=55).grid(row=0, column=1, padx=5)
        ttk.Button(f_config, text="Pilih", command=lambda: self.t3_input_csv.set(filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")]))).grid(row=0, column=2)

        f_actions = ttk.Frame(self.tab3, padding=5)
        f_actions.pack(fill="x", pady=5)
        
        self.btn_start_t3 = ttk.Button(f_actions, text="▶️ JALANKAN AUTO INPUT UKP", command=self.start_tab3_process)
        self.btn_start_t3.pack(side="left", padx=5)
        self.btn_stop_t3 = ttk.Button(f_actions, text="⏹️ STOP", state="disabled", command=self.stop_process)
        self.btn_stop_t3.pack(side="left", padx=5)
        
        self.log_t3 = scrolledtext.ScrolledText(self.tab3, height=22, font=("Consolas", 9))
        self.log_t3.pack(fill="both", expand=True, pady=5)

    def start_tab3_process(self):
        if not self.t3_input_csv.get():
            messagebox.showwarning("Warning", "Pilih file CSV terlebih dahulu!")
            return
        self.stop_flag = False
        self.btn_start_t3.config(state="disabled")
        self.btn_stop_t3.config(state="normal")
        threading.Thread(target=self._run_tab3_thread, daemon=True).start()

    def _run_tab3_thread(self):
        self.log(3, "🔄 Menghubungkan ke Chrome...")
        driver = self.get_driver()
        if not driver:
            self.root.after(0, lambda: self.btn_start_t3.config(state="normal"))
            return

        driver.get(URL_PKM)
        
        self.rem_tangan_popup(3, 
            "Pastikan sudah di halaman daftar UKP dan login.\n\nKlik OK setelah siap."
        )

        self.log(3, "⚡ Memulai Auto Input UKP...")

        rows = []
        try:
            with open(self.t3_input_csv.get(), mode='r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f, delimiter=';'))
        except Exception as e:
            self.log(3, f"❌ Gagal baca CSV: {e}")
            self.root.after(0, lambda: self.btn_start_t3.config(state="normal"))
            return

        for idx, row in enumerate(rows):
            if self.stop_flag:
                break

            inisial = row.get('inisial_pasien', 'Unknown')
            self.log(3, f"🔄 Memproses data ke-{idx+1}/{len(rows)} - {inisial}")

            try:
                if not self.click_tambah_data(driver):
                    self.log(3, "  ❌ Gagal klik Tambah Data")
                    continue

                time.sleep(3)
# --- 4. TATA LAKSANA FARMAKOLOGI (Persis cek_ttx.py + Data CSV) ---
                farmako_data = row.get("tata_laksana_farmako", "").strip()
                if farmako_data:
                    try:
                        # 1. Cari Label & Checkbox via atribut 'for'
                        xpath_label = "//label[normalize-space()='Farmakoterapi']"
                        label_el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_label)))
                        
                        checkbox_id = label_el.get_attribute("for")
                        checkbox = driver.find_element(By.ID, checkbox_id)

                        # 2. Klik/Centang via JavaScript jika belum terpilih
                        if not checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", label_el)
                            time.sleep(0.5) # Jeda singkat agar input aktif

                        # 3. Cari Input Text spesifik di bawah label tersebut
                        input_xpath = f"{xpath_label}/following::input[@placeholder='Masukkan tata laksana'][1]"
                        input_field = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, input_xpath)))

                        # 4. Langsung hajar isi sesuai CSV
                        input_field.clear()
                        input_field.send_keys(farmako_data)
                    except Exception as e:
                        self.log(3, f"⚠️ Gagal Farmakoterapi: {e}")

                # --- 5. TATA LAKSANA NON-FARMAKOLOGI (Persis cek_ttx.py + Data CSV) ---
                non_farmako_data = row.get("tata_laksana_nonfarmako", "").strip()
                if non_farmako_data:
                    try:
                        # 1. Cari Label & Checkbox via atribut 'for'
                        xpath_label = "//label[normalize-space()='Non-Farmakoterapi']"
                        label_el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_label)))
                        
                        checkbox_id = label_el.get_attribute("for")
                        checkbox = driver.find_element(By.ID, checkbox_id)

                        # 2. Klik/Centang via JavaScript jika belum terpilih
                        if not checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", label_el)
                            time.sleep(0.5) # Jeda singkat agar input aktif

                        # 3. Cari Input Text spesifik di bawah label tersebut
                        input_xpath = f"{xpath_label}/following::input[@placeholder='Masukkan tata laksana'][1]"
                        input_field = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, input_xpath)))

                        # 4. Logika Cek Kosong (perlu_cek_kosong=True)
                        current_value = input_field.get_attribute("value")
                        if not current_value: # Jika benar-benar kosong
                            input_field.send_keys(non_farmako_data)
                        else: 
                            pass
                    except Exception as e:
                        self.log(3, f"⚠️ Gagal Non-Farmakoterapi: {e}")
# --- 1. JENIS KELAMIN ---
                gender_raw = row.get("jenis_kelamin", "").strip()
                gender_map = {
                    "laki-laki": "MALE", "laki_laki": "MALE", "l": "MALE",
                    "perempuan": "FEMALE", "p": "FEMALE"
                }
                target_gender_id = gender_map.get(gender_raw.lower())
                
                if target_gender_id:
                    try:
                        gender_element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.ID, target_gender_id))
                        )
                        driver.execute_script("arguments[0].click();", gender_element)
                        time.sleep(0.2)
                    except Exception as e:
                        self.log(3, f"⚠️ Gagal klik kelamin: {e}")

                # --- 2. STATUS RUJUKAN ---
                rujukan_raw = row.get("status_rujukan", "").strip().lower()
                target_rujukan_id = None
                
                if "tidak" in rujukan_raw or "bukan" in rujukan_raw or rujukan_raw == "false":
                    target_rujukan_id = "false"
                elif "rujuk" in rujukan_raw or rujukan_raw == "true":
                    target_rujukan_id = "true"

                if target_rujukan_id:
                    try:
                        rujukan_element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.ID, target_rujukan_id))
                        )
                        driver.execute_script("arguments[0].click();", rujukan_element)
                        time.sleep(0.2)
                    except Exception as e:
                        self.log(3, f"⚠️ Gagal klik rujukan: {e}")
              
                self.select_dropdown_by_label(driver, "Jenis Tindakan", "Medik")
                self.fill_text_by_placeholder(driver, "Masukkan no. Rekam Medis", row.get('no_rekam_medis', ''))
                self.select_dropdown_by_label(driver, "Sumber Data", "Rawat Jalan")
                self.fill_text_by_placeholder(driver, "Contoh: Agus Surya Dana 50 tahun, ditulis ASD", row.get('inisial_pasien', ''))
                self.select_dropdown_by_label(driver, "Kategori pasien", row.get('kategori_pasien', 'Dewasa'))
                self.select_dropdown_by_label(driver, "Kategori kasus", "Non-Covid")
                self.fill_text_by_placeholder(driver, "Cth: 45", row.get('berat_badan', ''))
                self.fill_text_by_placeholder(driver, "Cth: 158", row.get('tinggi_badan', ''))
                self.fill_textarea_by_contains(driver, "keluhan utama", row.get('anamnesis', ''))
                self.fill_textarea_by_contains(driver, "kondisi umum", row.get('fisik', ''))
                self.fill_textarea_by_contains(driver, "hasil Lab", row.get('penunjang', 'Tidak dilakukan'))
                self.fill_textarea_by_contains(driver, "monitoring", 'Perkembangan kesehatan, kondisi umum, dan keluhan')
              
            # === POPUP MANUAL SUBMIT ===
            except:
                self.log(3, "Ada masalah")
            self.log(3, "\n" + "="*70)
            self.log(3, "⏸️  FORM SUDAH TERISI - SILAKAN CEK & SUBMIT")
            self.log(3, "="*70)
            diagnosis = row.get('diagnosis', '')
            messagebox.showinfo("Siap Submit", 
                f"Data ke-{idx+1} ({inisial}) sudah terisi otomatis.\n\n"
                "Silakan:\n"
                "• Cek semua isian\n"
                "• Pilih Diagnosis & Diagnosis Banding\n\n"
                f" Dx: {diagnosis}\n\n"
                "• Klik 'Kirim Data' atau 'Simpan Sebagai Draft'\n\n"
                "Tekan OK setelah berhasil submit.")

            # Tunggu user submit, lalu otomatis buka form baru
            time.sleep(2)

        self.log(3, "🏁 Semua data telah diproses.")
        self.root.after(0, lambda: self.btn_start_t3.config(state="normal"))
        self.root.after(0, lambda: self.btn_stop_t3.config(state="disabled"))
        
    def stop_process(self):
        self.stop_flag = True
        self.log(1, "⏹️ Proses dihentikan manual.")
        self.log(2, "⏹️ Proses dihentikan manual.")
        self.log(3, "⏹️ Proses dihentikan manual.")

if __name__ == "__main__":
    root = tk.Tk()
    app = UKPLauncher(root)
    root.mainloop()