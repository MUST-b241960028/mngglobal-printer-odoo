import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


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
    ], default="pending", string="Төлөв", tracking=True)
    printed_at = fields.Datetime(string="Хэвлэгдсэн огноо")
    error_message = fields.Text(string="Алдааны мэдээлэл")
    note = fields.Text(string="Тэмдэглэл",
                       help="Хэвлэх ажлын нэмэлт тэмдэглэл")

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

    def action_mark_failed(self, error=""):
        """Хэвлэх амжилтгүй болсон тохиолдолд клиент дуудна."""
        self.write({
            "state": "failed",
            "error_message": error,
        })

    def action_cancel(self):
        """Хүлээгдэж буй хэвлэх ажлыг цуцлах."""
        self.filtered(lambda r: r.state == "pending").write({
            "state": "cancelled",
        })

    def action_retry(self):
        """Амжилтгүй эсвэл цуцлагдсан ажлыг дахин дарааллд оруулах."""
        self.filtered(lambda r: r.state in ("failed", "cancelled")).write({
            "state": "pending",
            "error_message": False,
        })
