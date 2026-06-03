from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    daily_log_edit_cutoff_hours = fields.Integer(
        string="Засварлах хугацааны хязгаар (цаг)",
        config_parameter="mngglobal_logs.edit_cutoff_hours",
        default=24,
        help="Үүсгэснээс хойш энэ хэдэн цагийн дотор ажилтан өөрийн бүртгэлийг "
             "засварлах боломжтой. Дараа нь зөвхөн менежер засварлана. "
             "0 = шууд цоожлох, маш том утга = хязгааргүй.",
    )
