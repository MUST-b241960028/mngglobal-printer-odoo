from odoo import models, fields


class MngVisaProgramType(models.Model):
    _name = "mng.visa.program.type"
    _description = "Зуучлалын хөтөлбөрийн төрөл"
    _order = "sequence, id"

    name = fields.Char(string="Нэр", required=True)
    code = fields.Char(string="Код", required=True)
    sequence = fields.Integer(default=10)
    visa_type = fields.Selection([
        ("student", "Оюутан"),
        ("work", "Ажилтан / Дадлагажигч"),
        ("camp", "Camp / Зуны хөтөлбөр"),
    ], string="Визний төрөл", required=True, default="student")
    active = fields.Boolean(default=True)

    stage_ids = fields.One2many(
        "mng.visa.stage", "program_type_id", string="Үе шатууд")
