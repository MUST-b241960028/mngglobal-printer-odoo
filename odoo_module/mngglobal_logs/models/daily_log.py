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
