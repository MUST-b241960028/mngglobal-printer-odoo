from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MngVisaPeriodAddLeadWizard(models.TransientModel):
    _name = "mng.visa.period.add.lead.wizard"
    _description = "Эзэнгүй лид хавтасанд нэмэх визард"

    period_id = fields.Many2one(
        "mng.visa.recruitment.period", string="Элсэлтийн хавтас", required=True)

    program_type_id = fields.Many2one(
        related="period_id.program_type_id", string="Хөтөлбөр", readonly=True)

    application_ids = fields.Many2many(
        "mng.visa.application",
        string="Сонгох эзэнгүй лидүүд",
        domain="['&', ('recruitment_period_id', '=', False), '|', ('program_type_id', '=', False), ('program_type_id', '=', program_type_id)]"
    )

    def action_add_leads(self):
        self.ensure_one()
        if not self.application_ids:
            raise UserError(_("Ямар нэгэн эзэнгүй лид сонгогдоогүй байна!"))

        count = len(self.application_ids)
        self.application_ids.write({
            "recruitment_period_id": self.period_id.id
        })

        for app in self.application_ids:
            app.message_post(
                body=_("📁 '%s' элсэлтийн хавтасанд сонгон нэмэгдлээ.") % self.period_id.name
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Амжилттай!"),
                "message": _("Нийт %s лидийг '%s' хавтасанд амжилттай нэмлээ.") % (
                    count, self.period_id.name
                ),
                "type": "success",
                "sticky": False,
            }
        }
