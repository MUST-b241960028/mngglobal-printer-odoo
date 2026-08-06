from odoo import models, fields, api, _


class MngVisaRecruitmentPeriod(models.Model):
    """
    Элсэлтийн үе / Хавтас — Оюутан элсүүлэлтийн хугацаа, хавтас бүрийг ангилна.
    Жишээ нь: 9-р сарын элсэлт, 10-р сарын элсэлт, 11-р сарын элсэлт гэх мэт.
    """
    _name = "mng.visa.recruitment.period"
    _description = "Элсэлтийн үе / Хавтас"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"

    name = fields.Char(string="Элсэлтийн нэр / Хавтас", required=True, tracking=True)
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
        string="Хүсэлтүүд / Аппликейшн")

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
        Хавтасны карт дээр дарахад тухайн элсэлтийн үед хамаарах аппликейшнуудыг нээнэ.
        """
        self.ensure_one()
        return {
            "name": f"📁 {self.name} — Аппликейшнууд",
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.application",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": [("recruitment_period_id", "=", self.id)],
            "context": {
                "default_recruitment_period_id": self.id,
                "search_default_recruitment_period_id": self.id,
            },
        }

    def action_assign_unassigned_leads(self):
        """
        Хавтасгүй / эзэнгүй байгаа бүх хуучин лидийг энэхүү элсэлтийн хавтасанд нэгэн зэрэг оруулна.
        Хэрэв хавтас дээр тодорхой Хөтөлбөр сонгогдсон бол зөвхөн тухайн хөтөлбөрийн эзэнгүй лидүүдийг оруулна.
        """
        self.ensure_one()
        domain = [("recruitment_period_id", "=", False)]
        if self.program_type_id:
            domain.append(("program_type_id", "=", self.program_type_id.id))

        unassigned = self.env["mng.visa.application"].search(domain)
        if not unassigned:
            msg = _("Зөвхөн %s хөтөлбөрийн хавтасгүй лид олдсонгүй.") % self.program_type_id.name if self.program_type_id else _("Хавтасгүй олдсон эзэнгүй лид байхгүй байна.")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Мэдээлэл"),
                    "message": msg,
                    "type": "info",
                    "sticky": False,
                }
            }

        count = len(unassigned)
        unassigned.write({"recruitment_period_id": self.id})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Амжилттай!"),
                "message": _("Хавтасгүй байсан нийт %s лидийг '%s' хавтасанд амжилттай тохирууллаа.") % (
                    count, self.name
                ),
                "type": "success",
                "sticky": False,
            }
        }

