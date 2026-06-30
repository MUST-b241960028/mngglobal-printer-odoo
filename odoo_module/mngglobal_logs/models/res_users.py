from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    show_in_daily_logs = fields.Boolean(
        string="Лог матриц дээр харагдах",
        default=True,
        help="Хэрэв чагтыг авбал энэ ажилтан MNG Лог сарын ширээн дээр "
             "багана болж харагдахгүй. Хуучин бүртгэлүүд хадгалагдсаар "
             "байх боловч матрицын харагдацнаас нуугдана.",
    )

    def write(self, vals):
        # Allow visa managers to toggle ONLY show_in_daily_logs without
        # granting them blanket res.users write access. Anything else falls
        # through to standard permissions.
        if (
            set(vals.keys()) == {"show_in_daily_logs"}
            and self.env.user.has_group("mngglobal_visa.group_visa_manager")
            and not self.env.user._is_admin()
        ):
            return super(ResUsers, self.sudo()).write(vals)
        return super().write(vals)
