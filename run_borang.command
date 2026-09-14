#!/bin/bash
# ============================================================
# LAUNCHER - Borang PKM Otomatis (macOS)
# Vibe code by yaqinkdr 2026
# ============================================================

cd "$(dirname "$0")"

# === KONFIGURASI ===
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR="$HOME/selenium/AutomationProfile"
DEBUG_PORT=9222
PY_SCRIPT="input_borang_isip.py"

echo "================================================"
echo "  🚀 BORANG PKM OTOMATIS - Launcher macOS"
echo "================================================"
echo ""

# === 1. Cek Python ===
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 tidak ditemukan!"
    echo "   Install dulu: https://www.python.org/downloads/"
    read -p "Tekan Enter buat keluar..."
    exit 1
fi
echo "✅ Python3 OK: $(python3 --version)"
echo ""

# === 2. Cek Chrome ===
if [ ! -f "$CHROME" ]; then
    echo "❌ Chrome tidak ditemukan di: $CHROME"
    echo "   Edit file ini dan ubah variable CHROME."
    read -p "Tekan Enter buat keluar..."
    exit 1
fi
echo "✅ Chrome OK"
echo ""

# === 3. Cek script Python ===
if [ ! -f "$PY_SCRIPT" ]; then
    echo "❌ File '$PY_SCRIPT' tidak ditemukan di folder ini!"
    echo "   Pastikan file python ada di folder yang sama."
    read -p "Tekan Enter buat keluar..."
    exit 1
fi
echo "✅ Script OK: $PY_SCRIPT"
echo ""

# === 4. Cek dependencies ===
echo "🔍 Cek dependencies Python..."
python3 -c "import selenium, bs4, webdriver_manager" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Ada dependency yang belum keinstall."
    read -p "Install sekarang? (y/n): " ans
    if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
        python3 -m pip install --upgrade pip
        python3 -m pip install selenium webdriver-manager beautifulsoup4
    else
        echo "❌ Dependencies wajib. Keluar."
        read -p "Tekan Enter buat keluar..."
        exit 1
    fi
fi
echo "✅ Dependencies OK"
echo ""

# === 5. Bikin folder profile kalau belum ada ===
if [ ! -d "$PROFILE_DIR" ]; then
    mkdir -p "$PROFILE_DIR"
    echo "📁 Folder profile dibuat: $PROFILE_DIR"
else
    echo "✅ Folder profile OK: $PROFILE_DIR"
fi
echo ""

# === 6. Cek port 9222 ===
PORT_PID=$(lsof -ti :$DEBUG_PORT 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "⚠️  Port $DEBUG_PORT sudah dipakai (PID: $PORT_PID)"
    echo "   Ini tandanya Chrome debugger mungkin udah jalan."
    read -p "Kill PID tersebut? (y/n): " killit
    if [[ "$killit" == "y" || "$killit" == "Y" ]]; then
        kill -9 $PORT_PID
        echo "✅ PID $PORT_PID dibunuh"
        sleep 1
    else
        echo "⚠️  Port tetap kepake, launcher tetap lanjut (Chrome debug mungkin udah running)"
    fi
else
    echo "✅ Port $DEBUG_PORT bebas"
fi
echo ""

# === 7. Buka Chrome Debug Mode ===
echo "🌐 Membuka Chrome Debug Mode..."
"$CHROME" \
    --remote-debugging-port=$DEBUG_PORT \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    > /dev/null 2>&1 &

CHROME_PID=$!
echo "✅ Chrome PID: $CHROME_PID"
echo ""

# === 8. Tunggu Chrome siap ===
echo "⏳ Menunggu Chrome siap... (3 detik)"
sleep 3

# Verify port
if lsof -ti :$DEBUG_PORT > /dev/null 2>&1; then
    echo "✅ Chrome Debug Mode aktif di port $DEBUG_PORT"
else
    echo "⚠️  Chrome mungkin belum siap, tapi lanjut aja..."
fi
echo ""

# === 9. Jalanin Python GUI ===
echo "🐍 Menjalankan Python GUI..."
echo "================================================"
echo ""

python3 "$PY_SCRIPT"

# === 10. Setelah Python selesai ===
echo ""
echo "================================================"
echo "🏁 Aplikasi ditutup."
echo "==============================================="
read -p "Tekan Enter buat keluar..."
