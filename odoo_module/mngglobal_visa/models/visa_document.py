from odoo import models, fields, api


class MngVisaDocument(models.Model):
    _name = "mng.visa.document"
    _description = "Бичиг баримт"
    _order = "sequence, id"

    application_id = fields.Many2one(
        "mng.visa.application", string="Гэрээ",
        required=True, ondelete="cascade")

    name = fields.Char(string="Нэр", required=True,
        help="Жишээ: Паспорт, Зураг 3x4, Диплом, Гэрчилгээ")

    document_type = fields.Selection([
        ("passport", "Паспорт"),
        ("national_id", "Иргэний үнэмлэх"),
        ("photo", "Зураг"),
        ("diploma", "Диплом / Боловсролын гэрчилгээ"),
        ("birth_cert", "Төрсний гэрчилгээ"),
        ("medical", "Эмнэлгийн магадлагаа"),
        ("police", "Цагдаагийн тодорхойлолт"),
        ("bank", "Банкны тодорхойлолт"),
        ("contract", "Гэрээ"),
        ("invitation", "Урилга"),
        ("insurance", "Даатгал"),
        ("other", "Бусад"),
    ], string="Төрөл", default="other", required=True)

    file = fields.Binary(string="Файл", required=True, attachment=True)
    file_name = fields.Char(string="Файлын нэр")

    # Preview URL — computed from the underlying ir.attachment
    preview_url = fields.Char(
        string="Урьдчилан харах", compute="_compute_preview_url")

    sequence = fields.Integer(default=10)
    notes = fields.Text(string="Тэмдэглэл")
    upload_date = fields.Date(string="Огноо", default=fields.Date.today)
    uploaded_by = fields.Many2one(
        "res.users", string="Оруулсан",
        default=lambda self: self.env.user)

    @api.depends("file")
    def _compute_preview_url(self):
        for rec in self:
            if rec.id and rec.file:
                attachment = self.env["ir.attachment"].search([
                    ("res_model", "=", "mng.visa.document"),
                    ("res_id", "=", rec.id),
                    ("res_field", "=", "file"),
                ], limit=1)
                if attachment:
                    rec.preview_url = f"/web/content/{attachment.id}"
                else:
                    rec.preview_url = False
            else:
                rec.preview_url = False

    ONLYOFFICE_EXTS = (
        "docx", "doc", "odt", "rtf", "txt",
        "xlsx", "xls", "ods", "csv",
        "pptx", "ppt", "odp",
        "pdf",
    )

    def action_preview(self):
        self.ensure_one()
        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", "mng.visa.document"),
            ("res_id", "=", self.id),
            ("res_field", "=", "file"),
        ], limit=1)
        if not attachment:
            return
        ext = (self.file_name or "").rsplit(".", 1)[-1].lower()
        if ext in self.ONLYOFFICE_EXTS:
            url = f"/onlyoffice/editor/{attachment.id}"
        else:
            url = f"/web/content/{attachment.id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_download(self):
        """Download the document file."""
        self.ensure_one()
        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", "mng.visa.document"),
            ("res_id", "=", self.id),
            ("res_field", "=", "file"),
        ], limit=1)
        if attachment:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment.id}?download=true",
                "target": "new",
            }

    def action_delete_document(self):
        self.unlink()
