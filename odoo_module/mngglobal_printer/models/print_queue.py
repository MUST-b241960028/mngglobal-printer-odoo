import logging
import os
import base64
import tempfile
import subprocess
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (
    ".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff",
    ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".odt", ".ods", ".odp", ".rtf", ".txt", ".csv"
)

CONVERTIBLE_EXTENSIONS = (
    ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".odt", ".ods", ".odp", ".rtf", ".txt", ".csv"
)


class MngPrintQueue(models.Model):
    """
    Хэвлэх дараалал — MNG Printer Bridge клиент програмын хэвлэх ажлуудыг хадгална.
    Хэрэглэгч баримтыг шууд байршуулах эсвэл нэхэмжлэх/захиалга дээрх
    "Оффист хэвлэх" товчийг ашиглан дарааллд оруулна.
    """
    _name = "mng.print.queue"
    _description = "Хэвлэх ажил"
    _order = "create_date desc"
    _rec_name = "display_name"

    name = fields.Char(string="Баримтын нэр", required=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    pdf_data = fields.Binary(string="PDF файл", attachment=True, required=True)
    pdf_filename = fields.Char(string="Файлын нэр")
    copies = fields.Integer(string="Хуулбар", default=1)
    printer_id = fields.Many2one("mng.printer.device", string="Принтер",
                                  domain="[('is_online', '=', True)]",
                                  help="Хэвлэх принтерээ сонгоно уу. Хоосон бол үндсэн принтерээр хэвлэнэ.")

    # ── Print options (applied by the bridge via SumatraPDF -print-settings) ──
    pages = fields.Char(
        string="Хуудас",
        help="Хэвлэх хуудсууд, ж: 1-3,5,8. Хоосон бол бүх хуудас.")
    page_subset = fields.Selection([
        ("all", "Бүх хуудас"),
        ("odd", "Сондгой хуудас"),
        ("even", "Тэгш хуудас"),
    ], string="Хуудасны багц", default="all")
    duplex = fields.Selection([
        ("default", "Принтерийн үндсэн"),
        ("simplex", "Нэг талд"),
        ("duplexlong", "Хоёр талд (урт ирмэг)"),
        ("duplexshort", "Хоёр талд (богино ирмэг)"),
    ], string="Хэвлэх тал", default="default")
    orientation = fields.Selection([
        ("default", "Үндсэн"),
        ("portrait", "Босоо"),
        ("landscape", "Хэвтээ"),
    ], string="Чиглэл", default="default")
    color_mode = fields.Selection([
        ("default", "Үндсэн"),
        ("color", "Өнгөт"),
        ("monochrome", "Хар цагаан"),
    ], string="Өнгө", default="default")
    scaling = fields.Selection([
        ("default", "Үндсэн"),
        ("fit", "Хуудсанд багтаах"),
        ("shrink", "Багасгаж багтаах"),
        ("noscale", "Жинхэнэ хэмжээ"),
    ], string="Хэмжээ", default="default")
    source_model = fields.Char(string="Эх загвар")
    source_id = fields.Integer(string="Эх бичлэгийн ID")
    source_ref = fields.Char(string="Эх сурвалж", compute="_compute_source_ref")
    user_id = fields.Many2one("res.users", string="Хүсэлт гаргасан",
                               default=lambda self: self.env.user,
                               readonly=True)
    state = fields.Selection([
        ("pending", "Хүлээгдэж буй"),
        ("printed", "Хэвлэгдсэн"),
        ("failed", "Амжилтгүй"),
        ("cancelled", "Цуцлагдсан"),
    ], default="pending", string="Төлөв")
    printed_at = fields.Datetime(string="Хэвлэгдсэн огноо")
    error_message = fields.Text(string="Алдааны мэдээлэл")
    note = fields.Text(string="Тэмдэглэл",
                       help="Хэвлэх ажлын нэмэлт тэмдэглэл")

    @api.constrains("pdf_filename")
    def _check_supported_format(self):
        for rec in self:
            if rec.pdf_filename:
                ext = os.path.splitext(rec.pdf_filename)[1].lower()
                if ext and ext not in SUPPORTED_EXTENSIONS:
                    raise ValidationError(_(
                        "Хэвлэх боломжгүй форматтай файл байна (%s).\n\n"
                        "Зөвхөн дараах форматын файлуудыг хэвлэх боломжтой:\n"
                        "• PDF баримтууд (.pdf)\n"
                        "• Зургууд (.png, .jpg, .jpeg, .bmp, .gif, .webp, .tiff)\n"
                        "• MS Word & Excel (.docx, .doc, .xlsx, .xls, .csv)\n"
                        "• PowerPoint & Текст (.pptx, .ppt, .txt, .rtf, .odt)"
                    ) % ext)

    @api.depends("name", "pdf_filename")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.pdf_filename or rec.name or f"Ажил #{rec.id}"

    @api.depends("source_model", "source_id")
    def _compute_source_ref(self):
        for rec in self:
            if rec.source_model and rec.source_id:
                rec.source_ref = f"{rec.source_model},{rec.source_id}"
            else:
                rec.source_ref = "Гараар оруулсан"

    def action_mark_printed(self):
        """Клиент програм амжилттай хэвлэсний дараа дуудна."""
        self.write({
            "state": "printed",
            "printed_at": fields.Datetime.now(),
        })
        return True

    def action_mark_failed(self, error=""):
        """Хэвлэх амжилтгүй болсон тохиолдолд клиент дуудна."""
        self.write({
            "state": "failed",
            "error_message": error or "",
        })
        return True

    def action_cancel(self):
        """Хүлээгдэж буй хэвлэх ажлыг цуцлах."""
        self.filtered(lambda r: r.state == "pending").write({
            "state": "cancelled",
        })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            filename = vals.get("pdf_filename") or vals.get("name", "")
            ext = os.path.splitext(filename)[1].lower()
            if ext in CONVERTIBLE_EXTENSIONS and vals.get("pdf_data"):
                try:
                    raw_data = base64.b64decode(vals["pdf_data"])
                    with tempfile.TemporaryDirectory() as tmpdir:
                        in_file = os.path.join(tmpdir, filename)
                        with open(in_file, "wb") as f:
                            f.write(raw_data)

                        cmd = ["soffice", "--headless", "--convert-to", "pdf", in_file, "--outdir", tmpdir]
                        res = subprocess.run(cmd, capture_output=True, timeout=45)

                        pdf_out = os.path.splitext(in_file)[0] + ".pdf"
                        if os.path.exists(pdf_out):
                            with open(pdf_out, "rb") as f:
                                vals["pdf_data"] = base64.b64encode(f.read()).decode("utf-8")
                            vals["pdf_filename"] = os.path.basename(pdf_out)
                            _logger.info(f"Auto-converted {filename} -> {vals['pdf_filename']}")
                except Exception as e:
                    _logger.error(f"Failed to auto-convert {filename} to PDF: {e}")

        return super().create(vals_list)

    def action_retry(self):
        """Амжилтгүй эсвэл цуцлагдсан ажлыг дахин дарааллд оруулах."""
        self.filtered(lambda r: r.state in ("failed", "cancelled")).write({
            "state": "pending",
            "error_message": False,
        })
