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
        today = fields.Date.today()
        in_30 = today + timedelta(days=30)
        in_7 = today + timedelta(days=7)

        done_stages = self.env["mng.visa.stage"].search([("is_done", "=", True)]).ids
        failed_stages = self.env["mng.visa.stage"].search([("is_failed", "=", True)]).ids
        terminal = done_stages + failed_stages

        active_apps = App.search([("active", "=", True)])
        pipeline_apps = active_apps.filtered(
            lambda a: a.stage_id.id not in terminal)

        by_code = {}
        for a in pipeline_apps:
            by_code[a.program_type_id.code] = by_code.get(a.program_type_id.code, 0) + 1

        paid = sum(Payment.search([("state", "=", "paid")]).mapped("amount"))
        pending = sum(Payment.search([("state", "in", ["pending", "overdue"])]).mapped("amount"))

        for rec in self:
            rec.total_active = len(pipeline_apps)
            rec.count_ph_adult = by_code.get("PH_ADULT", 0)
            rec.count_ph_kids = by_code.get("PH_KIDS", 0)
            rec.count_jp_student = by_code.get("JP_STUDENT", 0)
            rec.count_jp_worker = by_code.get("JP_WORKER", 0)
            rec.count_kr = by_code.get("KR", 0)

            rec.total_fees = sum(active_apps.mapped("total_fee"))
            rec.total_collected = paid
            rec.total_outstanding = pending

            rec.overdue_payments = Payment.search_count([("state", "=", "overdue")])
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
        return self._open_apps("Филиппин Насанд хүрэгч",
                               [("program_type_id.code", "=", "PH_ADULT"), ("active", "=", True)])

    def action_open_ph_kids(self):
        return self._open_apps("Филиппин Хүүхэд",
                               [("program_type_id.code", "=", "PH_KIDS"), ("active", "=", True)])

    def action_open_jp_student(self):
        return self._open_apps("Япон Оюутан",
                               [("program_type_id.code", "=", "JP_STUDENT"), ("active", "=", True)])

    def action_open_jp_worker(self):
        return self._open_apps("Япон Ажилтан",
                               [("program_type_id.code", "=", "JP_WORKER"), ("active", "=", True)])

    def action_open_kr(self):
        return self._open_apps("Солонгос",
                               [("program_type_id.code", "=", "KR"), ("active", "=", True)])

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
