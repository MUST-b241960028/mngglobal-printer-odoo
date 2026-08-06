from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MngVisaPeriodAddLeadWizard(models.TransientModel):
    _name = "mng.visa.period.add.lead.wizard"
    _description = "Хуваарилаагүй хүсэлтийг элсэлтийн үед нэмэх визард"

    period_id = fields.Many2one(
        "mng.visa.recruitment.period", string="Элсэлтийн үе", required=True)

    program_type_id = fields.Many2one(
        related="period_id.program_type_id", string="Хөтөлбөр", readonly=True)

    application_ids = fields.Many2many(
        "mng.visa.application",
        string="Сонгох хуваарилаагүй хүсэлтүүд",
        domain="['&', ('recruitment_period_id', '=', False), '|', ('program_type_id', '=', False), ('program_type_id', '=', program_type_id)]"
    )

    def action_add_leads(self):
        self.ensure_one()
        if not self.application_ids:
            raise UserError(_("Ямар нэгэн эзэнгүй лид сонгогдоогүй байна!"))

        count = 0
        for app in self.application_ids:
            if app.action_move_to_period(
                self.period_id, _("Анхны элсэлтийн үеийн хуваарилалт"),
                move_type="assign",
            ):
                count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Элсэлтийн үед нэмлээ"),
                "message": _("Нийт %s хүсэлтийг '%s' элсэлтийн үед нэмлээ.") % (
                    count, self.period_id.name
                ),
                "type": "success",
                "sticky": False,
            }
        }
