"""
============================================================================
 ASISTEN OTOMATISASI LOGBOOK INTERNSIP - UKP  (v2.3)
============================================================================
Perubahan besar dari versi sebelumnya:

1. DIAGNOSIS & DIAGNOSIS BANDING SEKARANG BISA TERISI OTOMATIS
   Field ini adalah kombobox pencarian custom (klik -> muncul input
   'search' -> ketik -> klik hasil). Sebelumnya tidak pernah dicoba diisi
   sama sekali oleh kode lama. Lihat fill_diagnosis_multiselect().

2. FIX BUG "TIBA-TIBA KEMBALI KE HALAMAN UTAMA"
   Kode lama mencari tombol dropdown dengan XPath
   `//label[...]/following::button[1]` yang TIDAK dibatasi ruang lingkupnya
   -> kalau tombol yang dimaksud tidak ketemu tepat setelah label, Selenium
   bisa salah klik tombol lain yang letaknya jauh di bawah, termasuk
   kemungkinan tombol 'Kirim Data'. Sekarang pencarian tombol DIBATASI
   hanya di dalam wrapper <div> milik field itu sendiri
   (lihat _field_container()).

3. FIX BUG TANGGAL TIDAK PERNAH TERISI
   ID HeadlessUI (`headlessui-popover-button-v-1-5`) di-hardcode padahal ID
   itu berubah setiap render halaman. Sekarang tombol tanggal dicari
   berdasarkan LABEL "Tanggal pelayanan", bukan ID yang berubah-ubah.

4. SEMUA PENGISIAN TEKS SEKARANG PAKAI JS VALUE-SETTER
   Bukan send_keys() lagi. Ini menghindari risiko karakter newline yang
   tersimpan di CSV ikut terkirim sebagai tombol Enter (yang di beberapa
   form bisa memicu submit tidak sengaja), dan jauh lebih cepat & stabil
   untuk aplikasi Vue/Nuxt seperti ini.

5. VERIFIKASI HALAMAN
   Setelah proses isi form, script mengecek apakah kita MASIH di form
   'Tambah data UKP'. Kalau ternyata sudah pindah halaman (misal sesi
   login habis), proses dihentikan dan diberi tahu jelas -> tidak lagi
   "diam-diam gagal tapi dianggap sukses".

6. OPSI AUTO-SUBMIT (opsional, default MATI)
   Kalau dicentang, setelah semua field (termasuk diagnosis) terisi,
   script otomatis klik 'Kirim Data' tanpa perlu klik OK manual per baris.
   Defaultnya tetap manual (lebih aman untuk data resmi Kemenkes).

7. TAMPILAN DIRAPIKAN & watermark lama dihapus.

CATATAN PENTING:
- Ini mengotomasi akun & sesi login ANDA SENDIRI di logbook resmi.
  Tetap SELALU cek ulang data sebelum 'Kirim Data' final, terutama untuk
  data rekam medis resmi.
- Sesuaikan CHROME_PATH di bawah kalau lokasi Chrome Anda berbeda.
============================================================================
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import subprocess
import os
import time
import json
import csv
import re
import bs4
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException,
    StaleElementReferenceException, ElementClickInterceptedException
)
from bs4 import BeautifulSoup

# ============================================================
# KONFIGURASI
# ============================================================
DEBUG_PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL_PKM = "https://internsip-logbook.kemkes.go.id/peserta/ukpPkm"
URL_PKM_ADD = "https://internsip-logbook.kemkes.go.id/peserta/ukpAdd?typeStase=PUSKESMAS"
URL_E_PUSKESMAS = "http://172.16.10.99/j-care/"

APP_TITLE = "Asisten Otomatisasi Logbook Internsip - UKP"
APP_VERSION = "v3.0"

# Palet warna senada dengan warna resmi web Kemenkes (teal)
COLOR_BG = "#F4F7F8"
COLOR_HEADER_BG = "#0F5E58"
COLOR_HEADER_FG = "#FFFFFF"
COLOR_ACCENT = "#16B3AC"
COLOR_ACCENT_DARK = "#0D857F"
COLOR_DANGER = "#E4572E"
COLOR_TEXT = "#1A2B2A"
COLOR_LOG_BG = "#0B1F1E"
COLOR_LOG_FG = "#8CF1E8"

SYSTEM_INSTRUCTION = """Susun anamnesis rekam medis dari data yang saya berikan. Output hanya 1 paragraf ringkas PLAIN TEXT berisi keluhan utama, onset, gambaran keluhan, saat apa berkurang, saat apa bertambah, riwayat alergi, pengobatan, serta faktor risiko relevan jika ada terkait penyakit atau komplikasinya. Untuk penyakit akut, Riwayat Penyakit Dahulu dianggap (-) kecuali terdapat komorbid kronis yang diberikan dalam data sampaikan dengan BAHASA awam. Boleh karang sesuai teori karena semua pasien sesuai teori. JANGAN ada bold, JANGAN beri aku bertanyaan atau saran karena aku tidak konsultasi. JANGAN menulis ulang diagnosis. JANGAN pakai kata lapor atau turunannya, pakai mengeluh. Aku butuh kamu agar catatanku lengkap saat waktuku mengetik terbatas."""


class UKPLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.root.geometry("980x780")
        self.root.minsize(880, 640)
        self.root.configure(bg=COLOR_BG)

        self.stop_flag = False
        self.active_thread = None

        self._setup_style()
        self.setup_ui()

    # ============================================================
    # TAMPILAN / STYLE
    # ============================================================
    def _setup_style(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            pass

        self.style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=("Segoe UI", 10))
        self.style.configure("TFrame", background=COLOR_BG)
        self.style.configure("TLabelframe", background=COLOR_BG, bordercolor=COLOR_ACCENT)
        self.style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_ACCENT_DARK,
                              font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        self.style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[16, 8],
                              background="#DCEDEC", foreground=COLOR_TEXT)
        self.style.map("TNotebook.Tab",
                        background=[("selected", COLOR_ACCENT)],
                        foreground=[("selected", "white")])

        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"),
                              foreground="white", background=COLOR_ACCENT, padding=8)
        self.style.map("Accent.TButton",
                        background=[("active", COLOR_ACCENT_DARK), ("disabled", "#B7D9D6")])

        self.style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"),
                              foreground="white", background=COLOR_DANGER, padding=8)
        self.style.map("Danger.TButton",
                        background=[("active", "#B7431F"), ("disabled", "#E9C3B4")])

        self.style.configure("TEntry", padding=4)
        self.style.configure("TCheckbutton", background=COLOR_BG)

    def setup_ui(self):
        header = tk.Frame(self.root, bg=COLOR_HEADER_BG, height=64)
        header.pack(fill="x", side="top")
        tk.Label(header, text="\U0001FA7A  Asisten Otomatisasi Logbook Internsip",
                 bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=18, pady=10)
        tk.Label(header, text=APP_VERSION, bg=COLOR_HEADER_BG, fg="#BFE9E5",
                 font=("Segoe UI", 10)).pack(side="right", padx=18)

        top_frame = ttk.LabelFrame(self.root, text=" \u2699\ufe0f Kontrol Chrome Debugging Mode ", padding=10)
        top_frame.pack(fill="x", padx=15, pady=10)
        ttk.Label(top_frame, text="Buka Chrome khusus untuk otomatisasi (profil terpisah):").pack(side="left", padx=5)
        ttk.Button(top_frame, text="\U0001F680 Buka Chrome Debugger", style="Accent.TButton",
                   command=self.start_chrome_debug).pack(side="right", padx=5)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=5)

        self.tab1 = ttk.Frame(self.notebook, padding=10)
        self.tab2 = ttk.Frame(self.notebook, padding=10)
        self.tab3 = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab1, text=" \U0001F4E5  1. Ambil Data Pasien ")
        self.notebook.add(self.tab2, text=" \U0001F916  2. Perkaya Anamnesis (AI) ")
        self.notebook.add(self.tab3, text=" \U0001F4E4  3. Auto Input UKP ")

        self.setup_tab1()
        self.setup_tab2()
        self.setup_tab3()

        self.status_var = tk.StringVar(value="\U0001F7E2 Siap")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bg="#E7F3F2",
                               fg=COLOR_TEXT, anchor="w", padx=10, pady=6, font=("Segoe UI", 9))
        status_bar.pack(fill="x", side="bottom")

    def start_chrome_debug(self):
        cmd = f'"{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT} --user-data-dir="C:\\selenium\\AutomationProfile"'
        try:
            subprocess.Popen(cmd, shell=True)
            self.set_status("\u2705 Chrome Debugger dibuka.")
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
        self.log(tab_num, "\U0001F6D1 REM TANGAN AKTIF - Menunggu user...")
        messagebox.showinfo(f"Tab {tab_num} - Siapkan Halaman", message)

    def _navigate_to_page(self, driver, target_page):
        self.log(1, f"Navigasi ke halaman {target_page}...")
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(0.3)
        try:
            page_btn = driver.find_element(By.XPATH, f"//li[contains(@class, 'clickable')]/span[text()='{target_page}'] | //a[text()='{target_page}']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", page_btn)
            time.sleep(0.5)
            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.CSS_SELECTOR, ".pagination li.active span").text == str(target_page)
            )
            self.log(1, f"Berhasil ke halaman {target_page} (langsung)")
            return True
        except Exception:
            pass

        if target_page > 7:
            triggers = list(range(7, target_page, 2))
            for trigger in triggers:
                try:
                    trigger_btn = driver.find_element(By.XPATH, f"//li[contains(@class, 'clickable')]/span[text()='{trigger}'] | //a[text()='{trigger}']")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger_btn)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", trigger_btn)
                    self.log(1, f"   Trigger {trigger}")
                    time.sleep(1.0)
                except Exception:
                    self.log(1, f"   Trigger {trigger} gagal")
                    return False
            try:
                page_btn = driver.find_element(By.XPATH, f"//li[contains(@class, 'clickable')]/span[text()='{target_page}'] | //a[text()='{target_page}']")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_btn)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", page_btn)
                time.sleep(0.6)
                return True
            except Exception:
                return False
        return False

    # ============================================================
    # HELPER BARU - PENGISIAN FORM YANG LEBIH AMAN (JS value setter)
    # ============================================================
    def _js_set_value(self, driver, element, value):
        """
        Isi input/textarea via native value-setter lalu trigger event
        'input' & 'change'. Ini menggantikan send_keys() supaya:
        - Tidak ada risiko newline di teks CSV terbaca sebagai tombol
          Enter (yang bisa memicu submit form tidak sengaja).
        - Terdeteksi dengan benar oleh Vue (form ini pakai Nuxt/Vue,
          v-model mendengarkan event 'input').
        - Jauh lebih cepat daripada mengetik karakter satu-satu.
        """
        script = """
            const el = arguments[0];
            const val = arguments[1];
            const tag = el.tagName.toLowerCase();
            const proto = (tag === 'textarea') ? window.HTMLTextAreaElement.prototype
                                                : window.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        """
        driver.execute_script(script, element, value)

    def _clean_text(self, text, allow_newline=False):
        if text is None:
            return ""
        text = str(text)
        if text.strip() == "AWAS_KOSONG":
            return ""
        if allow_newline:
            return text.strip()
        return re.sub(r'[\r\n]+', ' ', text).strip()

    def fill_text_by_placeholder(self, driver, placeholder, text):
        try:
            elem = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//input[@placeholder='{placeholder}']"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            self._js_set_value(driver, elem, self._clean_text(text, allow_newline=False))
            time.sleep(0.25)
            return True
        except Exception as e:
            self.log(3, f"  \u26a0\ufe0f Gagal isi field '{placeholder}': {e}")
            return False

    def fill_text_by_placeholder_order(self, driver, placeholder, text, order=1):
        try:
            elems = WebDriverWait(driver, 10).until(
                lambda d: d.find_elements(By.XPATH, f"//input[@placeholder='{placeholder}']")
            )
            if len(elems) >= order:
                elem = elems[order - 1]
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                self._js_set_value(driver, elem, self._clean_text(text, allow_newline=False))
                time.sleep(0.25)
                return True
        except Exception as e:
            self.log(3, f"  \u26a0\ufe0f Gagal isi field urutan-{order} '{placeholder}': {e}")
        return False

    def fill_textarea_by_contains(self, driver, partial_placeholder, text):
        try:
            elem = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//textarea[contains(@placeholder, '{partial_placeholder}')]"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            self._js_set_value(driver, elem, self._clean_text(text, allow_newline=True))
            time.sleep(0.25)
            return True
        except Exception as e:
            self.log(3, f"  \u26a0\ufe0f Gagal isi textarea '{partial_placeholder}': {e}")
            return False

    def _field_container(self, driver, label_text):
        """
        Cari wrapper <div> milik SATU field spesifik berdasarkan teks
        label-nya. Ini kunci perbaikan bug 'tiba-tiba kembali ke halaman
        utama': kode lama mencari tombol dengan `following::button[1]`
        TANPA batas ruang lingkup, jadi kalau tombol yang benar tidak
        ketemu persis setelah label, Selenium bisa salah pilih tombol
        lain di form (termasuk mungkin tombol submit di bagian bawah).
        Sekarang pencarian tombol dibatasi HANYA di dalam wrapper field
        ini saja.
        """
        xpath = (
            f"//label[contains(normalize-space(.), '{label_text}')]"
            f"/ancestor::div[contains(@class,'my-[16px]') or contains(@class,'my-4')][1]"
        )
        return WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, xpath)))

    def select_dropdown_by_label(self, driver, label, value):
        """Pilih opsi dropdown (Listbox) yang tombolnya dicari HANYA di
        dalam wrapper field terkait (lihat _field_container)."""
        try:
            container = self._field_container(driver, label)
            btn = container.find_element(By.XPATH, ".//button")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.5)
            option = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//li//span[normalize-space(text())='{value}']"))
            )
            driver.execute_script("arguments[0].click();", option)
            time.sleep(0.3)
            return True
        except Exception as e:
            self.log(3, f"  \u26a0\ufe0f Gagal pilih dropdown '{label}' -> '{value}': {e}")
            return False

    def _add_form_ready(self, driver):
        """Deteksi form Tambah Data UKP tanpa bergantung pada satu tag/heading saja."""
        try:
            if "ukpadd" in (driver.current_url or "").lower():
                return True
        except Exception:
            pass

        checks = [
            (By.XPATH, "//p[contains(normalize-space(.), 'Tambah data UKP')]"),
            (By.XPATH, "//*[self::h1 or self::h2 or self::h3][contains(normalize-space(.), 'Tambah data UKP')]"),
            (By.XPATH, "//input[@placeholder='Masukkan no. Rekam Medis']"),
            (By.XPATH, "//textarea[contains(@placeholder, 'keluhan utama')]"),
        ]
        for by, selector in checks:
            try:
                elems = driver.find_elements(by, selector)
                if any(el.is_displayed() for el in elems):
                    return True
            except Exception:
                pass
        return False

    def click_tambah_data(self, driver):
        """Buka form Tambah Data UKP secara robust.

        v2.5:
        - tidak lagi mengasumsikan teks berada di <span> atau <a>;
        - mencari button/a/role=button yang TERLIHAT berdasarkan innerText;
        - mencoba ActionChains, click biasa, dan JavaScript click;
        - memverifikasi perpindahan ke /ukpAdd;
        - bila tombol berubah struktur, fallback langsung ke URL form resmi.
        """
        try:
            # Kalau ternyata sudah berada di form Tambah Data, tidak perlu klik lagi.
            if self._add_form_ready(driver):
                self.log(3, "  ✅ Form 'Tambah Data UKP' sudah terbuka.")
                return True

            # Tunggu halaman daftar selesai dimuat.
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
                )
            except Exception:
                pass

            def find_visible_add_button(d):
                # Pertama gunakan XPath yang generik terhadap tag aktual.
                xpaths = [
                    "//button[contains(normalize-space(.), 'Tambah Data UKP')]",
                    "//a[contains(normalize-space(.), 'Tambah Data UKP')]",
                    "//*[@role='button' and contains(normalize-space(.), 'Tambah Data UKP')]",
                    "//button[contains(normalize-space(.), 'Tambah Data')]",
                    "//a[contains(normalize-space(.), 'Tambah Data')]",
                ]
                for xp in xpaths:
                    try:
                        for el in d.find_elements(By.XPATH, xp):
                            if el.is_displayed() and el.is_enabled():
                                return el
                    except Exception:
                        pass

                # Fallback DOM: cocokkan innerText, berguna bila ada icon/child div/span.
                try:
                    return d.execute_script(
                        """
                        const els = [...document.querySelectorAll('button, a, [role="button"]')];
                        const norm = s => (s || '').replace(/\\s+/g,' ').trim().toLowerCase();
                        return els.find(el => {
                            const r = el.getBoundingClientRect();
                            const st = getComputedStyle(el);
                            const visible = el.offsetParent !== null && r.width > 0 && r.height > 0 &&
                                            st.display !== 'none' && st.visibility !== 'hidden';
                            const t = norm(el.innerText || el.textContent);
                            return visible && (t.includes('tambah data ukp') || t === 'tambah data');
                        }) || null;
                        """
                    )
                except Exception:
                    return None

            btn = WebDriverWait(driver, 10).until(find_visible_add_button)
            try:
                self.log(3, f"  🔎 Tombol Tambah Data ditemukan: '{btn.text.strip()}'")
            except Exception:
                self.log(3, "  🔎 Tombol Tambah Data ditemukan.")

            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", btn
            )
            time.sleep(0.2)

            methods = []
            methods.append(lambda: ActionChains(driver).move_to_element(btn).pause(0.1).click().perform())
            methods.append(lambda: btn.click())
            methods.append(lambda: driver.execute_script("arguments[0].click();", btn))

            for n, click_method in enumerate(methods, 1):
                try:
                    click_method()
                except Exception as e:
                    self.log(3, f"  ↪️ Metode klik {n} gagal: {type(e).__name__}")

                # Setelah setiap metode, tunggu form benar-benar terbuka.
                end_t = time.time() + 4.0
                while time.time() < end_t:
                    if self._add_form_ready(driver):
                        self.log(3, "  ✅ Form 'Tambah Data UKP' berhasil dibuka.")
                        time.sleep(0.7)
                        return True
                    time.sleep(0.15)

            # Struktur tombol/SPA bisa berubah. URL form ini sudah diketahui dari situs.
            self.log(3, "  ↪️ Klik tombol belum membuka form; mencoba URL Tambah Data secara langsung...")
            driver.get(URL_PKM_ADD)
            try:
                WebDriverWait(driver, 12).until(lambda d: self._add_form_ready(d))
                self.log(3, "  ✅ Form 'Tambah Data UKP' dibuka melalui URL langsung.")
                time.sleep(0.7)
                return True
            except TimeoutException:
                raise TimeoutException(
                    f"URL langsung juga tidak membuka form. URL saat ini: {driver.current_url}"
                )

        except Exception as e:
            try:
                current_url = driver.current_url
            except Exception:
                current_url = "(tidak diketahui)"
            self.log(
                3,
                f"  ⚠️ Gagal membuka form 'Tambah Data': {type(e).__name__}: {e} | URL: {current_url}"
            )
            return False

    def is_on_add_form(self, driver):
        """Cek apakah kita masih berada di form Tambah Data UKP."""
        return self._add_form_ready(driver)

    # ------------------------------------------------------------------
    # DIAGNOSIS / DIAGNOSIS BANDING - kombobox pencarian custom (v2.9 - loop multi diagnosis)
    # ------------------------------------------------------------------
    def _normalize_diagnosis_text(self, text):
        """Normalisasi ringan untuk pencocokan nama diagnosis."""
        text = "" if text is None else str(text)
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"\s+", " ", text).strip().lower()
        return text

    def _strip_icd_prefix(self, text):
        """
        Buang awalan kode ICD bila dropdown menampilkan format seperti:
        'Q38.1 Ankyloglossia' atau 'Q38.1 - Ankyloglossia'.
        """
        text = self._normalize_diagnosis_text(text)
        return re.sub(r"^[a-z]\d{2}(?:\.\d+)?\s*[-:]?\s*", "", text, flags=re.I).strip()

    def _close_diagnosis_panel(self, driver):
        """Tutup panel diagnosis yang masih terbuka sebelum pindah item/field."""
        try:
            active = driver.switch_to.active_element
            if active is not None and active.get_attribute("placeholder") == "search":
                active.send_keys(Keys.ESCAPE)
                time.sleep(0.15)
        except Exception:
            pass

        try:
            driver.execute_script("document.body.click();")
        except Exception:
            pass
        time.sleep(0.20)

    def _open_diagnosis_dropdown(self, driver, css_class):
        """Buka dropdown Diagnosis/Diagnosis Banding yang diminta secara spesifik.

        Penting untuk multi-diagnosis: fungsi ini TIDAK lagi memakai sembarang
        input search yang kebetulan masih terlihat dari dropdown sebelumnya.
        Setiap iterasi selalu menargetkan container ``css_class`` yang benar.
        """

        def get_visible_trigger(d):
            elems = d.find_elements(By.CSS_SELECTOR, f"div.{css_class}")
            visible = []
            for el in elems:
                try:
                    if el.is_displayed() and el.size.get('width', 0) > 0 and el.size.get('height', 0) > 0:
                        visible.append(el)
                except Exception:
                    continue
            return visible[-1] if visible else False

        trigger = WebDriverWait(driver, 8).until(get_visible_trigger)
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", trigger)
        time.sleep(0.20)

        def visible_search_for_this_field():
            # 1) Search input sebagai child dari container field.
            try:
                inputs = trigger.find_elements(By.CSS_SELECTOR, "input[placeholder='search']")
                for el in reversed(inputs):
                    try:
                        if el.is_displayed() and driver.execute_script(
                            "return arguments[0].offsetParent !== null;", el
                        ):
                            return el
                    except Exception:
                        continue
            except Exception:
                pass

            # 2) Fallback bila panel di-teleport/portal ke luar container.
            # Caller selalu menutup panel lama sebelum membuka field ini, jadi
            # input search visible terakhir aman dipakai setelah klik trigger.
            try:
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[placeholder='search']")
                visible = []
                for el in inputs:
                    try:
                        if el.is_displayed() and driver.execute_script(
                            "return arguments[0].offsetParent !== null;", el
                        ):
                            visible.append(el)
                    except Exception:
                        continue
                return visible[-1] if visible else None
            except Exception:
                return None

        # Bila panel field ini memang sudah terbuka, pakai langsung.
        existing = visible_search_for_this_field()
        if existing is not None:
            return trigger, existing

        # Tentukan target klik. Saat belum ada pilihan biasanya ada teks
        # "Pilih diagnosis"; setelah satu diagnosis terpilih teks itu bisa hilang,
        # sehingga fallback ke wrapper flex/trigger diperlukan.
        label = None
        click_target = None
        try:
            labels = trigger.find_elements(By.XPATH, ".//div[normalize-space(.)='Pilih diagnosis']")
            labels = [x for x in labels if x.is_displayed()]
            if labels:
                label = labels[-1]
                click_target = label.find_element(By.XPATH, "./..")
        except Exception:
            pass

        if click_target is None:
            try:
                flexes = trigger.find_elements(By.CSS_SELECTOR, "div.flex.flex-wrap.relative")
                flexes = [x for x in flexes if x.is_displayed()]
                if flexes:
                    click_target = flexes[-1]
            except Exception:
                pass

        if click_target is None:
            click_target = trigger

        point_element = None
        try:
            point_element = driver.execute_script(
                """
                const el = arguments[0];
                const r = el.getBoundingClientRect();
                return document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
                """,
                click_target,
            )
        except Exception:
            pass

        candidates = []
        for el in (click_target, label, point_element, trigger):
            if el is None:
                continue
            try:
                if not any(el.id == old.id for old in candidates):
                    candidates.append(el)
            except Exception:
                candidates.append(el)

        def wait_search(seconds=1.5):
            end_t = time.time() + seconds
            while time.time() < end_t:
                found = visible_search_for_this_field()
                if found is not None:
                    return found
                time.sleep(0.08)
            return None

        last_error = None
        for el in candidates:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.08)
                ActionChains(driver).move_to_element(el).pause(0.05).click().perform()
                search_input = wait_search()
                if search_input is not None:
                    return trigger, search_input
            except Exception as e:
                last_error = e

            try:
                el.click()
                search_input = wait_search()
                if search_input is not None:
                    return trigger, search_input
            except Exception as e:
                last_error = e

        try:
            driver.execute_script(
                """
                const el = arguments[0];
                const opts = {bubbles:true, cancelable:true, view:window, button:0, buttons:1};
                try { el.dispatchEvent(new PointerEvent('pointerdown', opts)); } catch(e) {}
                el.dispatchEvent(new MouseEvent('mousedown', opts));
                try { el.dispatchEvent(new PointerEvent('pointerup', {...opts, buttons:0})); } catch(e) {}
                el.dispatchEvent(new MouseEvent('mouseup', {...opts, buttons:0}));
                el.dispatchEvent(new MouseEvent('click', {...opts, buttons:0}));
                """,
                click_target,
            )
            search_input = wait_search(1.8)
            if search_input is not None:
                return trigger, search_input
        except Exception as e:
            last_error = e

        raise TimeoutException(
            f"Dropdown '{css_class}' tidak berhasil membuka input search. "
            f"LastError={type(last_error).__name__ if last_error else 'None'}: {last_error}"
        )

    def _collect_visible_diagnosis_options(self, driver, scope=None):
        """Ambil opsi diagnosis yang benar-benar sedang terlihat."""
        selector = "div.m-1.p-1.cursor-pointer.w-full"
        candidates = []

        # Coba dari scope lebih dulu.
        if scope is not None:
            try:
                for el in scope.find_elements(By.CSS_SELECTOR, selector):
                    try:
                        if el.is_displayed() and el.text.strip():
                            candidates.append(el)
                    except StaleElementReferenceException:
                        pass
            except StaleElementReferenceException:
                pass

        # Fallback global. Ini sama dengan selector yang berhasil di Console.
        if not candidates:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if el.is_displayed() and el.text.strip():
                        candidates.append(el)
                except StaleElementReferenceException:
                    pass

        # Hilangkan duplikat berdasarkan teks sambil mempertahankan urutan.
        unique = []
        seen = set()
        for el in candidates:
            try:
                key = self._normalize_diagnosis_text(el.text)
            except StaleElementReferenceException:
                continue
            if key and key not in seen:
                seen.add(key)
                unique.append(el)
        return unique

    def _type_diagnosis_search(self, driver, search_input, query, log_label="Diagnosis"):
        """Ketik query ke search diagnosis dengan EVENT KEYBOARD asli.

        Komponen diagnosis di situs ini ternyata tidak memfilter daftar hanya dari
        perubahan value + event ``input``. Karena itu search khusus diagnosis memakai
        Selenium ``send_keys`` agar keydown/keypress/input/keyup benar-benar terjadi,
        sama seperti saat user mengetik manual.
        """
        query = self._clean_text(query, allow_newline=False)
        if not query:
            return False

        # Pastikan input terlihat, fokus, dan kosong.
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", search_input)
        WebDriverWait(driver, 5).until(lambda d: search_input.is_displayed() and search_input.is_enabled())

        try:
            search_input.click()
        except Exception:
            driver.execute_script("arguments[0].focus();", search_input)

        # Clear dengan keyboard supaya framework juga menerima event penghapusan.
        try:
            search_input.send_keys(Keys.CONTROL, "a")
            search_input.send_keys(Keys.BACKSPACE)
        except Exception:
            driver.execute_script(
                """
                const el = arguments[0];
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                setter.call(el, '');
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true, key:'Backspace'}));
                """,
                search_input,
            )

        time.sleep(0.15)

        # PENTING: gunakan send_keys, bukan hanya JS setter.
        # Ini memicu keydown/keypress/input/keyup seperti pengetikan manusia.
        search_input.send_keys(query)

        # Tambahan event untuk berjaga-jaga bila komponen mendengarkan keyup/change.
        driver.execute_script(
            """
            const el = arguments[0];
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true, key:'a'}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            """,
            search_input,
        )

        # Verifikasi nilai input benar-benar terisi.
        try:
            WebDriverWait(driver, 3).until(
                lambda d: (search_input.get_attribute('value') or '').strip().lower() == query.strip().lower()
            )
        except TimeoutException:
            actual = search_input.get_attribute('value') or ''
            self.log(3, f"  ⚠️ Search {log_label} gagal menerima teks. Value aktual: '{actual}'")
            return False

        return True

    def _pick_diagnosis_option(self, driver, scope, search_input, keyword, log_label="Diagnosis"):
        """Pilih diagnosis dengan alur keyboard sederhana sesuai perilaku manual.

        Alur v2.6:
        1. Dropdown sudah dibuka oleh _open_diagnosis_dropdown().
        2. Fokus ke input search.
        3. Isi teks dari CSV memakai send_keys().
        4. Tekan ENTER untuk menjalankan pencarian/filter komponen.
        5. Jika dropdown masih terbuka, pilih kandidat pertama dengan ARROW_DOWN + ENTER.
        6. Bila navigasi keyboard tidak menutup dropdown, fallback klik kandidat pertama.

        Catatan: versi ini SENGAJA mengambil kandidat pertama, sesuai permintaan user.
        Karena itu hasil diagnosis harus tetap dicek sebelum submit.
        """
        keyword = self._clean_text(keyword, allow_newline=False)
        if not keyword:
            return False, None

        query = self._strip_icd_prefix(keyword) or keyword

        # Pastikan input search terlihat dan fokus.
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", search_input)
        WebDriverWait(driver, 5).until(
            lambda d: search_input.is_displayed() and search_input.is_enabled()
        )

        try:
            search_input.click()
        except Exception:
            driver.execute_script("arguments[0].focus();", search_input)

        # Bersihkan isi lama dengan keyboard agar event framework tetap terpanggil.
        try:
            search_input.send_keys(Keys.CONTROL, "a")
            search_input.send_keys(Keys.BACKSPACE)
        except Exception:
            driver.execute_script(
                """
                const el = arguments[0];
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                setter.call(el, '');
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                """,
                search_input,
            )

        time.sleep(0.15)

        # Ketik teks persis dari CSV.
        search_input.send_keys(query)
        self.log(3, f"  ⌨️ Search {log_label}: {query}")
        time.sleep(0.25)

        # ENTER pertama: pada komponen ini dipakai untuk mengeksekusi pencarian/filter.
        search_input.send_keys(Keys.ENTER)
        self.log(3, f"  ↵ Enter pencarian {log_label}")
        time.sleep(0.8)

        def input_masih_terbuka():
            try:
                return search_input.is_displayed() and search_input.get_attribute('offsetParent') is not None
            except Exception:
                try:
                    return bool(driver.execute_script(
                        "return arguments[0] && arguments[0].offsetParent !== null;",
                        search_input
                    ))
                except Exception:
                    return False

        # Bisa saja ENTER pertama langsung memilih hasil pertama dan menutup dropdown.
        try:
            still_visible = driver.execute_script(
                "return arguments[0] && arguments[0].offsetParent !== null;",
                search_input
            )
        except Exception:
            still_visible = False

        if not still_visible:
            self.log(3, f"  ✅ {log_label} dipilih setelah ENTER: {keyword}")
            return True, keyword

        # Tunggu kandidat hasil pencarian muncul. Tidak perlu exact-match: ambil kandidat pertama.
        first_option = None
        first_text = None
        end_t = time.time() + 5.0
        while time.time() < end_t:
            options = self._collect_visible_diagnosis_options(driver, scope)
            if options:
                try:
                    first_option = options[0]
                    first_text = re.sub(r"\s+", " ", first_option.text).strip()
                    if first_text:
                        break
                except StaleElementReferenceException:
                    first_option = None
                    first_text = None
            time.sleep(0.15)

        if first_option is None:
            self.log(3, f"  ⚠️ Tidak ada kandidat {log_label} setelah mencari '{keyword}'.")
            return False, None

        self.log(3, f"  ➜ Kandidat pertama {log_label}: {first_text}")

        # ENTER kedua: pindah ke kandidat pertama lalu pilih dengan keyboard.
        keyboard_selected = False
        try:
            search_input.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.12)
            search_input.send_keys(Keys.ENTER)
            time.sleep(0.45)

            try:
                keyboard_selected = not bool(driver.execute_script(
                    "return arguments[0] && arguments[0].offsetParent !== null;",
                    search_input
                ))
            except Exception:
                keyboard_selected = True
        except Exception:
            keyboard_selected = False

        if keyboard_selected:
            self.log(3, f"  ✅ {log_label} dipilih (kandidat pertama): {first_text}")
            return True, first_text

        # Fallback bila custom component tidak merespons ArrowDown + Enter.
        # Tetap kandidat PERTAMA, bukan pencocokan lain.
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", first_option)
            time.sleep(0.10)
            ActionChains(driver).move_to_element(first_option).click().perform()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", first_option)
            except Exception as e:
                self.log(3, f"  ⚠️ Gagal memilih kandidat pertama {log_label}: {type(e).__name__}: {e}")
                return False, None

        time.sleep(0.40)
        self.log(3, f"  ✅ {log_label} dipilih via fallback kandidat pertama: {first_text}")
        return True, first_text

    def fill_diagnosis_multiselect(self, driver, css_class, raw_text, log_label):
        """Isi satu atau banyak Diagnosis/Diagnosis Banding secara berurutan.

        Format CSV yang didukung:
            Dx 1
            Dx 1 | Dx 2 | Dx 3
            Dx 1 ; Dx 2 ; Dx 3

        Untuk N item, dropdown dibuka ulang N kali. Jadi bila hanya ada 1 item,
        setelah item pertama terpilih fungsi langsung selesai dan form lanjut ke
        segmen berikutnya. Bila ada 2/3/... item, semuanya diproses satu per satu.
        """
        if raw_text is None:
            return True

        raw = str(raw_text).strip()
        if not raw or raw == "AWAS_KOSONG":
            return True

        # Jangan split dengan koma karena nama diagnosis ICD dapat mengandung koma.
        items = [
            self._clean_text(x, allow_newline=False)
            for x in re.split(r"\||;|\r?\n", raw)
            if str(x).strip()
        ]
        items = [x for x in items if x]
        if not items:
            return True

        self.log(3, f"  📋 {log_label}: {len(items)} item akan diproses.")
        success_count = 0

        for nomor, item in enumerate(items, 1):
            try:
                # Sangat penting pada multi-select: pastikan panel dari iterasi
                # sebelumnya benar-benar tertutup, lalu buka ulang FIELD YANG SAMA.
                self._close_diagnosis_panel(driver)
                self.log(3, f"  🔎 {log_label} {nomor}/{len(items)}: {item}")

                scope, search_input = self._open_diagnosis_dropdown(driver, css_class)
                found, chosen_text = self._pick_diagnosis_option(
                    driver, scope, search_input, item, log_label
                )

                if found:
                    success_count += 1
                    self.log(
                        3,
                        f"  ✅ {log_label} {nomor}/{len(items)} dipilih: "
                        f"{chosen_text or item}"
                    )
                else:
                    self.log(3, f"  ⚠️ {log_label} {nomor}/{len(items)} gagal dipilih: {item}")

                # Tutup panel dan beri waktu UI menyimpan chip pilihan sebelum
                # iterasi berikutnya membuka dropdown lagi.
                self._close_diagnosis_panel(driver)
                time.sleep(0.35)

            except Exception as e:
                self.log(
                    3,
                    f"  ⚠️ Gagal isi {log_label} {nomor}/{len(items)} '{item}': "
                    f"{type(e).__name__}: {e!r}"
                )
                self._close_diagnosis_panel(driver)
                time.sleep(0.30)

        if len(items) == 1:
            self.log(3, f"  ➡️ {log_label} hanya 1 item; lanjut ke segmen berikutnya.")
        else:
            self.log(3, f"  📌 {log_label} selesai: {success_count}/{len(items)} item berhasil dipilih.")

        return success_count == len(items)

    def _find_and_click_submit_button(self, driver, mode="kirim"):
        """Klik Kirim Data, tangani modal konfirmasi, lalu verifikasi submit selesai.

        Alur pada web Kemenkes saat mode kirim:
        1. Klik tombol "Kirim Data" pada form.
        2. Muncul modal "Tambah data UKP".
        3. Klik tombol "Tambah" pada modal.
        4. Tunggu sampai keluar dari halaman ukpAdd / form Tambah Data tertutup.

        Fungsi hanya mengembalikan True bila langkah terakhir benar-benar terkonfirmasi.
        Ini mencegah loop lanjut ke pasien berikutnya saat modal masih terbuka.
        """
        text = "Kirim Data" if mode == "kirim" else "Simpan Sebagai Draf"

        def find_visible_button(d, wanted_text):
            """Cari button/role=button yang terlihat dengan teks exact terlebih dahulu."""
            xpaths = [
                f"//button[normalize-space(.)='{wanted_text}']",
                f"//*[@role='button' and normalize-space(.)='{wanted_text}']",
                f"//button[contains(normalize-space(.), '{wanted_text}')]",
                f"//*[@role='button' and contains(normalize-space(.), '{wanted_text}')]",
            ]
            for xp in xpaths:
                try:
                    for el in d.find_elements(By.XPATH, xp):
                        if el.is_displayed() and el.is_enabled():
                            return el
                except Exception:
                    pass

            try:
                return d.execute_script(
                    """
                    const wanted = (arguments[0] || '').replace(/\\s+/g,' ').trim().toLowerCase();
                    const els = [...document.querySelectorAll('button, [role="button"]')];
                    const norm = s => (s || '').replace(/\\s+/g,' ').trim().toLowerCase();
                    const visible = el => {
                        const r = el.getBoundingClientRect();
                        const st = getComputedStyle(el);
                        return el.offsetParent !== null && r.width > 0 && r.height > 0 &&
                               st.display !== 'none' && st.visibility !== 'hidden' &&
                               !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                    };
                    return els.find(el => visible(el) && norm(el.innerText || el.textContent) === wanted)
                        || els.find(el => visible(el) && norm(el.innerText || el.textContent).includes(wanted))
                        || null;
                    """,
                    wanted_text,
                )
            except Exception:
                return None

        def find_confirmation_button(d):
            """Cari tombol 'Tambah' KHUSUS pada modal konfirmasi submit."""
            # Utamakan tombol yang berada di dialog/modal dengan teks konfirmasi yang kita lihat.
            modal_xpaths = [
                "//div[@role='dialog']//button[normalize-space(.)='Tambah']",
                "//*[@role='dialog']//*[@role='button' and normalize-space(.)='Tambah']",
                "//*[contains(normalize-space(.),'Apakah Anda yakin ingin menambah data UKP baru ke logbook?')]//button[normalize-space(.)='Tambah']",
            ]
            for xp in modal_xpaths:
                try:
                    for el in d.find_elements(By.XPATH, xp):
                        if el.is_displayed() and el.is_enabled():
                            return el
                except Exception:
                    pass

            # Fallback: tombol exact "Tambah" yang terlihat. BUKAN "Tambah Data UKP".
            try:
                for el in d.find_elements(By.XPATH, "//button[normalize-space(.)='Tambah']"):
                    if el.is_displayed() and el.is_enabled():
                        return el
            except Exception:
                pass

            try:
                return d.execute_script(
                    """
                    const norm = s => (s || '').replace(/\\s+/g,' ').trim().toLowerCase();
                    const els = [...document.querySelectorAll('button, [role="button"]')];
                    return els.find(el => {
                        const r = el.getBoundingClientRect();
                        const st = getComputedStyle(el);
                        const visible = el.offsetParent !== null && r.width > 0 && r.height > 0 &&
                                        st.display !== 'none' && st.visibility !== 'hidden';
                        const enabled = !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                        return visible && enabled && norm(el.innerText || el.textContent) === 'tambah';
                    }) || null;
                    """
                )
            except Exception:
                return None

        def click_robust(el):
            """Klik dengan beberapa metode tanpa langsung menganggap submit berhasil."""
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", el
                )
            except Exception:
                pass
            time.sleep(0.2)

            try:
                ActionChains(driver).move_to_element(el).pause(0.1).click().perform()
                return True
            except Exception:
                pass
            try:
                el.click()
                return True
            except Exception:
                pass
            try:
                driver.execute_script(
                    """
                    const el = arguments[0];
                    el.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, pointerType:'mouse'}));
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                    el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                    el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
                    """,
                    el,
                )
                return True
            except Exception:
                return False

        def submit_confirmed(d):
            try:
                if 'ukpadd' not in (d.current_url or '').lower():
                    return True
            except Exception:
                pass
            try:
                return not self._add_form_ready(d)
            except Exception:
                return False

        try:
            # 1) Klik tombol Kirim Data / Simpan Sebagai Draf.
            btn = WebDriverWait(driver, 10).until(
                lambda d: find_visible_button(d, text) or False
            )
            self.log(3, f"  🔎 Tombol '{text}' ditemukan.")

            if not click_robust(btn):
                self.log(3, f"  ❌ Tombol '{text}' ditemukan tetapi tidak berhasil diklik.")
                return False

            self.log(3, f"  🖱️ '{text}' diklik.")

            # 2) Setelah Kirim Data, web menampilkan modal konfirmasi "Tambah data UKP".
            # Jangan menunggu 15 detik untuk navigasi sebelum menangani modal tersebut.
            if mode == "kirim":
                deadline = time.time() + 8.0
                confirm_btn = None

                while time.time() < deadline:
                    if submit_confirmed(driver):
                        # Jika website suatu saat tidak lagi memakai modal, tetap kompatibel.
                        self.log(3, "  ✅ Submit selesai tanpa modal konfirmasi tambahan.")
                        return True

                    confirm_btn = find_confirmation_button(driver)
                    if confirm_btn is not None:
                        break
                    time.sleep(0.15)

                if confirm_btn is None:
                    self.log(3, "  ⚠️ Modal konfirmasi muncul/tetap di form, tetapi tombol 'Tambah' tidak ditemukan.")
                    return False

                self.log(3, "  ✅ Modal konfirmasi 'Tambah data UKP' terdeteksi.")
                self.log(3, "  🖱️ Klik tombol konfirmasi 'Tambah'...")

                if not click_robust(confirm_btn):
                    self.log(3, "  ❌ Tombol konfirmasi 'Tambah' tidak berhasil diklik.")
                    return False

            # 3) Setelah konfirmasi, tunggu benar-benar keluar dari form sebelum lanjut pasien berikutnya.
            try:
                WebDriverWait(driver, 20).until(submit_confirmed)
                self.log(3, f"  ✅ '{text}' berhasil diproses; form sudah tertutup.")
                return True
            except TimeoutException:
                # Kadang modal masih ada karena klik pertama tidak diterima. Coba sekali lagi.
                if mode == "kirim":
                    confirm_btn = find_confirmation_button(driver)
                    if confirm_btn is not None:
                        self.log(3, "  ↪️ Modal masih terbuka; mencoba klik 'Tambah' sekali lagi.")
                        if click_robust(confirm_btn):
                            try:
                                WebDriverWait(driver, 12).until(submit_confirmed)
                                self.log(3, "  ✅ Submit terkonfirmasi setelah klik ulang 'Tambah'.")
                                return True
                            except TimeoutException:
                                pass

                self.log(3, f"  ❌ '{text}' belum terkonfirmasi; form masih terbuka. Proses dihentikan.")
                return False

        except Exception as e:
            self.log(3, f"  ⚠️ Gagal proses '{text}': {type(e).__name__}: {e!r}")
            return False

    def get_final_ai_response(self, driver):
        last_text = ""
        stable_count = 0
        max_retries = 30
        self.log(2, "  \u23f3 Memulai pemantauan streaming jawaban Gemini...")
        for i in range(max_retries):
            try:
                responses = driver.find_elements(By.CSS_SELECTOR, 'div[id^="model-response-message-content"]')
                if responses:
                    current_text = responses[-1].text.strip()
                    if current_text and current_text == last_text:
                        stable_count += 1
                        if stable_count >= 3:
                            self.log(2, "  \u2728 Gemini selesai mengetik (Respons Stabil).")
                            return current_text
                    else:
                        stable_count = 0
                        last_text = current_text
            except Exception:
                pass
            time.sleep(1.0)
        return last_text if last_text else None

    # ====================== TAB 1: AMBIL DATA PASIEN ======================
    def setup_tab1(self):
        f_config = ttk.LabelFrame(self.tab1, text=" Konfigurasi Scraping e-Puskesmas ", padding=10)
        f_config.pack(fill="x", pady=5)

        ttk.Label(f_config, text="Output Folder:").grid(row=0, column=0, sticky="w", pady=5)
        self.t1_output_dir = tk.StringVar(value=r"C:\Users\HP\Downloads\Temp")
        ttk.Entry(f_config, textvariable=self.t1_output_dir, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(f_config, text="Browse", command=lambda: self.t1_output_dir.set(filedialog.askdirectory())).grid(row=0, column=2)

        f_actions = ttk.Frame(self.tab1, padding=5)
        f_actions.pack(fill="x", pady=5)

        self.btn_start_t1 = ttk.Button(f_actions, text="\u25b6\ufe0f Mulai Scraping", style="Accent.TButton",
                                        command=self.start_tab1_process)
        self.btn_start_t1.pack(side="left", padx=5)
        self.btn_stop_t1 = ttk.Button(f_actions, text="\u23f9\ufe0f Stop", style="Danger.TButton", state="disabled",
                                       command=self.stop_process)
        self.btn_stop_t1.pack(side="left", padx=5)

        self.log_t1 = scrolledtext.ScrolledText(self.tab1, height=20, font=("Consolas", 9),
                                                 bg=COLOR_LOG_BG, fg=COLOR_LOG_FG, insertbackground=COLOR_LOG_FG)
        self.log_t1.pack(fill="both", expand=True, pady=5)

    def start_tab1_process(self):
        self.stop_flag = False
        self.btn_start_t1.config(state="disabled")
        self.btn_stop_t1.config(state="normal")
        threading.Thread(target=self._run_tab1_thread, daemon=True).start()

    # ---- helper ekstraksi data e-puskesmas (dipertahankan, dirapikan) ----
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
            if berat == "AWAS_KOSONG":
                bb = self.get_text_by_label(soup, "Berat Badan")
                berat = self.extract_number_from_text(bb)
            if tinggi == "AWAS_KOSONG":
                tb = self.get_text_by_label(soup, "Tinggi Badan")
                tinggi = self.extract_number_from_text(tb)
        except Exception:
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
        except Exception:
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
        except Exception:
            pass
        return "AWAS_KOSONG"

    def ekstrak_td(self, soup):
        sistole = "AWAS_KOSONG"
        diastole = "AWAS_KOSONG"
        try:
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
                                if "Sistole" in h:
                                    sistole = self.extract_number_from_text(text)
                                elif "Diastole" in h:
                                    diastole = self.extract_number_from_text(text)
            if sistole == "AWAS_KOSONG":
                sistole = self.extract_number_from_text(self.get_text_by_label(soup, "Sistole"))
            if diastole == "AWAS_KOSONG":
                diastole = self.extract_number_from_text(self.get_text_by_label(soup, "Diastole"))
        except Exception:
            pass
        return sistole, diastole

    def ekstrak_rr_nadi(self, soup):
        rr = "AWAS_KOSONG"
        nadi = "AWAS_KOSONG"
        try:
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
                                if "Detak Nadi" in h:
                                    nadi = self.extract_number_from_text(text)
                                elif "Nafas" in h:
                                    rr = self.extract_number_from_text(text)
            if nadi == "AWAS_KOSONG":
                nadi = self.extract_number_from_text(self.get_text_by_label(soup, "Detak Nadi"))
            if rr == "AWAS_KOSONG":
                rr = self.extract_number_from_text(self.get_text_by_label(soup, "Nafas"))
        except Exception:
            pass
        return nadi, rr

    def ekstrak_fisik(self, soup):
        try:
            sistole, diastole = self.ekstrak_td(soup)
            td = f"{sistole}/{diastole}" if sistole != "AWAS_KOSONG" and diastole != "AWAS_KOSONG" else "120/80"
            nadi, rr = self.ekstrak_rr_nadi(soup)
            template = (
                f"GCS: E4 V5 M6 TD: {td} mmHg N: {nadi} x/m RR: {rr} x/m Suhu: 36.6 \u00b0C Spo2: 99 %\n"
                "K/L: a(-), i(-), c(-), d(-), pupil isokor 3 mm/3 mm, RC (+/+)\n"
                "Tho: Simetris, retraksi (-)\n"
                "Cor: S1-S2 normal, murmur (-), gallop (-)\n"
                "Pul: Ves/Ves, ronkhi (-), wheezing (-)\n"
                "Abd: BU (+), turgor baik, nyeri tekan (-)\n"
                "Eks: Akral hangat, CRT < 2 detik, edema (-)"
            )
            return template
        except Exception:
            return "AWAS_KOSONG"

    def ekstrak_penunjang(self, soup):
        try:
            headers = soup.find_all(string=lambda text: text and "Pemeriksaan Detail Laboratorium" in text)
            if not headers:
                if "Pemeriksaan Detail Laboratorium" not in soup.get_text():
                    return "Tidak dilakukan"
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
            for row in rows[1:]:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    nama_pemeriksaan = cols[0].get_text(strip=True)
                    hasil = cols[2].get_text(strip=True)
                    if nama_pemeriksaan and hasil and hasil not in ["-", ""]:
                        results.append(f"{nama_pemeriksaan}: {hasil}")
            return ", ".join(results[:15]) if results else "Tidak dilakukan"
        except Exception as e:
            self.log(1, f"  \u26a0\ufe0f Gagal ekstrak penunjang: {e}")
            return "Tidak dilakukan"

    def _run_tab1_thread(self):
        self.log(1, "\U0001F504 Menghubungkan ke browser...")
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
        record = {}

        while not self.stop_flag:
            self.log(1, f"\U0001F4C4 Memproses Halaman {page}...")
            time.sleep(2)
            rows = driver.find_elements(By.CSS_SELECTOR, "table.datatable tbody tr.success")
            self.log(1, f"\U0001F50D Ditemukan {len(rows)} pasien.")
            if not rows:
                break

            for idx in range(len(rows)):
                if self.stop_flag:
                    break
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
                    except Exception:
                        pass

                    record = {
                        'nama_dokter': 'AWAS_KOSONG', 'no_rekam_medis': 'AWAS_KOSONG',
                        'sumber_data': 'Rawat Jalan', 'tanggal_pelayanan': 'AWAS_KOSONG',
                        'inisial_pasien': 'AWAS_KOSONG', 'jenis_kelamin': 'AWAS_KOSONG',
                        'kategori_pasien': 'Dewasa', 'berat_badan': 'AWAS_KOSONG',
                        'tinggi_badan': 'AWAS_KOSONG', 'anamnesis': 'AWAS_KOSONG',
                        'fisik': 'AWAS_KOSONG', 'penunjang': 'Tidak dilakukan',
                        'diagnosis': 'AWAS_KOSONG', 'diagnosis_banding': '',
                        'tata_laksana_farmako': 'AWAS_KOSONG',
                        'tata_laksana_nonfarmako': 'Kontrol dan konsultasi',
                        'monitoring': 'Keluhan dan kondisi umum',
                        'status_rujukan': 'Tidak rujuk', 'keterangan_CKG': 'AWAS_KOSONG'
                    }

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
                            name = strong.get_text(strip=True).split('(')[0].strip()
                            next_node = strong.next_sibling
                            dosage = ""
                            while next_node and next_node.name != 'strong':
                                if isinstance(next_node, bs4.NavigableString):
                                    text = next_node.strip()
                                    if text and "Jumlah Permintaan" not in text and "Keterangan" not in text:
                                        dosage = text.replace("|", "").strip()
                                        if dosage:
                                            break
                                next_node = next_node.next_sibling
                            items.append(f"{name} {dosage}".strip())
                        record['tata_laksana_farmako'] = ", ".join(items)

                    self.log(1, f"  \U0001F4E5 Sukses: {record['nama_dokter']} - {record['inisial_pasien']}")
                    all_data.append(record)

                    current_page = page
                    try:
                        btn_back = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Lihat Semua')]")))
                        btn_back.click()
                    except Exception:
                        driver.back()
                    time.sleep(1.5)

                    self.log(1, f"  \U0001F504 Kembali ke halaman {current_page}...")
                    if current_page > 1:
                        self._navigate_to_page(driver, current_page)
                        time.sleep(1)
                except Exception as ex:
                    self.log(1, f"  \u274c Error pasien {idx+1}: {ex}")
                    try:
                        driver.back()
                    except Exception:
                        pass

            try:
                next_page_num = page + 1
                if self._navigate_to_page(driver, next_page_num):
                    page += 1
                    self.log(1, f"Pindah ke halaman {page}")
                else:
                    self.log(1, f"Halaman {page} adalah halaman terakhir.")
                    break
            except Exception as e_page:
                self.log(1, f"\U0001F3C1 [INFO] Tidak bisa pindah ke halaman {page + 1}. {e_page}")
                break

        if all_data:
            tgl_pelayanan = all_data[0].get('tanggal_pelayanan', '')
            if tgl_pelayanan and tgl_pelayanan != "AWAS_KOSONG":
                file_tgl = tgl_pelayanan.replace('/', '').replace('-', '')[:8]
            else:
                file_tgl = datetime.now().strftime("%d%m%y")

            out_file = os.path.join(self.t1_output_dir.get(), f"data_ukp_{file_tgl}.csv")
            os.makedirs(os.path.dirname(out_file), exist_ok=True)

            fieldnames = list(record.keys()) if record else list(all_data[0].keys())
            with open(out_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(all_data)
            self.log(1, f"\U0001F4BE Sukses menyimpan {len(all_data)} data!")

        self.root.after(0, lambda: self.btn_start_t1.config(state="normal"))
        self.root.after(0, lambda: self.btn_stop_t1.config(state="disabled"))

    # ====================== TAB 2: PERKAYA ANAMNESIS (AI) ======================
    def setup_tab2(self):
        f_config = ttk.LabelFrame(self.tab2, text=" Konfigurasi AI Copilot Paragraf Rekam Medis ", padding=10)
        f_config.pack(fill="x", pady=5)

        ttk.Label(f_config, text="File Data Mentah (CSV):").grid(row=0, column=0, sticky="w", pady=5)
        self.t2_input_csv = tk.StringVar()
        ttk.Entry(f_config, textvariable=self.t2_input_csv, width=55).grid(row=0, column=1, padx=5)
        ttk.Button(f_config, text="Pilih", command=lambda: self.t2_input_csv.set(
            filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")]))).grid(row=0, column=2)

        ttk.Label(f_config, text="File Output Hasil (CSV):").grid(row=1, column=0, sticky="w", pady=5)
        self.t2_output_csv = tk.StringVar()
        ttk.Entry(f_config, textvariable=self.t2_output_csv, width=55).grid(row=1, column=1, padx=5)
        ttk.Button(f_config, text="Pilih", command=lambda: self.t2_output_csv.set(
            filedialog.asksaveasfilename(filetypes=[("CSV Files", "*.csv")]))).grid(row=1, column=2)

        ttk.Label(f_config, text="System Prompt AI:").grid(row=2, column=0, sticky="nw", pady=5)
        self.txt_prompt = scrolledtext.ScrolledText(f_config, height=4, width=52, font=("Segoe UI", 9))
        self.txt_prompt.grid(row=2, column=1, columnspan=2, padx=5, pady=5)
        self.txt_prompt.insert(tk.END, SYSTEM_INSTRUCTION)

        f_actions = ttk.Frame(self.tab2, padding=5)
        f_actions.pack(fill="x", pady=5)

        self.btn_start_t2 = ttk.Button(f_actions, text="\u25b6\ufe0f Mulai Penyusunan Anamnesis", style="Accent.TButton",
                                        command=self.start_tab2_process)
        self.btn_start_t2.pack(side="left", padx=5)
        self.btn_stop_t2 = ttk.Button(f_actions, text="\u23f9\ufe0f Stop", style="Danger.TButton", state="disabled",
                                       command=self.stop_process)
        self.btn_stop_t2.pack(side="left", padx=5)

        self.log_t2 = scrolledtext.ScrolledText(self.tab2, height=15, font=("Consolas", 9),
                                                 bg=COLOR_LOG_BG, fg=COLOR_LOG_FG, insertbackground=COLOR_LOG_FG)
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
        self.log(2, "\U0001F504 Menghubungkan ke browser...")
        driver = self.get_driver()
        if not driver:
            self.root.after(0, lambda: self.btn_start_t2.config(state="normal"))
            return

        self.log(2, "\U0001F310 Membuka Google Gemini...")
        driver.get("https://gemini.google.com")
        self.rem_tangan_popup(2, "Pastikan Google Gemini sudah terbuka dan siap.\nLogin jika perlu.\n\nKlik OK setelah halaman Gemini siap digunakan.")
        self.log(2, "\u26a1 Memulai proses enrich anamnesis via Gemini...")

        rows = []
        fieldnames = None
        try:
            with open(self.t2_input_csv.get(), mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames
                rows = list(reader)
        except Exception as e:
            self.log(2, f"\u274c Gagal membaca file CSV: {e}")
            self.root.after(0, lambda: self.btn_start_t2.config(state="normal"))
            return

        sys_instruction = self.txt_prompt.get("1.0", tk.END).strip()

        for idx, row in enumerate(rows):
            if self.stop_flag:
                break

            diagnosis = row.get('diagnosis', '')
            anamnesis_ori = row.get('anamnesis', '')
            inisial = row.get('inisial_pasien', 'Unknown')
            self.log(2, f"\U0001F916 Memproses pasien ke-{idx+1}/{len(rows)} -> {inisial}")

            full_prompt = f"{sys_instruction}\nDiagnosis: {diagnosis}\nKeluhan: {anamnesis_ori}"
            try:
                self.log(2, "  \u23f3 Menunggu chatbox Gemini dapat diklik...")
                chatbox_selector = 'div[role="textbox"]'
                time.sleep(2.0)
                text_area = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, chatbox_selector))
                )
                text_area.click()
                time.sleep(0.5)
                text_area.send_keys(Keys.CONTROL + "a")
                time.sleep(0.2)
                text_area.send_keys(Keys.BACKSPACE)
                time.sleep(0.3)
                text_area.send_keys(full_prompt)

                self.log(2, "  \U0001F680 Mengirim prompt ke Gemini...")
                send_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send'], button[aria-label*='Kirim']")
                send_button.click()
                time.sleep(2)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)

                response_text = self.get_final_ai_response(driver)
                if response_text and len(response_text) > 20:
                    row['anamnesis'] = response_text
                    self.log(2, f"  \u2705 Berhasil enrich anamnesis ({len(response_text)} karakter)")
                else:
                    self.log(2, "  \u274c Gagal menangkap respons yang valid, mempertahankan teks asli.")
            except Exception as ex:
                self.log(2, f"  \u274c Error saat memproses pasien {inisial}: {ex}")

            try:
                with open(self.t2_output_csv.get(), mode='w', newline='', encoding='utf-8') as f_out:
                    writer = csv.DictWriter(f_out, fieldnames=fieldnames, delimiter=';', quoting=csv.QUOTE_ALL)
                    writer.writeheader()
                    writer.writerows(rows)
            except Exception:
                pass

            time.sleep(3)

        self.log(2, f"\U0001F4BE Proses Tab 2 selesai! File disimpan: {self.t2_output_csv.get()}")
        self.root.after(0, lambda: self.btn_start_t2.config(state="normal"))
        self.root.after(0, lambda: self.btn_stop_t2.config(state="disabled"))

    # ====================== TAB 3: AUTO INPUT UKP ======================
    def setup_tab3(self):
        f_config = ttk.LabelFrame(self.tab3, text=" Konfigurasi Auto Input Logbook UKP ", padding=10)
        f_config.pack(fill="x", pady=5)

        ttk.Label(f_config, text="File CSV Lengkap:").grid(row=0, column=0, sticky="w", pady=5)
        self.t3_input_csv = tk.StringVar()
        ttk.Entry(f_config, textvariable=self.t3_input_csv, width=55).grid(row=0, column=1, padx=5)
        ttk.Button(f_config, text="Pilih File", command=lambda: self.t3_input_csv.set(
            filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")]))).grid(row=0, column=2)

        self.t3_auto_submit = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f_config,
            text="\U0001F680 Otomatis klik 'Kirim Data' setelah semua field (termasuk diagnosis) terisi - tanpa cek manual",
            variable=self.t3_auto_submit
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        note = ttk.Label(
            f_config,
            text=("Catatan: kolom CSV 'diagnosis' & 'diagnosis_banding' (opsional) boleh berisi lebih dari satu,\n"
                  "dipisah tanda '|' atau ';', contoh: 'Common cold | Faringitis akut'."),
        )
        note.configure(foreground=COLOR_ACCENT_DARK)
        note.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        f_actions = ttk.Frame(self.tab3, padding=5)
        f_actions.pack(fill="x", pady=5)

        self.btn_start_t3 = ttk.Button(f_actions, text="\u25b6\ufe0f Jalankan Auto Input UKP", style="Accent.TButton",
                                        command=self.start_tab3_process)
        self.btn_start_t3.pack(side="left", padx=5)
        self.btn_stop_t3 = ttk.Button(f_actions, text="\u23f9\ufe0f Stop", style="Danger.TButton", state="disabled",
                                       command=self.stop_process)
        self.btn_stop_t3.pack(side="left", padx=5)

        self.log_t3 = scrolledtext.ScrolledText(self.tab3, height=22, font=("Consolas", 9),
                                                 bg=COLOR_LOG_BG, fg=COLOR_LOG_FG, insertbackground=COLOR_LOG_FG)
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
        self.log(3, "\U0001F504 Menghubungkan ke Chrome...")
        driver = self.get_driver()
        if not driver:
            self.root.after(0, lambda: self.btn_start_t3.config(state="normal"))
            return

        driver.get(URL_PKM)
        self.rem_tangan_popup(3, "Pastikan sudah di halaman daftar UKP dan sudah login.\n\nKlik OK setelah siap.")
        self.log(3, "\u26a1 Memulai Auto Input UKP...")

        rows = []
        try:
            with open(self.t3_input_csv.get(), mode='r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f, delimiter=';'))
        except Exception as e:
            self.log(3, f"\u274c Gagal baca CSV: {e}")
            self.root.after(0, lambda: self.btn_start_t3.config(state="normal"))
            return

        auto_submit = self.t3_auto_submit.get()

        for idx, row in enumerate(rows):
            if self.stop_flag:
                break

            inisial = row.get('inisial_pasien', 'Unknown')
            self.log(3, f"\U0001F504 Memproses data ke-{idx+1}/{len(rows)} - {inisial}")

            if not self.click_tambah_data(driver):
                self.log(3, "  \u274c Gagal membuka form 'Tambah Data'. Baris ini dilewati.")
                continue

            try:
                # --- TATA LAKSANA FARMAKOLOGI ---
                farmako_data = self._clean_text(row.get("tata_laksana_farmako", ""), allow_newline=False)
                if farmako_data:
                    try:
                        xpath_label = "//label[normalize-space()='Farmakoterapi']"
                        label_el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_label)))
                        checkbox_id = label_el.get_attribute("for")
                        checkbox = driver.find_element(By.ID, checkbox_id)
                        if not checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", label_el)
                            time.sleep(0.4)
                        input_xpath = f"{xpath_label}/following::input[@placeholder='Masukkan tata laksana'][1]"
                        input_field = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, input_xpath)))
                        self._js_set_value(driver, input_field, farmako_data)
                    except Exception as e:
                        self.log(3, f"  \u26a0\ufe0f Gagal isi Farmakoterapi: {e}")

                # --- TATA LAKSANA NON-FARMAKOLOGI ---
                non_farmako_data = self._clean_text(row.get("tata_laksana_nonfarmako", ""), allow_newline=False)
                if non_farmako_data:
                    try:
                        xpath_label = "//label[normalize-space()='Non-Farmakoterapi']"
                        label_el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_label)))
                        checkbox_id = label_el.get_attribute("for")
                        checkbox = driver.find_element(By.ID, checkbox_id)
                        if not checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", label_el)
                            time.sleep(0.4)
                        input_xpath = f"{xpath_label}/following::input[@placeholder='Masukkan tata laksana'][1]"
                        input_field = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, input_xpath)))
                        current_value = input_field.get_attribute("value")
                        if not current_value:
                            self._js_set_value(driver, input_field, non_farmako_data)
                    except Exception as e:
                        self.log(3, f"  \u26a0\ufe0f Gagal isi Non-Farmakoterapi: {e}")

                # --- JENIS KELAMIN ---
                gender_raw = row.get("jenis_kelamin", "").strip().lower()
                gender_map = {"laki-laki": "MALE", "laki_laki": "MALE", "l": "MALE",
                              "perempuan": "FEMALE", "p": "FEMALE"}
                target_gender_id = gender_map.get(gender_raw)
                if target_gender_id:
                    try:
                        gender_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, target_gender_id)))
                        driver.execute_script("arguments[0].click();", gender_element)
                        time.sleep(0.2)
                    except Exception as e:
                        self.log(3, f"  \u26a0\ufe0f Gagal klik jenis kelamin: {e}")

                # --- STATUS RUJUKAN ---
                rujukan_raw = row.get("status_rujukan", "").strip().lower()
                target_rujukan_id = None
                if "tidak" in rujukan_raw or "bukan" in rujukan_raw or rujukan_raw == "false":
                    target_rujukan_id = "false"
                elif "rujuk" in rujukan_raw or rujukan_raw == "true":
                    target_rujukan_id = "true"
                if target_rujukan_id:
                    try:
                        rujukan_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, target_rujukan_id)))
                        driver.execute_script("arguments[0].click();", rujukan_element)
                        time.sleep(0.2)
                    except Exception as e:
                        self.log(3, f"  \u26a0\ufe0f Gagal klik status rujukan: {e}")

                # --- TANGGAL PELAYANAN (dicari via LABEL, bukan ID yang berubah-ubah) ---
                tanggal_pelayanan = self._clean_text(row.get('tanggal_pelayanan', ''), allow_newline=False)
                if tanggal_pelayanan:
                    try:
                        container = self._field_container(driver, "Tanggal pelayanan")
                        date_btn = container.find_element(By.XPATH, ".//button")
                        date_span = date_btn.find_element(By.XPATH, ".//span[last()]")
                        driver.execute_script(
                            """
                            const span = arguments[0];
                            const val = arguments[1];
                            span.innerText = val;
                            span.dispatchEvent(new Event('input', {bubbles:true}));
                            span.dispatchEvent(new Event('change', {bubbles:true}));
                            const btn = span.closest('button');
                            if (btn) { btn.dispatchEvent(new Event('change', {bubbles:true})); }
                            """,
                            date_span, tanggal_pelayanan
                        )
                        self.log(3, f"  \u2705 Tanggal pelayanan diisi: {tanggal_pelayanan}")
                    except Exception as e:
                        self.log(3, f"  \u26a0\ufe0f Gagal isi tanggal pelayanan: {e}")

                # --- FIELD LAINNYA ---
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
                self.fill_textarea_by_contains(driver, "monitoring", row.get('monitoring', ''))

                # --- DIAGNOSIS & DIAGNOSIS BANDING (BARU, sebelumnya tidak pernah diisi) ---
                self.fill_diagnosis_multiselect(driver, "options-multi-diagnosis",
                                                 row.get('diagnosis', ''), "Diagnosis")
                self.fill_diagnosis_multiselect(driver, "options-multi-diagnosis_banding",
                                                 row.get('diagnosis_banding', ''), "Diagnosis Banding")

            except Exception as e:
                self.log(3, f"  \u274c Terjadi galat saat mengisi form: {e}")

            # --- VERIFIKASI: apakah kita masih di form yang sama? ---
            if not self.is_on_add_form(driver):
                self.log(3, "  \U0001F6D1 Halaman berpindah dari form 'Tambah data UKP' sebelum selesai diisi.")
                self.log(3, "  \u23f8\ufe0f Otomatisasi dihentikan. Cek manual lalu jalankan lagi.")
                messagebox.showwarning(
                    "Halaman Berpindah Tak Terduga",
                    f"Data ke-{idx+1} ({inisial}): halaman keluar dari form sebelum selesai diisi.\n\n"
                    "Kemungkinan penyebab: sesi login habis, koneksi lambat, atau elemen lain "
                    "ter-klik tidak sengaja.\n\nSilakan cek manual sebelum melanjutkan."
                )
                break

            if auto_submit:
                self.log(3, "  🚀 Mode otomatis aktif -> mengirim data...")
                if self._find_and_click_submit_button(driver, "kirim"):
                    self.log(3, f"  ✅ Data ke-{idx+1} ({inisial}) terkirim dan submit terkonfirmasi.")
                    time.sleep(1.0)
                else:
                    self.log(3, "  🛑 Kirim Data tidak terkonfirmasi. Otomatisasi DIHENTIKAN agar data berikutnya tidak menumpuk.")
                    self.stop_flag = True
                    messagebox.showwarning(
                        "Auto Submit Dihentikan",
                        f"Data ke-{idx+1} ({inisial}) sudah terisi, tetapi pengiriman tidak terkonfirmasi.\n\n"
                        "Script dihentikan sebelum memproses pasien berikutnya agar data tidak menumpuk.\n\n"
                        "Silakan cek form dan klik 'Kirim Data' secara manual bila perlu."
                    )
                    break
            else:
                self.log(3, "\n" + "=" * 70)
                self.log(3, "\u23f8\ufe0f  FORM SUDAH TERISI (termasuk diagnosis) - SILAKAN CEK & SUBMIT")
                self.log(3, "=" * 70)
                messagebox.showinfo(
                    "Siap Submit",
                    f"Data ke-{idx+1} ({inisial}) sudah terisi otomatis, termasuk Diagnosis & Diagnosis Banding.\n\n"
                    "Silakan:\n"
                    "\u2022 Cek ulang semua isian\n"
                    "\u2022 Klik 'Kirim Data' atau 'Simpan Sebagai Draf'\n\n"
                    "Tekan OK setelah berhasil submit untuk lanjut ke data berikutnya."
                )
            time.sleep(1)

        self.log(3, "\U0001F3C1 Semua data telah diproses.")
        self.root.after(0, lambda: self.btn_start_t3.config(state="normal"))
        self.root.after(0, lambda: self.btn_stop_t3.config(state="disabled"))

    def stop_process(self):
        self.stop_flag = True
        self.log(1, "\u23f9\ufe0f Proses dihentikan manual.")
        self.log(2, "\u23f9\ufe0f Proses dihentikan manual.")
        self.log(3, "\u23f9\ufe0f Proses dihentikan manual.")


if __name__ == "__main__":
    root = tk.Tk()
    app = UKPLauncher(root)
    root.mainloop()