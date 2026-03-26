@echo off
title MNG Printer Bridge - Build .exe
echo.
echo ============================================================
echo   MNG Printer Bridge - Building standalone .exe
echo ============================================================
echo.
echo This will create a single MNG_Printer_Bridge.exe that
echo includes everything - no Python or SumatraPDF install needed!
echo.

REM ── Check Python ──
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is needed to BUILD the .exe
    echo Install from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found
python --version

REM ── Install PyInstaller ──
echo.
echo [STEP 1/4] Installing PyInstaller...
pip install pyinstaller --quiet
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)
echo [OK] PyInstaller installed

REM ── Download SumatraPDF portable (if not already present) ──
echo.
echo [STEP 2/4] Getting SumatraPDF portable...
if exist "SumatraPDF.exe" (
    echo [OK] SumatraPDF.exe already present
) else (
    echo Downloading SumatraPDF portable...
    
    REM Try PowerShell download
    powershell -Command "& { try { Invoke-WebRequest -Uri 'https://www.sumatrapdfreader.org/dl/rel/3.5.2/SumatraPDF-3.5.2-64.exe' -OutFile 'SumatraPDF.exe' -UseBasicParsing; Write-Host 'Downloaded' } catch { Write-Host 'FAILED' } }" 2>nul
    
    if exist "SumatraPDF.exe" (
        echo [OK] SumatraPDF downloaded
    ) else (
        echo.
        echo [WARNING] Could not auto-download SumatraPDF.
        echo Please manually download the PORTABLE version from:
        echo   https://www.sumatrapdfreader.org/download-free-pdf-viewer
        echo And place "SumatraPDF.exe" in this folder.
        echo.
        echo The .exe will still be built, but without embedded SumatraPDF.
        echo Users will need to install SumatraPDF separately.
        echo.
    )
)

REM ── Convert icon to .ico if not exists ──
echo.
echo [STEP 3/4] Preparing icon...
if exist "icon.ico" (
    echo [OK] icon.ico exists
) else if exist "icon.png" (
    echo Converting icon.png to icon.ico...
    python -c "from PIL import Image; img=Image.open('icon.png'); sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]; icons=[img.resize(s, Image.LANCZOS) for s in sizes]; icons[0].save('icon.ico', format='ICO', sizes=[(i.width,i.height) for i in icons], append_images=icons[1:]); print('[OK] icon.ico created')" 2>nul
    if not exist "icon.ico" (
        echo [WARNING] Could not convert icon. Install Pillow: pip install Pillow
        echo Building without custom icon...
    )
) else (
    echo [WARNING] No icon.png found. Building without icon.
)

REM ── Build with PyInstaller ──
echo.
echo [STEP 4/4] Building .exe with PyInstaller...
echo This may take 1-2 minutes...
echo.

REM Build the command
set PYINST_CMD=pyinstaller --onefile --windowed --name "MNG_Printer_Bridge"

REM Add icon if available
if exist "icon.ico" (
    set PYINST_CMD=%PYINST_CMD% --icon=icon.ico
)

REM Add data files
if exist "icon.png" (
    set PYINST_CMD=%PYINST_CMD% --add-data "icon.png;."
)

REM Add SumatraPDF if available
if exist "SumatraPDF.exe" (
    set PYINST_CMD=%PYINST_CMD% --add-data "SumatraPDF.exe;."
    echo [INFO] SumatraPDF will be embedded in the .exe
)

REM Run PyInstaller
%PYINST_CMD% printer_bridge.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed! Check the errors above.
    pause
    exit /b 1
)

REM ── Done! ──
echo.
echo ============================================================
echo   BUILD SUCCESSFUL!
echo ============================================================
echo.
echo   Your .exe is at:
echo     dist\MNG_Printer_Bridge.exe
echo.
echo   That single file is all you need!
echo   Copy it to the office PC and double-click to run.
echo.
echo   The .exe will create config.ini next to itself
echo   on first run.
echo ============================================================
echo.

REM Copy to root for convenience
if exist "dist\MNG_Printer_Bridge.exe" (
    copy /Y "dist\MNG_Printer_Bridge.exe" "MNG_Printer_Bridge.exe" >nul
    echo   Also copied to: MNG_Printer_Bridge.exe
    echo.
)

pause
