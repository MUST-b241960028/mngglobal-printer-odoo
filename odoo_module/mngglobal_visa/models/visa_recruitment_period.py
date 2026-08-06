from odoo import models, fields, api, _


class MngVisaRecruitmentPeriod(models.Model):
    """
    Элсэлтийн үе — Оюутан элсүүлэлтийн хугацаа, кохорт бүрийг ангилна.
    Жишээ нь: 9-р сарын элсэлт, 10-р сарын элсэлт, 11-р сарын элсэлт гэх мэт.
    """
    _name = "mng.visa.recruitment.period"
    _description = "Элсэлтийн үе"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"

    name = fields.Char(string="Элсэлтийн үеийн нэр", required=True, tracking=True)
    code = fields.Char(string="Код", help="Жишээ: SEP-2026, OCT-2026")
    date_start = fields.Date(string="Эхлэх огноо", tracking=True)
    date_end = fields.Date(string="Дуусах / Нисэх огноо", tracking=True)
    
    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        help="Тодорхой нэг хөтөлбөрт зориулсан бол сонгоно. Хоосон орхивол бүх хөтөлбөрт хамаарна.")
    
    state = fields.Selection([
        ("draft", "Бэлтгэл"),
        ("active", "Нээлттэй"),
        ("closed", "Хаагдсан"),
        ("archived", "Архив"),
    ], default="active", string="Төлөв", tracking=True)

    active = fields.Boolean(default=True)
    color = fields.Integer(string="Өнгө", default=10)
    note = fields.Text(string="Тэмдэглэл / Зааварчилгаа")

    application_ids = fields.One2many(
        "mng.visa.application", "recruitment_period_id",
        string="Аппликейшнүүд")

    application_count = fields.Integer(
        string="Нийт аппликейшн", compute="_compute_counts")
    pending_count = fields.Integer(
        string="Хүлээгдэж буй", compute="_compute_counts")
    paid_count = fields.Integer(
        string="Төлбөр төлөгдсөн", compute="_compute_counts")

    @api.depends("application_ids", "application_ids.payment_status")
    def _compute_counts(self):
        for rec in self:
            rec.application_count = len(rec.application_ids)
            rec.pending_count = len(rec.application_ids.filtered(lambda a: a.payment_status != 'paid'))
            rec.paid_count = len(rec.application_ids.filtered(lambda a: a.payment_status == 'paid'))

    def action_view_applications(self):
        """
        Элсэлтийн үеийн тохиргооноос тухайн кохортын ажлын самбарыг нээнэ.
        """
        self.ensure_one()
        return {
            "name": self.name,
            "type": "ir.actions.client",
            "tag": "mngglobal_visa.cohort_workspace",
            "params": {
                "program_id": self.program_type_id.id or False,
                "scope": "cohort",
                "cohort_id": self.id,
            },
        }

    def action_open_add_leads_wizard(self):
        """
        Хуваарилаагүй аппликейшнүүдээс сонгож энэ элсэлтийн үед нэмэх визардыг нээнэ.
        """
        self.ensure_one()
        return {
            "name": _("Хуваарилаагүй аппликейшн нэмэх"),
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.period.add.lead.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_period_id": self.id,
            }
        }
