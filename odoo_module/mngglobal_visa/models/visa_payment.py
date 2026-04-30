from odoo import models, fields, api


class MngVisaPayment(models.Model):
    _name = "mng.visa.payment"
    _description = "Зуучлалын төлбөр"
    _order = "date_due, id"

    application_id = fields.Many2one(
        "mng.visa.application", string="Гэрээ",
        required=True, ondelete="cascade")
    name = fields.Char(
        string="Тайлбар", required=True,
        help="Жишээ: '30% урьдчилгаа', 'Сургуулийн хураамж'")
    amount = fields.Monetary(string="Дүн", required=True, currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", string="Валют",
        related="application_id.currency_id", store=True, readonly=False)
    date_due = fields.Date(string="Төлөх хугацаа")
    date_paid = fields.Date(string="Төлсөн огноо")
    state = fields.Selection([
        ("pending", "Хүлээгдэж буй"),
        ("paid", "Төлсөн"),
        ("overdue", "Хугацаа хэтэрсэн"),
    ], string="Төлөв", default="pending", compute="_compute_state", store=True)
    payment_method = fields.Selection([
        ("cash", "Бэлэн мөнгө"),
        ("transfer", "Шилжүүлэг"),
        ("card", "Карт"),
    ], string="Төлбөрийн хэлбэр")
    receipt_file = fields.Binary(string="Баримт")
    receipt_filename = fields.Char()
    notes = fields.Text(string="Тэмдэглэл")

    @api.depends("date_due", "date_paid")
    def _compute_state(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_paid:
                rec.state = "paid"
            elif rec.date_due and rec.date_due < today:
                rec.state = "overdue"
            else:
                rec.state = "pending"
