from odoo import models, fields, api


class MngVisaLead(models.Model):
    _name = "mng.visa.lead"
    _description = "Зуучлалын lead (chatbot)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Нэр", tracking=True)
    phone = fields.Char(string="Утас", required=True, tracking=True)
    email = fields.Char(string="Имэйл")
    source = fields.Selection([
        ("chatbot", "AI Chatbot"),
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("phone", "Утсаар холбогдсон"),
        ("walkin", "Ирж уулзсан"),
        ("referral", "Танилын зуучлал"),
        ("other", "Бусад"),
    ], string="Эх сурвалж", default="chatbot", tracking=True)
    interest = fields.Selection([
        ("ph_adult", "🇵🇭 Филиппин Насанд хүрэгч"),
        ("ph_kids", "🇵🇭 Филиппин Хүүхэд"),
        ("jp_student", "🇯🇵 Япон Оюутан"),
        ("jp_worker", "🇯🇵 Япон Ажилтан"),
        ("kr", "🇰🇷 Солонгос"),
        ("unknown", "Тодорхойгүй"),
    ], string="Сонирхож буй хөтөлбөр", default="unknown", tracking=True)
    state = fields.Selection([
        ("new", "🆕 Шинэ"),
        ("contacted", "📞 Холбогдсон"),
        ("meeting", "💬 Уулзсан"),
        ("converted", "✅ Үйлчлүүлэгч болсон"),
        ("lost", "❌ Алдагдсан"),
    ], string="Төлөв", default="new", tracking=True, group_expand="_expand_states")
    assigned_to = fields.Many2one(
        "res.users", string="Хариуцагч", tracking=True)
    notes = fields.Text(string="Тэмдэглэл")
    application_id = fields.Many2one(
        "mng.visa.application", string="Өргөдөл",
        readonly=True, help="Lead-ээс үүссэн өргөдөл")
    partner_id = fields.Many2one(
        "res.partner", string="Харилцагч")

    @api.model
    def _expand_states(self, states, domain):
        """Show all states in kanban even if empty."""
        return [key for key, _ in type(self).state.selection]

    def action_convert_to_application(self):
        """Convert lead to a visa application."""
        self.ensure_one()

        # Find or create partner
        partner = self.partner_id
        if not partner:
            partner = self.env["res.partner"].create({
                "name": self.name or self.phone,
                "phone": self.phone,
                "email": self.email,
            })
            self.partner_id = partner

        # Map interest to program type
        code_map = {
            "ph_adult": "PH_ADULT",
            "ph_kids": "PH_KIDS",
            "jp_student": "JP_STUDENT",
            "jp_worker": "JP_WORKER",
            "kr": "KR",
        }
        program_type = False
        if self.interest and self.interest != "unknown":
            program_type = self.env["mng.visa.program.type"].search(
                [("code", "=", code_map.get(self.interest))], limit=1)

        # Create application
        vals = {
            "partner_id": partner.id,
            "lead_id": self.id,
            "assigned_to": self.assigned_to.id or self.env.uid,
        }
        if program_type:
            vals["program_type_id"] = program_type.id
            # Set first stage
            first_stage = self.env["mng.visa.stage"].search(
                [("program_type_id", "=", program_type.id)],
                order="sequence", limit=1)
            if first_stage:
                vals["stage_id"] = first_stage.id

        application = self.env["mng.visa.application"].create(vals)
        self.write({
            "state": "converted",
            "application_id": application.id,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.application",
            "res_id": application.id,
            "view_mode": "form",
            "target": "current",
        }
