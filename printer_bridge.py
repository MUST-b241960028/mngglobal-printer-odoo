#!/usr/bin/env python3
"""
MNG Printer Bridge — Odoo Cloud-to-Local Printer
==================================================
A desktop application that polls an Odoo instance for PDF attachments
in a "PRINT QUEUE" note and sends them to a local printer.

Usage:
    MNG_Printer_Bridge.exe        # Just double-click the .exe!
    python printer_bridge.py      # Or run with Python directly

Requirements (only if running from source):
    - Python 3.8+
    - Odoo Community with the Notes app installed
"""

import xmlrpc.client
import configparser
import subprocess
import base64
import os
import sys
import time
import logging
import signal
import argparse
import threading
import queue
import shutil
import socket
from pathlib import Path
from datetime import datetime, timedelta

try:
    import pystray
    from PIL import Image as PilImage
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

# ──────────────────────────────────────────────────────────────────────
# PyInstaller / Path helpers
# ──────────────────────────────────────────────────────────────────────

def _is_frozen():
    """Are we running as a PyInstaller bundle?"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def resource_path(filename):
    """Get path to a bundled resource file (icon, SumatraPDF, etc.)."""
    if _is_frozen():
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def app_dir():
    """Get the directory where the .exe lives (for config, logs, etc.).
    When frozen, this is the folder containing the .exe.
    When running from source, this is the script's directory."""
    if _is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

APP_NAME = "MNG Printer Bridge"
APP_VERSION = "1.3.2"
CONFIG_FILE = os.path.join(app_dir(), "config.ini")
LOG_FILE = os.path.join(app_dir(), "printer_bridge.log")
ICON_FILE = "icon.png"  # resolved via resource_path()
AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_REG_NAME = "MNGPrinterBridge"

# Brand colors (MNG logo palette)
COLOR_BG = "#1a1a2e"
COLOR_BG_LIGHT = "#16213e"
COLOR_BG_CARD = "#1f2b47"
COLOR_ACCENT = "#0ea5e9"
COLOR_ACCENT_HOVER = "#38bdf8"
COLOR_PURPLE = "#9b59b6"
COLOR_TEXT = "#e2e8f0"
COLOR_TEXT_DIM = "#94a3b8"
COLOR_SUCCESS = "#22c55e"
COLOR_ERROR = "#ef4444"
COLOR_WARNING = "#f59e0b"
COLOR_INPUT_BG = "#0f172a"
COLOR_BORDER = "#334155"

# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────

def setup_logging():
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logger = logging.getLogger("PrinterBridge")
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt, datefmt))
    logger.addHandler(ch)

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt, datefmt))
    logger.addHandler(fh)

    return logger

log = setup_logging()

# ──────────────────────────────────────────────────────────────────────
# Self-update — pull latest .exe from GitHub Releases
# ──────────────────────────────────────────────────────────────────────

UPDATE_REPO = "MUST-b241960028/mngglobal-printer-odoo"
UPDATE_ASSET = "MNG_Printer_Bridge.exe"
UPDATE_API = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_CHECK_INTERVAL = 6 * 3600  # seconds between background checks


def _parse_version(s):
    """'v1.2.0' / '1.2.0' -> (1, 2, 0). Non-numeric parts are ignored."""
    s = (s or "").strip().lstrip("vV")
    parts = []
    for chunk in s.split("."):
        num = "".join(c for c in chunk if c.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts) if parts else (0,)


def _fetch_latest_release():
    """Return (version_str, download_url) of the latest release, or None on any failure."""
    import json
    import urllib.request
    try:
        req = urllib.request.Request(
            UPDATE_API,
            headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}",
                     "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        url = None
        for asset in data.get("assets", []):
            if asset.get("name") == UPDATE_ASSET:
                url = asset.get("browser_download_url")
                break
        if tag and url:
            return tag, url
    except Exception as e:
        log.debug(f"Update check failed: {e}")
    return None


def _download_file(url, dest):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def apply_self_update(download_url):
    """Download the new .exe and hand off to a batch script that swaps it in
    once this process exits, then relaunches. Returns True if handoff started.
    Windows + frozen only."""
    if not (_is_frozen() and sys.platform == "win32"):
        return False
    try:
        cur_exe = sys.executable
        new_exe = os.path.join(app_dir(), f"{UPDATE_ASSET}.new")
        log.info(f"Downloading update to {new_exe} ...")
        _download_file(download_url, new_exe)
        if not os.path.exists(new_exe) or os.path.getsize(new_exe) < 100000:
            log.error("Downloaded update looks invalid; aborting.")
            return False

        bat_path = os.path.join(app_dir(), "_mng_update.bat")
        # move /Y retries until the running .exe releases its file lock (i.e. we exit),
        # then relaunches minimized (tray) and deletes itself.
        bat = (
            "@echo off\r\n"
            "timeout /t 2 /nobreak >NUL\r\n"
            ":retry\r\n"
            f'move /Y "{new_exe}" "{cur_exe}" >NUL 2>&1\r\n'
            "if errorlevel 1 (\r\n"
            "    timeout /t 1 /nobreak >NUL\r\n"
            "    goto retry\r\n"
            ")\r\n"
            f'start "" "{cur_exe}" --minimized\r\n'
            'del "%~f0"\r\n'
        )
        with open(bat_path, "w") as f:
            f.write(bat)

        log.info("Launching updater and exiting for swap...")
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                           | getattr(subprocess, "DETACHED_PROCESS", 0)),
            close_fds=True,
        )
        return True
    except Exception as e:
        log.error(f"Self-update failed: {e}")
        return False


def check_for_update():
    """Check GitHub for a newer release. If found, download + relaunch.
    Returns True if an update was started (caller should exit)."""
    if not _is_frozen():
        return False  # running from source — never self-update
    latest = _fetch_latest_release()
    if not latest:
        return False
    tag, url = latest
    if _parse_version(tag) > _parse_version(APP_VERSION):
        log.info(f"Update available: {APP_VERSION} -> {tag}")
        return apply_self_update(url)
    log.debug(f"Up to date (current {APP_VERSION}, latest {tag})")
    return False


# ──────────────────────────────────────────────────────────────────────
# Printer Discovery — auto-detect ALL installed printers
# ──────────────────────────────────────────────────────────────────────

def _get_bundled_sumatra():
    """Find SumatraPDF — bundled inside the .exe or in the app directory."""
    # Check if bundled (PyInstaller)
    bundled = resource_path("SumatraPDF.exe")
    if os.path.exists(bundled):
        return bundled
    # Check app directory
    local = os.path.join(app_dir(), "SumatraPDF.exe")
    if os.path.exists(local):
        return local
    # Check common install locations
    for p in [
        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
        os.path.expanduser(r"~\AppData\Local\SumatraPDF\SumatraPDF.exe"),
    ]:
        if os.path.exists(p):
            return p
    return None


def discover_printers():
    """
    Detect all installed printers on the system.
    Returns a list of dicts: [{"name": "...", "default": bool}, ...]
    Works on Windows, Linux, and Wine.
    """
    printers = []

    # ── Method 1: Windows — wmic (works on Win7+, Wine) ──
    try:
        result = subprocess.run(
            ["wmic", "printer", "get", "Name,Default,PortName", "/format:csv"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            # CSV format: Node,Default,Name,PortName
            for line in lines[1:]:  # skip header
                parts = line.split(",")
                if len(parts) >= 3:
                    is_default = parts[1].strip().upper() == "TRUE"
                    name = parts[2].strip()
                    port = parts[3].strip() if len(parts) > 3 else ""
                    if name:
                        printers.append({
                            "name": name,
                            "default": is_default,
                            "port": port,
                        })
            if printers:
                log.info(f"Discovered {len(printers)} printer(s) via wmic")
                return printers
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # ── Method 2: Windows — PowerShell (Win10+) ──
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Printer | Select-Object Name,Type,PortName,Default | ConvertTo-Csv -NoTypeInformation"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = [l.strip().strip('"') for l in result.stdout.strip().split("\n") if l.strip()]
            for line in lines[1:]:
                parts = [p.strip().strip('"') for p in line.split('","')]
                if parts and parts[0]:
                    is_default = parts[3].upper() == "TRUE" if len(parts) > 3 else False
                    port = parts[2] if len(parts) > 2 else ""
                    printers.append({
                        "name": parts[0],
                        "default": is_default,
                        "port": port,
                    })
            if printers:
                log.info(f"Discovered {len(printers)} printer(s) via PowerShell")
                return printers
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # ── Method 3: Windows — registry query (backup) ──
    try:
        result = subprocess.run(
            ["reg", "query",
             r"HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\Devices"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and "REG_SZ" in line:
                    name = line.split("    REG_SZ")[0].strip()
                    if name and not name.startswith("HKEY"):
                        printers.append({
                            "name": name,
                            "default": False,
                            "port": "",
                        })
            if printers:
                # Try to find default
                try:
                    def_result = subprocess.run(
                        ["reg", "query",
                         r"HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\Windows",
                         "/v", "Device"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if def_result.returncode == 0:
                        for line in def_result.stdout.split("\n"):
                            if "Device" in line and "REG_SZ" in line:
                                default_name = line.split("REG_SZ")[1].strip().split(",")[0]
                                for p in printers:
                                    if p["name"] == default_name:
                                        p["default"] = True
                except Exception:
                    pass
                log.info(f"Discovered {len(printers)} printer(s) via registry")
                return printers
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # ── Method 4: Linux / macOS — CUPS (lpstat) ──
    try:
        result = subprocess.run(
            ["lpstat", "-p", "-d"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            default_printer = ""
            for line in result.stdout.strip().split("\n"):
                if line.startswith("system default destination:"):
                    default_printer = line.split(":")[1].strip()
                elif line.startswith("printer "):
                    name = line.split()[1]
                    printers.append({
                        "name": name,
                        "default": name == default_printer,
                        "port": "",
                    })
            if printers:
                log.info(f"Discovered {len(printers)} printer(s) via CUPS/lpstat")
                return printers
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    log.warning("No printers discovered on this system.")
    return printers

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

def load_config(config_path=CONFIG_FILE):
    config = configparser.ConfigParser()
    if not os.path.exists(config_path):
        return None
    config.read(config_path, encoding="utf-8")
    return config

def save_config(config_path, odoo_url, database, username, password,
                sumatra_path, printer_name, poll_interval,
                autostart=None, minimize_to_tray=None):
    config = configparser.ConfigParser()
    # Preserve existing settings not passed in
    existing = load_config(config_path)
    if autostart is None and existing:
        autostart = existing.getboolean("settings", "autostart", fallback=False)
    if minimize_to_tray is None and existing:
        minimize_to_tray = existing.getboolean("settings", "minimize_to_tray", fallback=True)
    if minimize_to_tray is None:
        minimize_to_tray = True
    config["odoo"] = {
        "url": odoo_url, "database": database,
        "username": username, "password": password,
    }
    config["printer"] = {
        "sumatra_path": sumatra_path, "printer_name": printer_name,
    }
    config["settings"] = {
        "poll_interval": str(poll_interval),
        "temp_folder": "temp_prints",
        "autostart": str(bool(autostart)),
        "minimize_to_tray": str(bool(minimize_to_tray)),
    }
    with open(config_path, "w", encoding="utf-8") as f:
        config.write(f)
    log.info(f"Configuration saved to {config_path}")

# ──────────────────────────────────────────────────────────────────────
# Windows Auto-Start
# ──────────────────────────────────────────────────────────────────────

def _startup_folder():
    """Return path to Windows user Startup folder."""
    return os.path.join(os.environ.get("APPDATA", ""),
                        r"Microsoft\Windows\Start Menu\Programs\Startup")

def _vbs_path():
    return os.path.join(_startup_folder(), "MNGPrinterBridge.vbs")

def get_autostart_enabled(config_path=None):
    """Check autostart state: Startup folder VBScript takes priority, then config.ini."""
    if sys.platform == "win32":
        if os.path.exists(_vbs_path()):
            return True
    if config_path:
        cfg = load_config(config_path)
        if cfg:
            return cfg.getboolean("settings", "autostart", fallback=False)
    return False

def set_autostart_enabled(enable):
    """Enable/disable auto-start via Windows Startup folder VBScript. Returns (success, error_msg)."""
    if sys.platform != "win32":
        return True, None
    vbs = _vbs_path()
    try:
        if enable:
            exe_path = sys.executable if _is_frozen() else os.path.abspath(__file__)
            vbs_content = (
                'Set WShell = CreateObject("WScript.Shell")\n'
                f'WShell.Run Chr(34) & "{exe_path}" & Chr(34) & " --minimized", 0, False\n'
            )
            os.makedirs(_startup_folder(), exist_ok=True)
            with open(vbs, "w", encoding="utf-8") as f:
                f.write(vbs_content)
            log.info(f"Auto-start enabled via Startup folder: {vbs}")
        else:
            if os.path.exists(vbs):
                os.remove(vbs)
            log.info("Auto-start disabled, VBS removed")
        return True, None
    except Exception as e:
        log.error(f"Failed to set auto-start: {e}")
        return False, str(e)

# ──────────────────────────────────────────────────────────────────────
# Odoo XML-RPC Connection
# ──────────────────────────────────────────────────────────────────────

class OdooConnection:
    def __init__(self, url, database, username, password, verify_ssl=True):
        self.url = url.rstrip("/")
        self.database = database
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.use_unverified_ssl = not verify_ssl
        self.uid = None
        self.models = None
        self.server_version = "unknown"
        self.last_error = ""

    def _create_proxy(self, path, unverified=False):
        context = None
        if unverified or self.use_unverified_ssl or not self.verify_ssl:
            import ssl
            context = ssl._create_unverified_context()
        return xmlrpc.client.ServerProxy(f"{self.url}{path}", allow_none=True, context=context)

    def _is_ssl_error(self, e):
        err_str = str(e).lower()
        return any(k in err_str for k in ("certificate", "ssl", "verify", "1007", "cert", "handshake"))

    def connect(self):
        log.info(f"Connecting to Odoo at {self.url} ...")
        self.last_error = ""

        try:
            common = self._create_proxy("/xmlrpc/2/common")
            version = common.version()
        except Exception as e:
            if self._is_ssl_error(e) and not self.use_unverified_ssl:
                log.warning(f"SSL verification failed ({e}), retrying with unverified SSL context...")
                try:
                    self.use_unverified_ssl = True
                    common = self._create_proxy("/xmlrpc/2/common", unverified=True)
                    version = common.version()
                except Exception as ssl_e:
                    self.last_error = f"SSL Certificate Verification Failed: {ssl_e}"
                    log.error(self.last_error)
                    return False
            else:
                self.last_error = f"Cannot reach Odoo server at {self.url}: {e}"
                log.error(self.last_error)
                return False

        self.server_version = version.get("server_version", "unknown")
        log.info(f"Odoo server version: {self.server_version}")

        try:
            self.uid = common.authenticate(self.database, self.username, self.password, {})
        except Exception as e:
            if self._is_ssl_error(e) and not self.use_unverified_ssl:
                log.warning(f"SSL error during authentication ({e}), retrying with unverified SSL context...")
                try:
                    self.use_unverified_ssl = True
                    common = self._create_proxy("/xmlrpc/2/common", unverified=True)
                    self.uid = common.authenticate(self.database, self.username, self.password, {})
                except Exception as ssl_e:
                    self.last_error = f"Authentication SSL Error: {ssl_e}"
                    log.error(self.last_error)
                    return False
            else:
                self.last_error = f"Authentication call failed: {e}"
                log.error(self.last_error)
                return False

        if not self.uid:
            self.last_error = f"Authentication failed for user '{self.username}' on database '{self.database}'. Check database name, username, and password."
            log.error(self.last_error)
            return False

        log.info(f"Authenticated as UID: {self.uid}")
        self.models = self._create_proxy("/xmlrpc/2/object")
        return True

    def execute(self, model, method, *args, **kwargs):
        try:
            return self.models.execute_kw(
                self.database, self.uid, self.password,
                model, method, list(args), kwargs if kwargs else {},
            )
        except Exception as e:
            if self._is_ssl_error(e) and not self.use_unverified_ssl:
                log.warning(f"SSL error during RPC execution ({e}). Switching to unverified SSL context...")
                self.use_unverified_ssl = True
                self.models = self._create_proxy("/xmlrpc/2/object", unverified=True)
                return self.models.execute_kw(
                    self.database, self.uid, self.password,
                    model, method, list(args), kwargs if kwargs else {},
                )
            raise

    def get_pending_jobs(self):
        """Get all pending print jobs from mng.print.queue."""
        ids = self.execute("mng.print.queue", "search",
                           [["state", "=", "pending"]])
        if not ids:
            return []
        return self.execute("mng.print.queue", "read", ids,
                            fields=["id", "name", "pdf_data", "pdf_filename",
                                    "copies", "printer_id", "create_date",
                                    "pages", "page_subset", "duplex",
                                    "orientation", "color_mode", "scaling"])

    def register_printers(self, printers):
        """Register local printers with Odoo so users can choose them."""
        try:
            client_name = socket.gethostname()
            result = self.execute("mng.printer.device", "register_printers",
                                  client_name, printers, client_version=APP_VERSION)
            log.info(f"Registered {len(result)} printer(s) with Odoo")
            return result
        except Exception as e:
            log.error(f"Failed to register printers: {e}")
            return []

    def mark_printed(self, job_id):
        """Mark a job as printed."""
        try:
            self.execute("mng.print.queue", "action_mark_printed", [job_id])
            return True
        except Exception as e:
            log.error(f"Failed to mark job {job_id} as printed: {e}")
            return False

    def mark_failed(self, job_id, error=""):
        """Mark a job as failed."""
        try:
            self.execute("mng.print.queue", "action_mark_failed",
                         [job_id], error=error or "")
        except Exception as e:
            log.error(f"Failed to mark job {job_id}: {e}")

# ──────────────────────────────────────────────────────────────────────
# Printer
# ──────────────────────────────────────────────────────────────────────

def build_print_settings(job):
    """Translate a print-queue job's options into a SumatraPDF -print-settings
    string. Anything left at the printer default is omitted. Copies are handled
    separately (loop in print_pdf), so they're not included here."""
    tokens = []

    pages = (job.get("pages") or "").replace(" ", "")
    if pages:
        tokens.append(pages)

    subset = job.get("page_subset")
    if subset in ("odd", "even"):
        tokens.append(subset)

    duplex = job.get("duplex")
    if duplex in ("simplex", "duplexlong", "duplexshort"):
        tokens.append(duplex)

    orientation = job.get("orientation")
    if orientation in ("portrait", "landscape"):
        tokens.append(orientation)

    color = job.get("color_mode")
    if color in ("color", "monochrome"):
        tokens.append(color)

    scaling = job.get("scaling")
    if scaling in ("fit", "shrink", "noscale"):
        tokens.append(scaling)

    return ",".join(tokens)


class Printer:
    def __init__(self, sumatra_path="", printer_name="", temp_folder="temp_prints"):
        self.printer_name = printer_name.strip()
        self.temp_folder = os.path.join(app_dir(), temp_folder)
        os.makedirs(self.temp_folder, exist_ok=True)
        self.last_error = ""

        # Resolve SumatraPDF: user-specified > bundled > system
        sp = sumatra_path.strip()
        if sp and os.path.exists(sp):
            self.sumatra_path = sp
        else:
            self.sumatra_path = _get_bundled_sumatra() or sp

    def print_pdf(self, pdf_data_b64, filename, copies=1, print_settings=""):
        self.last_error = ""
        try:
            pdf_bytes = base64.b64decode(pdf_data_b64)
        except Exception as e:
            self.last_error = f"Failed to decode base64 file data: {e}"
            log.error(self.last_error)
            return False

        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
        if not safe_name:
            safe_name = f"print_job_{int(time.time())}.pdf"
        file_path = os.path.join(self.temp_folder, safe_name)

        try:
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            log.info(f"Saved: {file_path} ({len(pdf_bytes):,} bytes)")
        except Exception as e:
            self.last_error = f"Failed to save temp file '{safe_name}': {e}"
            log.error(self.last_error)
            return False

        success = True
        num_copies = max(1, copies)
        for i in range(num_copies):
            if i > 0:
                log.info(f"→ Printing copy {i+1} of {num_copies}...")
            if not self._send_to_printer(file_path, print_settings):
                success = False
                break
            # Small delay between copies to avoid printer queue congestion
            if num_copies > 1 and i < num_copies - 1:
                time.sleep(0.5)

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        return success

    def _send_to_printer(self, path, print_settings=""):
        ext = os.path.splitext(path)[1].lower()
        sumatra_supported = ext in (
            ".pdf", ".xps", ".cbz", ".cbr", ".djvu", ".chm",
            ".epub", ".mobi", ".png", ".jpg", ".jpeg", ".bmp",
            ".gif", ".webp", ".tiff"
        )

        if self.sumatra_path and os.path.exists(self.sumatra_path) and sumatra_supported:
            if self._print_sumatra(path, print_settings):
                return True

        if sys.platform == "win32":
            if self._print_shell(path):
                return True

        if not sumatra_supported and sys.platform != "win32":
            if self._print_cups(path):
                return True
            self.last_error = f"Unsupported format '{ext}' for silent printing on Linux. Convert file to PDF or Image before sending."
            log.error(self.last_error)
            return False

        if self.sumatra_path and os.path.exists(self.sumatra_path) and not sumatra_supported:
            self.last_error = f"SumatraPDF cannot print '{ext}' files. Please convert to PDF or Image (.pdf, .jpg, .png) before queuing."
            log.error(self.last_error)
            return False

        return self._print_cups(path) if sys.platform != "win32" else False

    def _print_sumatra(self, path, print_settings=""):
        try:
            cmd = [self.sumatra_path]
            if self.printer_name:
                cmd += ["-print-to", self.printer_name]
            else:
                cmd += ["-print-to-default"]
            if print_settings:
                cmd += ["-print-settings", print_settings]
            cmd += ["-silent", path]
            log.info(f"Printing: {os.path.basename(path)}"
                     + (f" [{print_settings}]" if print_settings else ""))
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                log.info(f"✓ Printed: {os.path.basename(path)}")
                return True
            err_msg = (r.stderr or "").strip() or f"Exit code {r.returncode}"
            self.last_error = f"SumatraPDF error: {err_msg}"
            log.error(self.last_error)
            return False
        except subprocess.TimeoutExpired:
            self.last_error = "Print timeout (60s exceeded)"
            log.error(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"Print error: {e}"
            log.error(self.last_error)
            return False

    def _print_shell(self, path):
        try:
            log.info(f"Printing via Windows shell: {os.path.basename(path)}")
            os.startfile(path, "print")
            time.sleep(5)
            log.info(f"✓ Sent to Windows printer shell: {os.path.basename(path)}")
            return True
        except Exception as e:
            self.last_error = f"Windows shell print error: {e}"
            log.error(self.last_error)
            return False

    def _print_cups(self, path):
        """Print via CUPS (Linux/macOS)."""
        try:
            cmd = ["lp"]
            if self.printer_name:
                cmd += ["-d", self.printer_name]
            cmd.append(path)
            log.info(f"Printing via CUPS: {os.path.basename(path)}")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                log.info(f"✓ Printed: {os.path.basename(path)}")
                return True
            err_msg = (r.stderr or "").strip() or f"Exit code {r.returncode}"
            self.last_error = f"CUPS error: {err_msg}"
            log.error(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"CUPS print error: {e}"
            log.error(self.last_error)
            return False

# ──────────────────────────────────────────────────────────────────────
# Bridge Engine
# ──────────────────────────────────────────────────────────────────────

class BridgeEngine:
    def __init__(self, odoo_url, database, username, password,
                 sumatra_path, printer_name, poll_interval,
                 message_queue):
        self.odoo = OdooConnection(odoo_url, database, username, password)
        self.default_printer = Printer(sumatra_path, printer_name)
        self.sumatra_path = sumatra_path
        self.poll_interval = poll_interval
        self.msg = message_queue
        self.running = False
        self.jobs_printed = 0
        self.start_time = None
        self._thread = None

    def _emit(self, t, d):
        self.msg.put((t, d))

    def test_connection(self):
        if not self.odoo.connect():
            err_msg = self.odoo.last_error or "Check URL, database, and credentials."
            return False, f"Connection failed: {err_msg}"
        try:
            jobs = self.odoo.get_pending_jobs()
            return True, (
                f"Connected to Odoo {self.odoo.server_version}\n"
                f"MNG Print Bridge module detected ✓\n"
                f"Pending jobs in queue: {len(jobs)}"
            )
        except xmlrpc.client.Fault as e:
            if "mng.print.queue" in str(e):
                return False, (
                    "Connected to Odoo but the MNG Print Bridge module\n"
                    "is NOT installed on the server.\n\n"
                    "Install it: Apps → Update Apps List → search 'MNG Print Bridge'"
                )
            return False, f"Odoo API error: {e.faultString}"
        except Exception as e:
            return False, f"Error: {e}"

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _connect_with_retry(self, is_reconnect=False):
        """Connect to Odoo with exponential backoff. Returns True when connected, False if engine stopped."""
        delays = [5, 10, 30, 60, 120]
        attempt = 0
        label = "Re-connecting" if is_reconnect else "Connecting"
        while self.running:
            if self.odoo.connect():
                return True
            wait = delays[min(attempt, len(delays) - 1)]
            attempt += 1
            self._emit("warning", f"{label} to Odoo failed (attempt {attempt}). Retrying in {wait}s...")
            self._emit("status", "reconnecting")
            for _ in range(wait * 2):
                if not self.running:
                    return False
                time.sleep(0.5)
        return False

    def _run(self):
        self.start_time = datetime.now()
        self._emit("status", "connecting")

        if not self._connect_with_retry():
            self._emit("status", "stopped")
            self._emit("engine_stopped", None)
            return

        self._emit("log", f"Connected to Odoo {self.odoo.server_version}")

        try:
            self.odoo.get_pending_jobs()
            self._emit("log", "MNG Print Bridge module detected ✓")
        except Exception:
            self._emit("error", "MNG Print Bridge module not installed on Odoo!")
            self._emit("status", "disconnected")
            self._emit("engine_stopped", None)
            return

        # Register local printers with Odoo
        try:
            printers = discover_printers()
            if printers:
                registered = self.odoo.register_printers(printers)
                self._emit("log", f"Registered {len(registered)} printer(s) with Odoo")
            else:
                self._emit("warning", "No local printers found to register")
        except Exception as e:
            self._emit("warning", f"Could not register printers: {e}")

        self._emit("status", "polling")
        self._emit("log", f"Polling every {self.poll_interval}s ...")

        poll_count = 0
        consecutive_errors = 0
        last_update_check = time.time()
        while self.running:
            # Re-register printers every 30 polls (~5 min at 10s interval)
            if poll_count > 0 and poll_count % 30 == 0:
                try:
                    printers = discover_printers()
                    if printers:
                        self.odoo.register_printers(printers)
                except Exception:
                    pass
            poll_count += 1
            try:
                self._check_for_jobs()
                consecutive_errors = 0
                # Idle moment (jobs done synchronously above): safe to self-update.
                if time.time() - last_update_check >= UPDATE_CHECK_INTERVAL:
                    last_update_check = time.time()
                    if check_for_update():
                        self._emit("log", "Шинэчлэл татаж байна — програм дахин эхэлнэ...")
                        time.sleep(1)
                        os._exit(0)  # updater .bat swaps the .exe and relaunches
            except xmlrpc.client.Fault as e:
                consecutive_errors += 1
                self._emit("error", f"Odoo API error: {e.faultString}")
            except (ConnectionError, OSError) as e:
                consecutive_errors += 1
                self._emit("warning", f"Connection lost: {e}")
                self._emit("status", "reconnecting")
            except Exception as e:
                consecutive_errors += 1
                self._emit("error", f"Error: {e}")

            # After 3 consecutive failures, force a full re-connect
            if consecutive_errors >= 3:
                self._emit("warning", "Persistent errors — re-connecting to Odoo...")
                if not self._connect_with_retry(is_reconnect=True):
                    break
                consecutive_errors = 0
                self._emit("status", "polling")
                self._emit("log", "Reconnected to Odoo ✓")

            for _ in range(self.poll_interval * 2):
                if not self.running:
                    break
                time.sleep(0.5)

        self._emit("status", "stopped")
        self._emit("log", f"Stopped. Total printed: {self.jobs_printed}")
        self._emit("engine_stopped", None)

    def _get_printer_for_job(self, job):
        """Get a Printer instance for this job — uses the Odoo-selected printer or fallback."""
        printer_id = job.get("printer_id")
        if printer_id and isinstance(printer_id, (list, tuple)) and len(printer_id) >= 2:
            # printer_id is [id, "Printer Name (computer)"] from Odoo Many2one
            # Extract just the printer name (before the parentheses)
            selected_name = printer_id[1].split(" (")[0].strip()
            if selected_name and selected_name != "★":
                return Printer(self.sumatra_path, selected_name)
        return self.default_printer

    def _check_for_jobs(self):
        jobs = self.odoo.get_pending_jobs()
        if not jobs:
            self._emit("status", "polling")
            return

        self._emit("log", f"Found {len(jobs)} job(s)!")
        for job in jobs:
            if not self.running:
                break
            job_id = job["id"]
            name = job.get("pdf_filename") or job.get("name", "unknown.pdf")
            self._emit("status", "printing")
            self._emit("log", f"Printing: {name}")

            data = job.get("pdf_data")
            if not data:
                self._emit("warning", f"{name} has no data")
                self.odoo.mark_failed(job_id, "No PDF data")
                continue

            printer = self._get_printer_for_job(job)
            copies = job.get("copies", 1) or 1
            print_settings = build_print_settings(job)
            if printer.printer_name:
                self._emit("log", f"→ Using printer: {printer.printer_name} ({copies} copies)")
            if print_settings:
                self._emit("log", f"→ Print options: {print_settings}")

            if printer.print_pdf(data, name, copies=copies, print_settings=print_settings):
                if self.odoo.mark_printed(job_id):
                    self.jobs_printed += 1
                    copy_str = f" ({copies} copies)" if copies > 1 else ""
                    self._emit("success", f"✓ Printed: {name}{copy_str}")
                    self._emit("jobs_count", self.jobs_printed)
                else:
                    self._emit("warning", f"Printed but status update failed: {name}")
            else:
                self._emit("error", f"✗ Failed: {name}")
                self.odoo.mark_failed(job_id, "Print command failed")
        self._emit("status", "polling")

# ──────────────────────────────────────────────────────────────────────
# GUI Application
# ──────────────────────────────────────────────────────────────────────

def run_gui(start_minimized=False):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    # ── Resolve paths (works both from source and as .exe) ──
    icon_path = resource_path(ICON_FILE)
    config_path = CONFIG_FILE  # already resolved to app_dir()

    # ── Window ──
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("760x750")
    root.minsize(680, 650)
    root.configure(bg=COLOR_BG)

    # Prevent the console window from appearing on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass

    # Icon
    try:
        if os.path.exists(icon_path):
            _icon = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, _icon)
    except Exception:
        pass

    # ── Scrollable main area ──
    main_canvas = tk.Canvas(root, bg=COLOR_BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
    scroll_frame = tk.Frame(main_canvas, bg=COLOR_BG)

    scroll_frame.bind("<Configure>",
                      lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
    main_canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    main_canvas.configure(yscrollcommand=scrollbar.set)

    # Mouse wheel scrolling
    def _on_mousewheel(event):
        main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    def _on_mousewheel_linux(event):
        if event.num == 4:
            main_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            main_canvas.yview_scroll(1, "units")

    main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    main_canvas.bind_all("<Button-4>", _on_mousewheel_linux)
    main_canvas.bind_all("<Button-5>", _on_mousewheel_linux)

    scrollbar.pack(side="right", fill="y")
    main_canvas.pack(side="left", fill="both", expand=True)

    # Make scroll_frame expand to canvas width
    def _configure_frame_width(event):
        main_canvas.itemconfig(main_canvas.find_all()[0], width=event.width)
    main_canvas.bind("<Configure>", _configure_frame_width)

    # ── Shared state ──
    msg_queue = queue.Queue()
    engine_ref = [None]
    config = load_config(config_path)
    discovered_printers = []

    # ── Helper: create styled entry ──
    def make_entry(parent, var, show=None, **kw):
        e = tk.Entry(parent, textvariable=var, font=("Segoe UI", 10),
                     bg=COLOR_INPUT_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
                     relief="flat", highlightthickness=1,
                     highlightbackground=COLOR_BORDER, highlightcolor=COLOR_ACCENT,
                     disabledbackground="#1e293b", disabledforeground=COLOR_TEXT_DIM,
                     **kw)
        if show:
            e.config(show=show)
        return e

    def make_label(parent, text, **kw):
        return tk.Label(parent, text=text, bg=COLOR_BG_CARD, fg=COLOR_TEXT,
                        font=("Segoe UI", 10), **kw)

    def make_card(parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD,
                        highlightbackground=COLOR_BORDER, highlightthickness=1, bd=0)
        card.pack(fill="x", padx=20, pady=(0, 10))
        inner = tk.Frame(card, bg=COLOR_BG_CARD)
        inner.pack(fill="x", padx=16, pady=12)
        return card, inner

    def make_card_title(parent, icon, text):
        tk.Label(parent, text=f"{icon}  {text}", bg=COLOR_BG_CARD,
                 fg=COLOR_ACCENT, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

    # ════════════════════════════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════════════════════════════
    header = tk.Frame(scroll_frame, bg=COLOR_BG)
    header.pack(fill="x", padx=20, pady=(15, 5))

    header_logo = None
    try:
        if os.path.exists(icon_path):
            _raw = tk.PhotoImage(file=icon_path)
            factor = max(1, _raw.width() // 36)
            header_logo = _raw.subsample(factor, factor)
    except Exception:
        pass

    if header_logo:
        lbl = tk.Label(header, image=header_logo, bg=COLOR_BG)
        lbl.image = header_logo
        lbl.pack(side="left", padx=(0, 10))

    tk.Label(header, text=APP_NAME, bg=COLOR_BG, fg=COLOR_TEXT,
             font=("Segoe UI", 18, "bold")).pack(side="left")
    tk.Label(header, text=f"v{APP_VERSION}", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
             font=("Segoe UI", 9)).pack(side="left", padx=(8, 0), pady=(6, 0))

    tk.Frame(scroll_frame, height=1, bg=COLOR_BORDER).pack(fill="x", padx=20, pady=(8, 12))

    # ════════════════════════════════════════════════════════════════════
    # ODOO CONNECTION CARD
    # ════════════════════════════════════════════════════════════════════
    _, odoo_inner = make_card(scroll_frame)
    make_card_title(odoo_inner, "⚡", "Odoo Connection")

    _cv = lambda s, k, fb="": config.get(s, k, fallback=fb) if config else fb

    make_label(odoo_inner, "Server URL:").grid(row=1, column=0, sticky="w", pady=3)
    url_var = tk.StringVar(value=_cv("odoo", "url", "https://"))
    url_entry = make_entry(odoo_inner, url_var)
    url_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=3, padx=(8, 0))

    make_label(odoo_inner, "Database:").grid(row=2, column=0, sticky="w", pady=3)
    db_var = tk.StringVar(value=_cv("odoo", "database"))
    db_entry = make_entry(odoo_inner, db_var)
    db_entry.grid(row=2, column=1, columnspan=3, sticky="ew", pady=3, padx=(8, 0))

    make_label(odoo_inner, "Username:").grid(row=3, column=0, sticky="w", pady=3)
    user_var = tk.StringVar(value=_cv("odoo", "username"))
    user_entry = make_entry(odoo_inner, user_var)
    user_entry.grid(row=3, column=1, columnspan=3, sticky="ew", pady=3, padx=(8, 0))

    make_label(odoo_inner, "Password:").grid(row=4, column=0, sticky="w", pady=3)
    pass_var = tk.StringVar(value=_cv("odoo", "password"))
    pass_entry = make_entry(odoo_inner, pass_var, show="•")
    pass_entry.grid(row=4, column=1, columnspan=3, sticky="ew", pady=3, padx=(8, 0))

    odoo_inner.columnconfigure(1, weight=1)

    # ════════════════════════════════════════════════════════════════════
    # PRINTER SETTINGS CARD
    # ════════════════════════════════════════════════════════════════════
    _, pr_inner = make_card(scroll_frame)
    make_card_title(pr_inner, "🖨️", "Printer Selection")

    # ── Printer dropdown ──
    make_label(pr_inner, "Printer:").grid(row=1, column=0, sticky="w", pady=3)

    printer_var = tk.StringVar(value=_cv("printer", "printer_name"))
    printer_combo = ttk.Combobox(pr_inner, textvariable=printer_var,
                                  font=("Segoe UI", 10), state="readonly")
    printer_combo.grid(row=1, column=1, sticky="ew", pady=3, padx=(8, 4))

    # Style the combobox for dark theme
    root.option_add("*TCombobox*Listbox*Background", COLOR_INPUT_BG)
    root.option_add("*TCombobox*Listbox*Foreground", COLOR_TEXT)
    root.option_add("*TCombobox*Listbox*selectBackground", COLOR_ACCENT)
    root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox*Font", ("Segoe UI", 10))

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TCombobox",
                     fieldbackground=COLOR_INPUT_BG, background=COLOR_BG_LIGHT,
                     foreground=COLOR_TEXT, selectbackground=COLOR_ACCENT,
                     selectforeground="#ffffff", arrowcolor=COLOR_ACCENT)
    style.map("TCombobox",
              fieldbackground=[("readonly", COLOR_INPUT_BG)],
              foreground=[("readonly", COLOR_TEXT)])

    # Printer info label
    printer_info_var = tk.StringVar(value="")
    printer_info = tk.Label(pr_inner, textvariable=printer_info_var,
                             bg=COLOR_BG_CARD, fg=COLOR_TEXT_DIM,
                             font=("Segoe UI", 8), anchor="w")
    printer_info.grid(row=2, column=1, columnspan=2, sticky="w", padx=(8, 0))

    def refresh_printers():
        """Scan for available printers and populate dropdown."""
        nonlocal discovered_printers
        refresh_btn.config(state="disabled", text="Scanning...")
        root.update()

        def _scan():
            printers = discover_printers()
            msg_queue.put(("printers_found", printers))

        threading.Thread(target=_scan, daemon=True).start()

    def _populate_printer_list(printers):
        nonlocal discovered_printers
        discovered_printers = printers

        saved_name = printer_var.get()
        names = []
        default_name = ""

        for p in printers:
            display = p["name"]
            if p.get("default"):
                display += "  ★ default"
                default_name = p["name"]
            if p.get("port"):
                display += f"  ({p['port']})"
            names.append(display)

        # Add "System Default" option at top
        choices = ["(System Default Printer)"] + names
        printer_combo["values"] = choices

        # Select saved printer or default
        if saved_name:
            for i, p in enumerate(printers):
                if p["name"] == saved_name:
                    printer_combo.current(i + 1)
                    break
            else:
                printer_combo.current(0)
        else:
            printer_combo.current(0)

        count = len(printers)
        printer_info_var.set(
            f"{count} printer(s) found" + (f" — default: {default_name}" if default_name else "")
        )
        refresh_btn.config(state="normal", text="🔄 Refresh")

    def on_printer_select(event=None):
        """When user picks a printer from dropdown, store the raw name."""
        idx = printer_combo.current()
        if idx <= 0:
            printer_var.set("")  # System default
        else:
            printer_var.set(discovered_printers[idx - 1]["name"])

    printer_combo.bind("<<ComboboxSelected>>", on_printer_select)

    refresh_btn = tk.Button(pr_inner, text="🔄 Refresh", command=refresh_printers,
                             bg=COLOR_BG_LIGHT, fg=COLOR_TEXT, relief="flat",
                             font=("Segoe UI", 9), cursor="hand2",
                             activebackground=COLOR_ACCENT, activeforeground="white",
                             padx=8, pady=2)
    refresh_btn.grid(row=1, column=2, pady=3, padx=(0, 0))

    # ── SumatraPDF path ──
    make_label(pr_inner, "SumatraPDF:").grid(row=3, column=0, sticky="w", pady=3)
    sumatra_var = tk.StringVar(value=_cv("printer", "sumatra_path"))
    sumatra_entry = make_entry(pr_inner, sumatra_var)
    sumatra_entry.grid(row=3, column=1, sticky="ew", pady=3, padx=(8, 4))

    def browse_sumatra():
        p = filedialog.askopenfilename(
            title="Select SumatraPDF.exe",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")])
        if p:
            sumatra_var.set(p)

    browse_btn = tk.Button(pr_inner, text="📂", command=browse_sumatra,
                            bg=COLOR_BG_LIGHT, fg=COLOR_TEXT, relief="flat",
                            font=("Segoe UI", 10), cursor="hand2",
                            activebackground=COLOR_ACCENT)
    browse_btn.grid(row=3, column=2, pady=3)

    tk.Label(pr_inner, text="For silent printing (no window flash). Leave blank to use OS default.",
             bg=COLOR_BG_CARD, fg=COLOR_TEXT_DIM,
             font=("Segoe UI", 8)).grid(row=4, column=1, columnspan=2, sticky="w", padx=(8, 0))

    # ── Poll interval ──
    make_label(pr_inner, "Poll Interval:").grid(row=5, column=0, sticky="w", pady=3)
    poll_frame = tk.Frame(pr_inner, bg=COLOR_BG_CARD)
    poll_frame.grid(row=5, column=1, columnspan=2, sticky="w", pady=3, padx=(8, 0))

    poll_var = tk.StringVar(value=_cv("settings", "poll_interval", "10"))
    poll_entry = make_entry(poll_frame, poll_var, width=6)
    poll_entry.pack(side="left")
    tk.Label(poll_frame, text="seconds", bg=COLOR_BG_CARD, fg=COLOR_TEXT_DIM,
             font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

    pr_inner.columnconfigure(1, weight=1)

    # ════════════════════════════════════════════════════════════════════
    # BACKGROUND SERVICE CARD
    # ════════════════════════════════════════════════════════════════════
    _, svc_inner = make_card(scroll_frame)
    make_card_title(svc_inner, "⚙️", "Background Service")

    # ── Auto-start on Windows boot ──
    autostart_var = tk.BooleanVar(value=get_autostart_enabled(config_path))

    def _toggle_autostart():
        enabled = autostart_var.get()
        ok, err = set_autostart_enabled(enabled)
        if not ok:
            append_log(f"Auto-start registry write failed: {err}", "error")
            from tkinter import messagebox
            messagebox.showerror(
                "Auto-Start Error",
                f"Could not write to Windows registry:\n{err}\n\n"
                "The setting was saved to config.ini as a fallback."
            )
        # Always persist to config.ini so checkbox state survives
        try:
            poll = int(poll_var.get())
        except (ValueError, NameError):
            poll = 10
        save_config(config_path,
                    url_var.get(), db_var.get(), user_var.get(), pass_var.get(),
                    sumatra_var.get(), _get_printer_name(), poll,
                    autostart=enabled, minimize_to_tray=tray_var.get())
        append_log(f"Auto-start {'enabled' if enabled else 'disabled'} ✓", "success")

    autostart_chk = tk.Checkbutton(
        svc_inner, text="Start automatically when PC turns on",
        variable=autostart_var, bg=COLOR_BG_CARD, fg=COLOR_TEXT,
        activebackground=COLOR_BG_CARD, activeforeground=COLOR_TEXT,
        selectcolor=COLOR_INPUT_BG, font=("Segoe UI", 10),
        command=_toggle_autostart,
    )
    autostart_chk.grid(row=1, column=0, columnspan=4, sticky="w", pady=3)

    # ── Minimize to tray on close ──
    _tray_default = True
    if config:
        _tray_default = config.getboolean("settings", "minimize_to_tray", fallback=True)
    tray_var = tk.BooleanVar(value=_tray_default)
    tray_chk = tk.Checkbutton(
        svc_inner, text="Minimize to system tray when window is closed",
        variable=tray_var, bg=COLOR_BG_CARD, fg=COLOR_TEXT,
        activebackground=COLOR_BG_CARD, activeforeground=COLOR_TEXT,
        selectcolor=COLOR_INPUT_BG, font=("Segoe UI", 10),
    )
    tray_chk.grid(row=2, column=0, columnspan=4, sticky="w", pady=3)

    tk.Label(svc_inner,
             text="When enabled, closing the window keeps the printer bridge running in the background.",
             bg=COLOR_BG_CARD, fg=COLOR_TEXT_DIM,
             font=("Segoe UI", 8), wraplength=500, justify="left",
    ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(0, 4))

    # ════════════════════════════════════════════════════════════════════
    # CONTROLS
    # ════════════════════════════════════════════════════════════════════
    ctrl_frame = tk.Frame(scroll_frame, bg=COLOR_BG)
    ctrl_frame.pack(fill="x", padx=20, pady=(2, 6))

    status_var = tk.StringVar(value="● Idle")
    status_lbl = tk.Label(ctrl_frame, textvariable=status_var,
                           bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                           font=("Segoe UI", 10, "bold"))
    status_lbl.pack(side="left")

    jobs_var = tk.StringVar(value="Jobs: 0")
    tk.Label(ctrl_frame, textvariable=jobs_var, bg=COLOR_BG, fg=COLOR_ACCENT,
             font=("Segoe UI", 10, "bold")).pack(side="right")

    uptime_var = tk.StringVar(value="")
    tk.Label(ctrl_frame, textvariable=uptime_var, bg=COLOR_BG, fg=COLOR_TEXT_DIM,
             font=("Segoe UI", 9)).pack(side="right", padx=(0, 16))

    btn_frame = tk.Frame(scroll_frame, bg=COLOR_BG)
    btn_frame.pack(fill="x", padx=20, pady=(0, 10))

    # All widgets that should be locked when running
    form_widgets = []  # populated after all widgets are created

    def _get_printer_name():
        """Get the actual printer name from the combo selection."""
        idx = printer_combo.current()
        if idx <= 0 or not discovered_printers:
            return ""
        return discovered_printers[idx - 1]["name"]

    def _save():
        try:
            poll = int(poll_var.get())
        except ValueError:
            poll = 10
        pname = _get_printer_name()
        save_config(config_path,
                     url_var.get(), db_var.get(), user_var.get(), pass_var.get(),
                     sumatra_var.get(), pname, poll,
                     autostart=autostart_var.get(),
                     minimize_to_tray=tray_var.get())
        append_log("Settings saved ✓", "success")

    def on_test():
        _save()
        test_btn.config(state="disabled", text="Testing...")
        root.update()
        def _t():
            odoo = OdooConnection(url_var.get(), db_var.get(), user_var.get(), pass_var.get())
            try:
                if not odoo.connect():
                    err_msg = odoo.last_error or "Check URL, database, and credentials."
                    msg_queue.put(("test_result", (False, f"Connection failed: {err_msg}")))
                    return
                try:
                    jobs = odoo.get_pending_jobs()
                    msg_queue.put(("test_result", (True,
                        f"Connected to Odoo {odoo.server_version}\n"
                        f"MNG Print Bridge module detected ✓\n"
                        f"Pending jobs: {len(jobs)}")))
                except xmlrpc.client.Fault as ef:
                    if "mng.print.queue" in str(ef):
                        msg_queue.put(("test_result", (False,
                            "Connected but MNG Print Bridge module\n"
                            "is NOT installed on the server.")))
                    else:
                        msg_queue.put(("test_result", (False, str(ef))))
            except Exception as e:
                msg_queue.put(("test_result", (False, str(e))))
        threading.Thread(target=_t, daemon=True).start()

    def on_start():
        _save()
        if not url_var.get().strip() or not db_var.get().strip():
            if not start_minimized:
                messagebox.showwarning("Missing Info", "Please fill in the Odoo connection details.")
            append_log("Cannot start: Odoo URL / database not configured.", "error")
            return
        if not user_var.get().strip() or not pass_var.get().strip():
            if not start_minimized:
                messagebox.showwarning("Missing Info", "Please enter username and password.")
            append_log("Cannot start: username / password not configured.", "error")
            return

        try:
            poll = int(poll_var.get())
        except ValueError:
            poll = 10

        pname = _get_printer_name()
        engine_ref[0] = BridgeEngine(
            url_var.get(), db_var.get(), user_var.get(), pass_var.get(),
            sumatra_var.get(), pname, poll, msg_queue,
        )
        engine_ref[0].start()

        for w in form_widgets:
            try:
                w.config(state="disabled")
            except Exception:
                pass
        start_btn.pack_forget()
        stop_btn.pack(side="right", padx=(8, 0))
        test_btn.config(state="disabled")

    def on_stop():
        if engine_ref[0]:
            engine_ref[0].stop()
        for w in form_widgets:
            try:
                w.config(state="normal")
            except Exception:
                w.config(state="readonly")
        stop_btn.pack_forget()
        start_btn.pack(side="right", padx=(8, 0))
        test_btn.config(state="normal")
        status_var.set("● Idle")
        status_lbl.config(fg=COLOR_TEXT_DIM)

    def make_btn(parent, text, cmd, bg_color, fg="white", bold=False, **kw):
        f = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
        return tk.Button(parent, text=text, command=cmd,
                          bg=bg_color, fg=fg, relief="flat", font=f,
                          cursor="hand2", activebackground=bg_color,
                          activeforeground=fg, padx=14, pady=6, **kw)

    test_btn = make_btn(btn_frame, "🔍 Test Connection", on_test, COLOR_PURPLE)
    test_btn.pack(side="left")

    start_btn = make_btn(btn_frame, "▶  Start Printing", on_start, COLOR_SUCCESS, bold=True)
    start_btn.pack(side="right", padx=(8, 0))

    stop_btn = make_btn(btn_frame, "■  Stop", on_stop, COLOR_ERROR, bold=True)
    # hidden initially

    save_btn = make_btn(btn_frame, "💾 Save", _save, COLOR_BG_LIGHT, COLOR_TEXT)
    save_btn.pack(side="right", padx=(8, 0))

    # Collect form widgets for locking
    form_widgets = [url_entry, db_entry, user_entry, pass_entry,
                    sumatra_entry, poll_entry, browse_btn, refresh_btn,
                    printer_combo]

    # ════════════════════════════════════════════════════════════════════
    # ACTIVITY LOG CARD
    # ════════════════════════════════════════════════════════════════════
    log_card = tk.Frame(scroll_frame, bg=COLOR_BG_CARD,
                         highlightbackground=COLOR_BORDER, highlightthickness=1, bd=0)
    log_card.pack(fill="both", expand=True, padx=20, pady=(0, 15))

    log_hdr = tk.Frame(log_card, bg=COLOR_BG_CARD)
    log_hdr.pack(fill="x", padx=16, pady=(12, 4))

    tk.Label(log_hdr, text="📋  Activity Log", bg=COLOR_BG_CARD,
             fg=COLOR_ACCENT, font=("Segoe UI", 11, "bold")).pack(side="left")

    def clear_log():
        log_text.config(state="normal")
        log_text.delete("1.0", "end")
        log_text.config(state="disabled")

    tk.Button(log_hdr, text="Clear", command=clear_log,
              bg=COLOR_BG_LIGHT, fg=COLOR_TEXT_DIM, relief="flat",
              font=("Segoe UI", 8), cursor="hand2",
              activebackground=COLOR_BORDER).pack(side="right")

    log_text = tk.Text(log_card, height=12, bg=COLOR_INPUT_BG, fg=COLOR_TEXT,
                        font=("Consolas", 9), relief="flat", wrap="word",
                        insertbackground=COLOR_TEXT, state="disabled",
                        selectbackground=COLOR_ACCENT, selectforeground="white",
                        padx=8, pady=8)
    log_text.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    for tag, color in [("success", COLOR_SUCCESS), ("error", COLOR_ERROR),
                        ("warning", COLOR_WARNING), ("info", COLOR_TEXT),
                        ("dim", COLOR_TEXT_DIM), ("timestamp", COLOR_TEXT_DIM)]:
        log_text.tag_configure(tag, foreground=color)

    def append_log(message, tag="info"):
        log_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        log_text.insert("end", f"[{ts}] ", "timestamp")
        log_text.insert("end", f"{message}\n", tag)
        log_text.see("end")
        log_text.config(state="disabled")

    append_log(f"{APP_NAME} v{APP_VERSION}", "dim")
    append_log("Scanning for printers...", "dim")

    # ════════════════════════════════════════════════════════════════════
    # MESSAGE PROCESSING LOOP (GUI thread)
    # ════════════════════════════════════════════════════════════════════

    STATUS_DISPLAY = {
        "connecting":   ("● Connecting...", COLOR_WARNING),
        "polling":      ("● Connected — Polling", COLOR_SUCCESS),
        "printing":     ("● Printing...", COLOR_ACCENT),
        "reconnecting": ("● Reconnecting...", COLOR_WARNING),
        "stopped":      ("● Stopped", COLOR_TEXT_DIM),
        "disconnected": ("● Disconnected", COLOR_ERROR),
    }

    def tick():
        try:
            while True:
                t, d = msg_queue.get_nowait()
                if t == "log":
                    append_log(d, "info")
                elif t == "success":
                    append_log(d, "success")
                elif t == "error":
                    append_log(d, "error")
                elif t == "warning":
                    append_log(d, "warning")
                elif t == "status":
                    disp = STATUS_DISPLAY.get(d, (f"● {d}", COLOR_TEXT_DIM))
                    status_var.set(disp[0])
                    status_lbl.config(fg=disp[1])
                elif t == "jobs_count":
                    jobs_var.set(f"Jobs: {d}")
                elif t == "test_result":
                    ok, msg = d
                    test_btn.config(state="normal", text="🔍 Test Connection")
                    if ok:
                        messagebox.showinfo("Connection Test", f"✅ Success!\n\n{msg}")
                        append_log("Connection test passed ✓", "success")
                    else:
                        messagebox.showerror("Connection Test", f"❌ Failed\n\n{msg}")
                        append_log(f"Test failed: {msg}", "error")
                elif t == "printers_found":
                    _populate_printer_list(d)
                    if d:
                        append_log(f"Found {len(d)} printer(s)", "success")
                    else:
                        append_log("No printers found", "warning")
                elif t == "engine_stopped":
                    on_stop()
                    if start_minimized:
                        append_log("Auto-restarting in 30s...", "warning")
                        def _auto_restart():
                            if not (engine_ref[0] and engine_ref[0].running):
                                on_start()
                        root.after(30000, _auto_restart)
        except queue.Empty:
            pass

        if engine_ref[0] and engine_ref[0].running and engine_ref[0].start_time:
            e = datetime.now() - engine_ref[0].start_time
            h, rem = divmod(int(e.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            uptime_var.set(f"Uptime: {h:02d}:{m:02d}:{s:02d}")

        root.after(200, tick)

    tick()

    # Auto-scan printers on startup
    refresh_printers()

    # ── System tray icon ──
    tray_icon_ref = [None]

    def _build_tray_icon():
        if not HAS_PYSTRAY:
            return None
        try:
            img = PilImage.open(resource_path(ICON_FILE)).resize((64, 64))
        except Exception:
            img = PilImage.new("RGBA", (64, 64), (80, 50, 140, 255))

        def _on_show(icon, _item):
            icon.stop()
            tray_icon_ref[0] = None
            root.after(0, _show_from_tray)

        def _on_quit(icon, _item):
            icon.stop()
            tray_icon_ref[0] = None
            if engine_ref[0] and engine_ref[0].running:
                engine_ref[0].stop()
            root.after(0, root.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("MNG Printer Bridge", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Window", _on_show, default=True),
            pystray.MenuItem("Quit", _on_quit),
        )
        return pystray.Icon("MNGPrinterBridge", img, "MNG Printer Bridge", menu)

    def _minimize_to_tray():
        root.withdraw()
        append_log("Minimized to tray. Still printing!", "dim")
        if HAS_PYSTRAY and tray_icon_ref[0] is None:
            icon = _build_tray_icon()
            if icon:
                tray_icon_ref[0] = icon
                threading.Thread(target=icon.run, daemon=True).start()

    def _show_from_tray():
        root.deiconify()
        root.lift()
        root.focus_force()

    def on_close():
        is_running = engine_ref[0] and engine_ref[0].running
        if is_running and tray_var.get():
            _minimize_to_tray()
        elif is_running:
            if messagebox.askyesno("Quit", "Printer bridge is running.\nStop and exit?"):
                if tray_icon_ref[0]:
                    tray_icon_ref[0].stop()
                engine_ref[0].stop()
                time.sleep(0.5)
                root.destroy()
        else:
            if tray_icon_ref[0]:
                tray_icon_ref[0].stop()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # Center window on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")

    # ── Auto-start if launched with --minimized (e.g. on boot) ──
    if start_minimized and config:
        # Hide window immediately so it doesn't flash on screen at boot.
        root.withdraw()
        # Build tray icon now so it's visible right away.
        if HAS_PYSTRAY and tray_icon_ref[0] is None:
            _tray = _build_tray_icon()
            if _tray:
                tray_icon_ref[0] = _tray
                threading.Thread(target=_tray.run, daemon=True).start()
        # Kick off printing after UI is fully initialized.
        root.after(1500, on_start)

    root.mainloop()


# ──────────────────────────────────────────────────────────────────────
# Headless / Test modes
# ──────────────────────────────────────────────────────────────────────

def run_headless(config_path):
    config = load_config(config_path)
    if not config:
        log.error(f"Config not found: {config_path}")
        sys.exit(1)

    mq = queue.Queue()
    eng = BridgeEngine(
        config.get("odoo", "url"), config.get("odoo", "database"),
        config.get("odoo", "username"), config.get("odoo", "password"),
        config.get("printer", "sumatra_path", fallback=""),
        config.get("printer", "printer_name", fallback=""),
        config.getint("settings", "poll_interval", fallback=10),
        mq,
    )
    signal.signal(signal.SIGINT, lambda s, f: eng.stop())
    signal.signal(signal.SIGTERM, lambda s, f: eng.stop())

    print(f"\n{'='*56}\n  🖨️  {APP_NAME} (headless)\n{'='*56}\n  Ctrl+C to stop\n")
    eng.start()
    try:
        while eng.running or not mq.empty():
            try:
                t, d = mq.get(timeout=1)
                if t in ("success", "error", "warning", "log", "status"):
                    print(f"  [{t.upper():7s}] {d}")
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        eng.stop()
        time.sleep(1)
    print(f"\n  Total printed: {eng.jobs_printed}\n")


def run_test(config_path):
    config = load_config(config_path)
    if not config:
        log.error(f"Config not found: {config_path}")
        sys.exit(1)
    mq = queue.Queue()
    eng = BridgeEngine(
        config.get("odoo", "url"), config.get("odoo", "database"),
        config.get("odoo", "username"), config.get("odoo", "password"),
        "", "", 10, mq,
    )
    print("\n🔍 Testing connection ...\n")
    ok, msg = eng.test_connection()
    print(f"{'✅' if ok else '❌'} {msg}\n")
    if not ok:
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} — Odoo Printer Client")
    parser.add_argument("--config", "-c", default=CONFIG_FILE)
    parser.add_argument("--test", "-t", action="store_true", help="Test connection")
    parser.add_argument("--headless", action="store_true", help="No GUI")
    parser.add_argument("--minimized", action="store_true",
                        help="Start minimized to tray (used for auto-start on boot)")
    parser.add_argument("--no-update", action="store_true",
                        help="Skip the startup self-update check")
    args = parser.parse_args()

    # Self-update on startup (frozen .exe only). If an update is found it
    # downloads, launches the swap-and-relaunch helper, and we exit here.
    if not args.test and not args.no_update:
        try:
            if check_for_update():
                log.info("Update started — exiting so the new version can launch.")
                return
        except Exception as e:
            log.debug(f"Startup update check skipped: {e}")

    if args.test:
        run_test(args.config)
    elif args.headless:
        run_headless(args.config)
    else:
        run_gui(start_minimized=args.minimized)

if __name__ == "__main__":
    main()
