from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MngVisaAssignPeriodWizard(models.TransientModel):
    """
    Олон лидэд нэгэн зэрэг элсэлтийн хавтас тохируулах визард.
    """
    _name = "mng.visa.assign.period.wizard"
    _description = "Элсэлтийн хавтас бөөнөөр тохируулах"

    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        compute="_compute_program_type_id"
    )
    recruitment_period_id = fields.Many2one(
        "mng.visa.recruitment.period",
        string="Сонгох элсэлтийн хавтас",
        required=True,
        domain="['&', ('state', '!=', 'archived'), '|', ('program_type_id', '=', False), ('program_type_id', '=', program_type_id)]"
    )
    application_ids = fields.Many2many(
        "mng.visa.application",
        string="Сонгосон лидүүд / аппликейшнууд"
    )

    @api.depends("application_ids", "application_ids.program_type_id")
    def _compute_program_type_id(self):
        for rec in self:
            progs = rec.application_ids.mapped("program_type_id")
            if len(progs) == 1:
                rec.program_type_id = progs.id
            else:
                rec.program_type_id = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self._context.get("active_ids")
        if active_ids and self._context.get("active_model") == "mng.visa.application":
            res["application_ids"] = [(6, 0, active_ids)]
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.application_ids:
            raise UserError(_("Ямар нэгэн аппликейшн сонгогдоогүй байна!"))
        
        self.application_ids.write({
            "recruitment_period_id": self.recruitment_period_id.id
        })

        for app in self.application_ids:
            app.message_post(
                body=_("📁 Элсэлтийн хавтас шинэчлэгдлээ: <b>%s</b>") % self.recruitment_period_id.name
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Амжилттай!"),
                "message": _("Нийт %s лидийн элсэлтийн хавтас '%s' болж шинэчлэгдлээ.") % (
                    len(self.application_ids), self.recruitment_period_id.name
                ),
                "type": "success",
                "sticky": False,
            }
        }
