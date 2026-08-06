from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MngVisaPeriodMoveWizard(models.TransientModel):
    _name = "mng.visa.period.move.wizard"
    _description = "Элсэлтийн үе шилжүүлэх визард"

    application_id = fields.Many2one(
        "mng.visa.application", string="Хүсэлт", required=True,
        readonly=True)
    program_type_id = fields.Many2one(
        related="application_id.program_type_id", string="Хөтөлбөр", readonly=True)
    current_period_id = fields.Many2one(
        related="application_id.recruitment_period_id",
        string="Одоогийн элсэлтийн үе", readonly=True)
    target_period_id = fields.Many2one(
        "mng.visa.recruitment.period", string="Шинэ элсэлтийн үе", required=True,
        domain="['&', ('state', '!=', 'archived'), '|', ('program_type_id', '=', False), ('program_type_id', '=', program_type_id)]")
    mode = fields.Selection([
        ("move", "Одоогийн хүсэлтийг шилжүүлэх"),
        ("defer", "Шинэ хүсэлт үүсгэж хойшлуулах"),
    ], string="Үйлдэл", required=True, default="move", readonly=True)
    reason = fields.Text(string="Шалтгаан", required=True)

    @api.constrains("target_period_id", "current_period_id", "mode")
    def _check_target_period(self):
        for rec in self:
            if rec.target_period_id == rec.current_period_id:
                raise UserError(_("Одоогийн элсэлтийн үеэс өөр үе сонгоно уу."))

    def action_confirm(self):
        self.ensure_one()
        if self.mode == "defer":
            new_application = self.application_id.action_defer_to_period(
                self.target_period_id, self.reason
            )
            return {
                "type": "ir.actions.act_window",
                "name": _("Шинэ хүсэлт"),
                "res_model": "mng.visa.application",
                "res_id": new_application.id,
                "view_mode": "form",
                "target": "current",
            }

        self.application_id.action_move_to_period(
            self.target_period_id, self.reason
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Элсэлтийн үе шинэчлэгдлээ"),
                "message": _("'%s' элсэлтийн үе рүү шилжүүллээ.") % self.target_period_id.name,
                "type": "success",
                "sticky": False,
            },
        }
