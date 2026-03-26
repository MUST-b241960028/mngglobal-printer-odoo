#!/bin/bash
set -e

echo "============================================================"
echo "  Building Windows .exe on Linux via Wine"
echo "============================================================"
echo ""

# 1. Check for Wine
if ! command -v wine &> /dev/null; then
    echo "[ERROR] Wine is not installed."
    echo "Please install it with: sudo apt install wine wine32:i386"
    exit 1
fi

WINEPREFIX="$PWD/.wine_python"
export WINEPREFIX
export WINEARCH=win32

echo "[INFO] Using Wine Prefix: $WINEPREFIX"

# Create prefix
wineboot -u &> /dev/null || true

PYTHON_PREFIX='C:\Python310\'

# 2. Download Python for Windows (3.10.11 32-bit)
if [ ! -f "python-installer.exe" ]; then
    echo "[INFO] Downloading Python for Windows..."
    wget -q --show-progress "https://www.python.org/ftp/python/3.10.11/python-3.10.11.exe" -O python-installer.exe
fi

# 3. Install Python inside Wine
echo "[INFO] Installing Python inside Wine (this takes a minute)..."
# We install it to C:\Python310 directly
wine python-installer.exe /quiet InstallAllUsers=1 TargetDir=$PYTHON_PREFIX PrependPath=1 Include_doc=0 Include_test=0 Include_tcltk=1
# Wait for installation to finish
while ! WINEPREFIX="$WINEPREFIX" wine cmd /c "if exist $PYTHON_PREFIX\python.exe (exit 0) else (exit 1)"; do
    sleep 2
done
echo "[OK] Python installed in Wine."

# 4. Install PyInstaller
echo "[INFO] Installing PyInstaller..."
wine "$PYTHON_PREFIX\\python.exe" -m pip install pyinstaller --disable-pip-version-check

# 5. Download SumatraPDF
if [ ! -f "SumatraPDF.exe" ]; then
    echo "[INFO] Downloading SumatraPDF Portable..."
    wget -q --show-progress "https://www.sumatrapdfreader.org/dl/rel/3.5.2/SumatraPDF-3.5.2.exe" -O SumatraPDF.exe
fi

# 6. Build the .exe!
echo "[INFO] Building the .exe using PyInstaller..."
wine "$PYTHON_PREFIX\\Scripts\\pyinstaller.exe" --onefile --windowed --name "MNG_Printer_Bridge" --add-data "SumatraPDF.exe;." --icon="icon.ico" --add-data "icon.png;." printer_bridge.py

echo ""
echo "============================================================"
echo "[SUCCESS] Build complete!"
echo "Your Windows executable is ready:"
ls -lh dist/MNG_Printer_Bridge.exe
echo ""
echo "You can now copy it to a USB drive or send it to your office PC."
echo "============================================================"
