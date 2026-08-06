from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gemini_api_key = fields.Char(
        string="Gemini API Key",
        config_parameter="mngglobal_visa.gemini_api_key",
        help="Google AI Studio API Key (https://aistudio.google.com)"
    )
    gemini_model = fields.Selection(
        [
            ("gemini-2.5-flash", "Gemini 2.5 Flash (Хурдан / Задалбар)"),
            ("gemini-2.5-pro", "Gemini 2.5 Pro (Өндөр чадамжтай)"),
        ],
        string="Gemini загвар",
        default="gemini-2.5-flash",
        config_parameter="mngglobal_visa.gemini_model",
        help="Паспорт OCR-д ашиглах Gemini загвар"
    )
