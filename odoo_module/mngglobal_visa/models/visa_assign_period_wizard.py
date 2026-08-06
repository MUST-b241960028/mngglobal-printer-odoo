from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MngVisaAssignPeriodWizard(models.TransientModel):
    """
    Олон хүсэлтийг нэгэн зэрэг элсэлтийн үед шилжүүлэх визард.
    """
    _name = "mng.visa.assign.period.wizard"
    _description = "Элсэлтийн үе бөөнөөр шилжүүлэх"

    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        compute="_compute_program_type_id"
    )
    recruitment_period_id = fields.Many2one(
        "mng.visa.recruitment.period",
        string="Шинэ элсэлтийн үе",
        required=True,
        domain="['&', ('state', '!=', 'archived'), '|', ('program_type_id', '=', False), ('program_type_id', '=', program_type_id)]"
    )
    application_ids = fields.Many2many(
        "mng.visa.application",
        string="Сонгосон лидүүд / хүсэлтүүд"
    )
    reason = fields.Text(string="Шилжүүлэх шалтгаан", required=True)

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
            raise UserError(_("Ямар нэгэн хүсэлт сонгогдоогүй байна!"))
        
        moved_count = 0
        for app in self.application_ids:
            if app.action_move_to_period(
                self.recruitment_period_id, self.reason, move_type="assign"
            ):
                moved_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Элсэлтийн үе шинэчлэгдлээ"),
                "message": _("Нийт %s хүсэлтийг '%s' элсэлтийн үед шилжүүллээ.") % (
                    moved_count, self.recruitment_period_id.name
                ),
                "type": "success",
                "sticky": False,
            }
        }
