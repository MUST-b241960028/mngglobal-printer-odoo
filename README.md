# 🖨️ MNG Printer Bridge

Connect your **office printers** to a self-hosted **Odoo Community ERP** — **zero cost**, no Odoo Enterprise, no paid plugins.

## The Full Picture

```
👤 Manager (overseas)                    🖥️ Worker's PC (office)
     │                                        │
     │  1. Click "Print at Office"            │
     ▼                                        │
☁️ Odoo ERP (VPS)                             │
     │  - Generates PDF                       │
     │  - Attaches to PRINT QUEUE note        │
     │                                        │
     │            ◄── Internet ──►            │
     │                                        ▼
     │  2. Client polls via XML-RPC     📋 MNG Printer Bridge
     │                                   (desktop app)
     │  3. Downloads PDF                      │
     │  4. Deletes from queue                 │
     │                                        ▼
     │                                  🖨️ HP / Epson
     │                                   (USB or WiFi)
```

## Two Components

### 1. 🖥️ Client Software (`printer_bridge.py`)
Desktop app that runs on the **office worker's Windows PC**. Polls your Odoo for PDFs and prints them automatically.

### 2. 📦 Odoo Module (`odoo_module/mng_print_bridge/`)
Adds a **"🖨️ Print at Office"** button to invoices, sales orders, and purchase orders in Odoo. One click from anywhere in the world.

---

## Quick Start

### Step 1: Install the Odoo Module (on your VPS)

1. Copy `odoo_module/mng_print_bridge/` to your Odoo addons directory:
   ```bash
   cp -r odoo_module/mng_print_bridge /path/to/odoo/addons/
   ```
2. Restart Odoo:
   ```bash
   sudo systemctl restart odoo
   ```
3. In Odoo, go to **Apps** → click **Update Apps List**
4. Search for **"MNG Print Bridge"** and install it
5. The "🖨️ Print at Office" button will appear on confirmed invoices, sale orders, and purchase orders

### Step 2: Set Up the Client (on the office PC)

**Prerequisites:**
- **Python 3.8+** — [Download](https://www.python.org/downloads/) (check "Add to PATH")
- **SumatraPDF** (recommended) — [Download](https://www.sumatrapdfreader.org) (free, silent printing)
- Printers installed on the PC

**Setup:**
1. Copy this repo to the office Windows PC
2. Double-click **`install.bat`** — it walks you through setup
3. Or manually:
   ```bash
   copy config.ini.example config.ini
   notepad config.ini    # Fill in your Odoo details
   ```

**Run:**
```bash
python printer_bridge.py          # Launch the desktop app
```
Or double-click **`start_printer.bat`**

### Step 3: Print from Anywhere

1. Open an invoice/sale order/purchase order in Odoo
2. Click **"🖨️ Print at Office"**
3. ✅ Done! The document prints at the office within 10 seconds

---

## Client Features

| Feature | Description |
|---------|-------------|
| **Printer auto-detect** | Finds all USB + WiFi printers automatically |
| **Printer dropdown** | Choose which printer to use from a list |
| **Test Connection** | Verify Odoo connection before starting |
| **Activity Log** | Real-time colored log of all print activity |
| **Auto-reconnect** | Handles network drops gracefully |
| **Settings GUI** | No config files to edit manually |
| **Dark theme** | Professional MNG-branded interface |
| **Headless mode** | `--headless` flag for running as a service |

## Odoo Module Features

| Feature | Description |
|---------|-------------|
| **One-click printing** | "Print at Office" button on invoices, SO, PO |
| **Auto PDF generation** | Generates the document PDF automatically |
| **Queue management** | Attaches to PRINT QUEUE note, auto-deleted after printing |
| **Success notification** | Shows confirmation toast after queuing |
| **Community Edition** | Works on self-hosted Odoo CE (no Enterprise needed) |

---

## Auto-Start on Windows Boot

1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Click **Create Basic Task**
3. Name: `MNG Printer Bridge`
4. Trigger: **When the computer starts**
5. Action: **Start a program**
6. Program: `pythonw` (not `python` — this hides the console)
7. Arguments: `printer_bridge.py`
8. Start in: `C:\path\to\mngglobal-printer-odoo`

---

## Command Line Options

```
python printer_bridge.py                    # GUI (default)
python printer_bridge.py --headless         # No GUI, console-only
python printer_bridge.py --test             # Test connection and exit
python printer_bridge.py --config my.ini    # Custom config file
```

---

## Project Structure

```
mngglobal-printer-odoo/
├── printer_bridge.py              # Client desktop app
├── icon.png                       # App icon (MNG logo)
├── config.ini.example             # Config template
├── install.bat                    # Windows setup helper
├── start_printer.bat              # Daily launcher
├── requirements.txt               # No dependencies needed!
├── README.md                      # This file
├── .gitignore
│
└── odoo_module/
    └── mng_print_bridge/          # Odoo CE module
        ├── __manifest__.py
        ├── __init__.py
        ├── models/
        │   ├── __init__.py
        │   └── print_bridge.py    # Print at Office logic
        ├── views/
        │   └── print_bridge_views.xml  # Button UI
        ├── security/
        │   └── ir.model.access.csv
        └── static/description/
            └── icon.png
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Button not visible | Make sure the document is confirmed/posted |
| "No report configured" | The document type may not have a PDF report |
| Connection failed | Check Odoo URL, database name, credentials |
| No printers found | Make sure printers are installed in Windows |
| Prints twice | Check logs — attachment deletion may have failed |
| Module not found | Run "Update Apps List" in Odoo, then search again |

## Security

- `config.ini` contains credentials — it's gitignored
- Use an [Odoo API key](https://www.odoo.com/documentation/17.0/developer/reference/external_api.html) instead of password
- Create a dedicated Odoo user with minimal permissions
- The connection uses HTTPS if your Odoo is on HTTPS

## License

MIT — Free for any use.
