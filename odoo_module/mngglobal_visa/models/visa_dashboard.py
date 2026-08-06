from odoo import models, fields, api
from datetime import timedelta


class MngVisaDashboard(models.TransientModel):
    _name = "mng.visa.dashboard"
    _description = "MNG Visa Dashboard"

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Удирдлагын самбар"

    # Pipeline counts
    total_active = fields.Integer(compute="_compute_all")
    count_ph_adult = fields.Integer(compute="_compute_all")
    count_ph_kids = fields.Integer(compute="_compute_all")
    count_jp_student = fields.Integer(compute="_compute_all")
    count_jp_worker = fields.Integer(compute="_compute_all")
    count_kr = fields.Integer(compute="_compute_all")

    # Finance
    total_fees = fields.Monetary(compute="_compute_all", currency_field="currency_id")
    total_collected = fields.Monetary(compute="_compute_all", currency_field="currency_id")
    total_outstanding = fields.Monetary(compute="_compute_all", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)

    # Alerts (7 / 30 day windows)
    overdue_payments = fields.Integer(compute="_compute_all")
    insurance_due_soon = fields.Integer(compute="_compute_all")
    departures_next_30 = fields.Integer(compute="_compute_all")

    def _compute_all(self):
        App = self.env["mng.visa.application"]
        Payment = self.env["mng.visa.payment"]
        Stage = self.env["mng.visa.stage"]
        today = fields.Date.today()
        in_30 = today + timedelta(days=30)
        in_7 = today + timedelta(days=7)

        done_stages = Stage.search([("is_done", "=", True)]).ids
        failed_stages = Stage.search([("is_failed", "=", True)]).ids
        terminal = done_stages + failed_stages

        # Inquiry-only (first) stage per program — excluded from finance totals
        first_stage_ids = set()
        for pt in self.env["mng.visa.program.type"].search([]):
            first = Stage.search(
                [("program_type_id", "=", pt.id)], order="sequence", limit=1
            )
            if first:
                first_stage_ids.add(first.id)

        active_apps = App.search([("active", "=", True)])
        pipeline_apps = active_apps.filtered(
            lambda a: a.stage_id.id not in terminal)
        finance_apps = active_apps.filtered(
            lambda a: a.stage_id.id not in first_stage_ids)
        finance_app_ids = finance_apps.ids

        by_code = {}
        for a in pipeline_apps:
            by_code[a.program_type_id.code] = by_code.get(a.program_type_id.code, 0) + 1

        paid = sum(Payment.search([
            ("state", "=", "paid"),
            ("application_id", "in", finance_app_ids),
        ]).mapped("amount"))
        pending = sum(Payment.search([
            ("state", "in", ["pending", "overdue"]),
            ("application_id", "in", finance_app_ids),
        ]).mapped("amount"))

        for rec in self:
            rec.total_active = len(pipeline_apps)
            rec.count_ph_adult = by_code.get("PH_ADULT", 0)
            rec.count_ph_kids = by_code.get("PH_KIDS", 0)
            rec.count_jp_student = by_code.get("JP_STUDENT", 0)
            rec.count_jp_worker = by_code.get("JP_WORKER", 0)
            rec.count_kr = by_code.get("KR", 0)

            rec.total_fees = sum(finance_apps.mapped("total_fee"))
            rec.total_collected = paid
            rec.total_outstanding = pending

            rec.overdue_payments = Payment.search_count([
                ("state", "=", "overdue"),
                ("application_id", "in", finance_app_ids),
            ])
            rec.insurance_due_soon = len(active_apps.filtered(
                lambda a: (
                    not a.insurance_done
                    and a.insurance_due_date
                    and a.insurance_due_date <= in_7
                )))
            rec.departures_next_30 = len(active_apps.filtered(
                lambda a: a.departure_date and today <= a.departure_date <= in_30))

    def _open_apps(self, name, domain, ctx=None, view_mode="kanban,list,form"):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "mng.visa.application",
            "view_mode": view_mode,
            "domain": domain,
            "context": ctx or {},
        }

    def action_open_applications(self):
        return self._open_apps("Бүх өргөдлүүд", [("active", "=", True)],
                               view_mode="list,form")

    def action_open_ph_adult(self):
        return self.env.ref("mngglobal_visa.mng_visa_cohort_workspace_ph_adult").read()[0]

    def action_open_ph_kids(self):
        return self.env.ref("mngglobal_visa.mng_visa_cohort_workspace_ph_kids").read()[0]

    def action_open_jp_student(self):
        return self.env.ref("mngglobal_visa.mng_visa_cohort_workspace_jp_student").read()[0]

    def action_open_jp_worker(self):
        return self.env.ref("mngglobal_visa.mng_visa_cohort_workspace_jp_worker").read()[0]

    def action_open_kr(self):
        return self.env.ref("mngglobal_visa.mng_visa_cohort_workspace_kr").read()[0]

    def action_open_overdue(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Хугацаа хэтэрсэн төлбөрүүд",
            "res_model": "mng.visa.payment",
            "view_mode": "list,form",
            "domain": [("state", "=", "overdue")],
        }

    def action_open_departures(self):
        today = fields.Date.today()
        in_30 = today + timedelta(days=30)
        return self._open_apps(
            "Нисэх (30 хоног)",
            [("departure_date", ">=", today), ("departure_date", "<=", in_30),
             ("active", "=", True)],
            view_mode="list,form",
        )

    def action_open_insurance(self):
        in_7 = fields.Date.today() + timedelta(days=7)
        return self._open_apps(
            "Даатгал яаралтай",
            [("insurance_done", "=", False),
             ("insurance_due_date", "<=", in_7),
             ("insurance_due_date", "!=", False),
             ("active", "=", True)],
            view_mode="list,form",
        )
