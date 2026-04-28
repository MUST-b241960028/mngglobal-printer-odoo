from odoo import models, fields


class MngVisaDocument(models.Model):
    _name = "mng.visa.document"
    _description = "Бичиг баримт"
    _order = "sequence, id"

    application_id = fields.Many2one(
        "mng.visa.application", string="Өргөдөл",
        required=True, ondelete="cascade")

    name = fields.Char(string="Нэр", required=True,
        help="Жишээ: Паспорт, Зураг 3x4, Диплом, Гэрчилгээ")

    document_type = fields.Selection([
        ("passport", "Паспорт"),
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

    sequence = fields.Integer(default=10)
    notes = fields.Text(string="Тэмдэглэл")
    upload_date = fields.Date(string="Огноо", default=fields.Date.today)
    uploaded_by = fields.Many2one(
        "res.users", string="Оруулсан",
        default=lambda self: self.env.user)
