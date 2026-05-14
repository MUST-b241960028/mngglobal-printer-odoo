from odoo import models, fields, api


class MngVisaDocument(models.Model):
    _name = "mng.visa.document"
    _description = "Бичиг баримт"
    _order = "sequence, id"

    active = fields.Boolean(default=True)
    deleted_at = fields.Datetime(string="Устгасан огноо", readonly=True)
    deleted_by = fields.Many2one("res.users", string="Устгасан хэрэглэгч", readonly=True)

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
                    rec.preview_url = f"/web/content/{attachment.id}?download=false"
                else:
                    rec.preview_url = False
            else:
                rec.preview_url = False

    def action_preview(self):
        """Open the document in a new browser tab for preview."""
        self.ensure_one()
        if not self.preview_url:
            return
        return {
            "type": "ir.actions.act_url",
            "url": self.preview_url,
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
        """Soft-delete: archive the document for 7 days before permanent removal."""
        self.write({
            "active": False,
            "deleted_at": fields.Datetime.now(),
            "deleted_by": self.env.user.id,
        })

    def action_restore_document(self):
        """Restore a soft-deleted document back to active."""
        self.write({
            "active": True,
            "deleted_at": False,
            "deleted_by": False,
        })

    @api.model
    def cron_purge_deleted_documents(self):
        """Permanently delete documents that have been in trash for over 7 days."""
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(days=7)
        old = self.with_context(active_test=False).search([
            ("active", "=", False),
            ("deleted_at", "!=", False),
            ("deleted_at", "<", cutoff),
        ])
        if old:
            old.unlink()
