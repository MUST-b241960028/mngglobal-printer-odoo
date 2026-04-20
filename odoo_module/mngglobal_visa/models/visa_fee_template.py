from odoo import models, fields, api


class MngVisaFeeTemplate(models.Model):
    _name = "mng.visa.fee.template"
    _description = "Төлбөрийн хуваарийн загвар"
    _order = "program_type_id, sequence"

    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        required=True, ondelete="cascade")
    name = fields.Char(string="Тайлбар", required=True,
        help="Жишээ: '30% урьдчилгаа', '600K орчуулгын хураамж'")
    sequence = fields.Integer(default=10)

    fee_type = fields.Selection([
        ("percentage", "Нийт дүнгийн хувиар"),
        ("fixed", "Тогтмол дүн"),
    ], string="Төрөл", required=True, default="percentage")
    percentage = fields.Float(string="Хувь (%)",
        help="Нийт хураамжийн хэдэн хувийг авах")
    fixed_amount = fields.Float(string="Тогтмол дүн")
    currency_id = fields.Many2one(
        "res.currency", string="Валют",
        default=lambda self: self.env.company.currency_id)

    payment_method = fields.Selection([
        ("cash", "Бэлэн мөнгө"),
        ("transfer", "Шилжүүлэг"),
        ("card", "Карт"),
    ], string="Төлбөрийн хэлбэр")

    @api.onchange("fee_type")
    def _onchange_fee_type(self):
        if self.fee_type == "fixed":
            self.percentage = 0
        else:
            self.fixed_amount = 0
