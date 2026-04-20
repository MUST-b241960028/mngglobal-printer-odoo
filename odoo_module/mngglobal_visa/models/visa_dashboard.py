from odoo import models, fields, api
from datetime import date, timedelta


class MngVisaDashboard(models.TransientModel):
    _name = "mng.visa.dashboard"
    _description = "CEO Dashboard"

    # ── Pipeline counts ──
    total_active = fields.Integer(compute="_compute_all")
    total_leads = fields.Integer(compute="_compute_all")

    count_ph_adult = fields.Integer(compute="_compute_all")
    count_ph_kids = fields.Integer(compute="_compute_all")
    count_jp_student = fields.Integer(compute="_compute_all")
    count_jp_worker = fields.Integer(compute="_compute_all")
    count_kr = fields.Integer(compute="_compute_all")

    # ── Finance ──
    total_fees = fields.Monetary(compute="_compute_all", currency_field="currency_id")
    total_collected = fields.Monetary(compute="_compute_all", currency_field="currency_id")
    total_outstanding = fields.Monetary(compute="_compute_all", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)

    # ── Alerts ──
    overdue_payments = fields.Integer(compute="_compute_all")
    insurance_due_soon = fields.Integer(compute="_compute_all")
    departures_next_30 = fields.Integer(compute="_compute_all")

    @api.depends()
    def _compute_all(self):
        App = self.env["mng.visa.application"]
        Lead = self.env["mng.visa.lead"]
        Payment = self.env["mng.visa.payment"]
        today = date.today()
        in_30 = today + timedelta(days=30)
        in_7 = today + timedelta(days=7)

        active_apps = App.search([("active", "=", True)])
        done_stages = self.env["mng.visa.stage"].search([("is_done", "=", True)]).ids
        failed_stages = self.env["mng.visa.stage"].search([("is_failed", "=", True)]).ids
        pipeline_apps = active_apps.filtered(
            lambda a: a.stage_id.id not in done_stages + failed_stages)

        for rec in self:
            rec.total_leads = Lead.search_count([("state", "not in", ["converted", "lost"])])
            rec.total_active = len(pipeline_apps)

            rec.count_ph_adult = len(pipeline_apps.filtered(
                lambda a: a.program_type_id.code == "PH_ADULT"))
            rec.count_ph_kids = len(pipeline_apps.filtered(
                lambda a: a.program_type_id.code == "PH_KIDS"))
            rec.count_jp_student = len(pipeline_apps.filtered(
                lambda a: a.program_type_id.code == "JP_STUDENT"))
            rec.count_jp_worker = len(pipeline_apps.filtered(
                lambda a: a.program_type_id.code == "JP_WORKER"))
            rec.count_kr = len(pipeline_apps.filtered(
                lambda a: a.program_type_id.code == "KR"))

            rec.total_fees = sum(active_apps.mapped("total_fee"))
            rec.total_collected = sum(
                p.amount for p in Payment.search([("state", "=", "paid")]))
            rec.total_outstanding = sum(
                p.amount for p in Payment.search([("state", "in", ["pending", "overdue"])]))

            rec.overdue_payments = Payment.search_count([("state", "=", "overdue")])
            rec.insurance_due_soon = len(active_apps.filtered(
                lambda a: (
                    not a.insurance_done
                    and a.insurance_due_date
                    and a.insurance_due_date <= fields.Date.to_date(str(in_7))
                )))
            rec.departures_next_30 = len(active_apps.filtered(
                lambda a: (
                    a.departure_date
                    and fields.Date.to_date(str(today)) <= a.departure_date <= fields.Date.to_date(str(in_30))
                )))

    def action_open_leads(self):
        return {"type": "ir.actions.act_window", "res_model": "mng.visa.lead",
                "view_mode": "kanban,list,form", "name": "Leads"}

    def action_open_applications(self):
        return {"type": "ir.actions.act_window", "res_model": "mng.visa.application",
                "view_mode": "kanban,list,form", "name": "Бүх өргөдлүүд"}

    def action_open_overdue(self):
        return {"type": "ir.actions.act_window", "res_model": "mng.visa.payment",
                "view_mode": "list", "name": "Хугацаа хэтэрсэн төлбөрүүд",
                "domain": [("state", "=", "overdue")]}

    def action_open_departures(self):
        today = fields.Date.today()
        in_30 = fields.Date.to_string(date.today() + timedelta(days=30))
        return {"type": "ir.actions.act_window", "res_model": "mng.visa.application",
                "view_mode": "list,form", "name": "Нисэж яах суралцагчид (30 хоног)",
                "domain": [("departure_date", ">=", today), ("departure_date", "<=", in_30)]}

    def action_open_insurance(self):
        today = fields.Date.today()
        in_7 = fields.Date.to_string(date.today() + timedelta(days=7))
        return {"type": "ir.actions.act_window", "res_model": "mng.visa.application",
                "view_mode": "list,form", "name": "Даатгал хийлгэх шаардлагатай",
                "domain": [
                    ("insurance_done", "=", False),
                    ("insurance_due_date", "<=", in_7),
                    ("insurance_due_date", "!=", False),
                ]}

    @api.model
    def action_open_dashboard(self):
        rec = self.create({})
        return {
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.dashboard",
            "res_id": rec.id,
            "view_mode": "form",
            "target": "main",
            "name": "CEO Dashboard",
        }
