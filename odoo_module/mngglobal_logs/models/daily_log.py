import calendar
import datetime

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError

MANAGER_GROUP = "mngglobal_visa.group_visa_manager"


class MngDailyLogMixin(models.AbstractModel):
    """Shared fields + write/create guards for daily reports and plans."""
    _name = "mng.daily.log.mixin"
    _description = "MNG өдөр тутмын лог (mixin)"
    _inherit = ["mail.thread"]
    _order = "log_date desc, time_slot, id desc"

    log_date = fields.Date(
        string="Огноо", required=True, tracking=True, index=True,
        default=fields.Date.context_today,
    )
    time_slot = fields.Char(
        string="Цаг", tracking=True,
        help="Жишээ: 10:00-11:30 (заавал биш)",
    )
    user_id = fields.Many2one(
        "res.users", string="Хэрэглэгч", required=True, tracking=True,
        default=lambda self: self.env.user, index=True,
    )
    description = fields.Text(
        string="Тайлбар", required=True, tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company,
    )

    can_edit_now = fields.Boolean(
        string="Засварлах боломжтой",
        compute="_compute_can_edit_now",
    )

    @api.depends("create_date", "user_id")
    def _compute_can_edit_now(self):
        cutoff_hours = self._get_edit_cutoff_hours()
        now = fields.Datetime.now()
        is_manager = self.env.user.has_group(MANAGER_GROUP)
        for rec in self:
            if is_manager:
                rec.can_edit_now = True
            elif rec.user_id != self.env.user:
                rec.can_edit_now = False
            elif not rec.create_date:
                rec.can_edit_now = True
            elif cutoff_hours <= 0:
                rec.can_edit_now = False
            else:
                elapsed = (now - rec.create_date).total_seconds() / 3600.0
                rec.can_edit_now = elapsed < cutoff_hours

    @api.model
    def _get_edit_cutoff_hours(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "mngglobal_logs.edit_cutoff_hours", "24"
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            return 24

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = self.env.user.has_group(MANAGER_GROUP)
        for vals in vals_list:
            if not is_manager:
                vals["user_id"] = self.env.user.id
            else:
                vals.setdefault("user_id", self.env.user.id)
        return super().create(vals_list)

    @api.model
    def get_monthly_matrix(self, year, month):
        """Build a (date × user) matrix for the given month.

        Returns:
            {
                "year": int, "month": int,
                "month_label": "2026 он 06 сар",
                "users": [{id, name, login, color}, ...],
                "dates": [{iso, day, label, weekday, is_weekend, is_today}, ...],
                "entries": {"<iso>_<uid>": {id, description, time_slot, can_edit, ...}, ...},
                "stats": {"<uid>": int_count},
                "is_manager": bool,
                "current_uid": int,
                "cutoff_hours": int,
            }
        """
        year = int(year)
        month = int(month)
        _, ndays = calendar.monthrange(year, month)
        start = datetime.date(year, month, 1)
        end = datetime.date(year, month, ndays)
        today = datetime.date.today()

        # All employee-like users (non-shared, active)
        users = self.env["res.users"].sudo().search(
            [("active", "=", True), ("share", "=", False)],
            order="name",
        )
        users_data = [
            {"id": u.id, "name": u.name or u.login, "login": u.login,
             "color": (u.id * 7) % 360}  # stable hue per user
            for u in users
        ]

        is_manager = self.env.user.has_group(MANAGER_GROUP)
        current_uid = self.env.user.id
        cutoff_hours = self._get_edit_cutoff_hours()
        now_dt = fields.Datetime.now()

        entries = self.search([
            ("log_date", ">=", start),
            ("log_date", "<=", end),
        ])
        entries_data = {}
        stats = {u["id"]: 0 for u in users_data}
        for e in entries:
            iso = e.log_date.isoformat()
            key = f"{iso}_{e.user_id.id}"
            # compute can_edit (matches write() guard logic)
            if is_manager:
                can_edit = True
            elif e.user_id.id != current_uid:
                can_edit = False
            elif cutoff_hours <= 0:
                can_edit = False
            elif e.create_date:
                elapsed = (now_dt - e.create_date).total_seconds() / 3600.0
                can_edit = elapsed < cutoff_hours
            else:
                can_edit = True
            entries_data[key] = {
                "id": e.id,
                "description": e.description or "",
                "time_slot": e.time_slot or "",
                "user_id": e.user_id.id,
                "log_date": iso,
                "can_edit": can_edit,
                "active": e.active,
            }
            if e.user_id.id in stats:
                stats[e.user_id.id] += 1

        # Mongolian weekday short names
        weekday_mn = ["Дав", "Мяг", "Лха", "Пүр", "Баа", "Бям", "Ням"]
        dates_data = []
        for day in range(1, ndays + 1):
            d = datetime.date(year, month, day)
            dates_data.append({
                "iso": d.isoformat(),
                "day": day,
                "label": f"{weekday_mn[d.weekday()]} {day:02d}",
                "weekday": d.weekday(),
                "is_weekend": d.weekday() >= 5,
                "is_today": d == today,
            })

        return {
            "year": year,
            "month": month,
            "month_label": f"{year} он {month:02d} сар",
            "users": users_data,
            "dates": dates_data,
            "entries": entries_data,
            "stats": stats,
            "is_manager": is_manager,
            "current_uid": current_uid,
            "cutoff_hours": cutoff_hours,
        }

    def write(self, vals):
        if not vals:
            return super().write(vals)
        is_manager = self.env.user.has_group(MANAGER_GROUP)
        if not is_manager:
            if "user_id" in vals and any(
                vals["user_id"] != rec.user_id.id for rec in self
            ):
                raise AccessError(_(
                    "Бүртгэлийн эзэмшигчийг өөрчилж болохгүй."
                ))
            cutoff_hours = self._get_edit_cutoff_hours()
            now = fields.Datetime.now()
            for rec in self:
                if rec.user_id != self.env.user:
                    raise AccessError(_(
                        "Бусдын бүртгэлийг засварлах эрхгүй."
                    ))
                if cutoff_hours <= 0:
                    raise UserError(_(
                        "Тохиргооны дагуу бүртгэлийг үүсгэсэн даруйд цоожилно. "
                        "Менежертэй холбогдоно уу."
                    ))
                if rec.create_date:
                    elapsed = (now - rec.create_date).total_seconds() / 3600.0
                    if elapsed >= cutoff_hours:
                        raise UserError(_(
                            "Энэ бүртгэлийг засварлах %d цагийн хугацаа дууссан. "
                            "Менежертэй холбогдоно уу."
                        ) % cutoff_hours)
        return super().write(vals)


class MngDailyReport(models.Model):
    _name = "mng.daily.report"
    _description = "Өдрийн тайлан"
    _inherit = ["mng.daily.log.mixin"]

    @api.constrains("log_date")
    def _check_log_date_not_future(self):
        today = fields.Date.context_today(self)
        is_manager = self.env.user.has_group(MANAGER_GROUP)
        if is_manager:
            return
        for rec in self:
            if rec.log_date and rec.log_date > today:
                raise ValidationError(_(
                    "Тайлан нь ирээдүйн огноогоор оруулах боломжгүй."
                ))


class MngDailyPlan(models.Model):
    _name = "mng.daily.plan"
    _description = "Өдрийн төлөвлөгөө"
    _inherit = ["mng.daily.log.mixin"]

    @api.constrains("log_date")
    def _check_log_date_not_past(self):
        today = fields.Date.context_today(self)
        is_manager = self.env.user.has_group(MANAGER_GROUP)
        if is_manager:
            return
        for rec in self:
            if rec.log_date and rec.log_date < today:
                raise ValidationError(_(
                    "Төлөвлөгөөг өнгөрсөн огноогоор оруулах боломжгүй."
                ))
