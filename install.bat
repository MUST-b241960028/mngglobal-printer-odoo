@echo off
title Odoo Printer Bridge - Setup
echo.
echo ============================================
echo   Odoo Printer Bridge - Windows Setup
echo ============================================
echo.

REM ── Check Python ──
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.8+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

REM ── Check SumatraPDF ──
if exist "C:\Program Files\SumatraPDF\SumatraPDF.exe" (
    echo [OK] SumatraPDF found at default location.
) else (
    echo [WARNING] SumatraPDF not found at default location.
    echo   Download free from: https://www.sumatrapdfreader.org/download-free-pdf-viewer
    echo   The script will fall back to Windows default PDF handler.
)
echo.

REM ── Create config.ini if it doesn't exist ──
if not exist "config.ini" (
    echo [SETUP] Creating config.ini from template...
    copy "config.ini.example" "config.ini" >nul
    echo [OK] config.ini created.
    echo.
    echo ============================================
    echo   IMPORTANT: Edit config.ini with your
    echo   Odoo credentials before running!
    echo ============================================
    echo.
    echo Opening config.ini in Notepad...
    notepad config.ini
) else (
    echo [OK] config.ini already exists.
)
echo.

REM ── Create temp folder ──
if not exist "temp_prints" (
    mkdir temp_prints
    echo [OK] Created temp_prints folder.
)
echo.

REM ── Test connection ──
echo ============================================
echo   Testing Odoo connection...
echo ============================================
echo.
python printer_bridge.py --test
echo.

if %ERRORLEVEL% equ 0 (
    echo ============================================
    echo   Setup complete! To start printing, run:
    echo.
    echo     python printer_bridge.py
    echo.
    echo   Or double-click "start_printer.bat"
    echo ============================================
) else (
    echo ============================================
    echo   Connection test failed. Please check your
    echo   config.ini settings and try again.
    echo ============================================
)
echo.
pause
