from odoo import models, fields, api
from odoo.exceptions import UserError


class MngVisaDocument(models.Model):
    _name = "mng.visa.document"
    _description = "Бичиг баримт"
    _order = "sequence, id"
    _inherit = ["mail.thread"]

    application_id = fields.Many2one(
        "mng.visa.application", string="Гэрээ",
        required=True, ondelete="cascade")

    name = fields.Char(string="Нэр", required=True, tracking=True,
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
    ], string="Төрөл", default="other", required=True, tracking=True)

    file = fields.Binary(string="Файл", required=True, attachment=True)
    file_name = fields.Char(string="Файлын нэр", tracking=True)

    # Preview URL — computed from the underlying ir.attachment
    preview_url = fields.Char(
        string="Урьдчилан харах", compute="_compute_preview_url")

    last_edited_by = fields.Many2one(
        "res.users", string="Сүүлд засварласан",
        compute="_compute_last_edited", store=False)
    last_edited_at = fields.Datetime(
        string="Засварласан огноо",
        compute="_compute_last_edited", store=False)

    sequence = fields.Integer(default=10)
    notes = fields.Text(string="Тэмдэглэл", tracking=True)
    upload_date = fields.Date(string="Огноо", default=fields.Date.today)
    uploaded_by = fields.Many2one(
        "res.users", string="Оруулсан",
        default=lambda self: self.env.user)

    @api.depends("file")
    def _compute_last_edited(self):
        for rec in self:
            att = rec._get_attachment() if rec.id else None
            if att:
                rec.last_edited_by = att.write_uid
                rec.last_edited_at = att.write_date
            else:
                rec.last_edited_by = False
                rec.last_edited_at = False

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
    ONLYOFFICE_EDITABLE_EXTS = (
        "docx", "doc", "odt", "rtf", "txt",
        "xlsx", "xls", "ods", "csv",
        "pptx", "ppt", "odp",
        "pdf",
    )

    def _file_ext(self):
        return (self.file_name or "").rsplit(".", 1)[-1].lower()

    def _get_attachment(self):
        return self.env["ir.attachment"].search([
            ("res_model", "=", "mng.visa.document"),
            ("res_id", "=", self.id),
            ("res_field", "=", "file"),
        ], limit=1)

    def action_preview(self):
        self.ensure_one()
        attachment = self._get_attachment()
        if not attachment:
            return
        ext = (self.file_name or "").rsplit(".", 1)[-1].lower()
        if ext in self.ONLYOFFICE_EXTS:
            from urllib.parse import quote
            url = (
                f"/onlyoffice/preview?url=/onlyoffice/file/content/{attachment.id}"
                f"&title={quote(self.file_name or 'document')}"
            )
        else:
            url = f"/web/content/{attachment.id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_edit(self):
        self.ensure_one()
        attachment = self._get_attachment()
        if not attachment:
            return
        if self._file_ext() not in self.ONLYOFFICE_EDITABLE_EXTS:
            raise UserError(
                "Энэ төрлийн файлыг засах боломжгүй. "
                "Зөвхөн урьдчилан харах, татах боломжтой.\n\n"
                "(Зөвхөн Word, Excel, PowerPoint, PDF, текст файлуудыг засах боломжтой.)"
            )
        return {
            "type": "ir.actions.act_url",
            "url": f"/onlyoffice/editor/{attachment.id}",
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

    def _sync_attachment_name(self):
        for rec in self:
            if not rec.file_name:
                continue
            att = rec._get_attachment()
            if att and att.name != rec.file_name:
                att.sudo().write({"name": rec.file_name})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") and vals.get("file_name"):
                vals["name"] = vals["file_name"].rsplit(".", 1)[0]
        records = super().create(vals_list)
        records._sync_attachment_name()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "file_name" in vals or "file" in vals:
            self._sync_attachment_name()
        return res

    @api.onchange("file_name")
    def _onchange_file_name_set_name(self):
        if self.file_name and not self.name:
            self.name = self.file_name.rsplit(".", 1)[0]
