from odoo import models, fields


class MngVisaProgramType(models.Model):
    _name = "mng.visa.program.type"
    _description = "Зуучлалын хөтөлбөрийн төрөл"
    _order = "sequence, id"

    name = fields.Char(string="Нэр", required=True)
    code = fields.Char(string="Код", required=True)
    sequence = fields.Integer(default=10)
    country_id = fields.Many2one("res.country", string="Улс")
    visa_type = fields.Selection([
        ("student", "Оюутан"),
        ("work", "Ажилтан / Дадлагажигч"),
        ("camp", "Camp / Зуны хөтөлбөр"),
    ], string="Визний төрөл", required=True, default="student")
    description = fields.Text(string="Тайлбар")
    active = fields.Boolean(default=True)

    stage_ids = fields.One2many(
        "mng.visa.stage", "program_type_id", string="Үе шатууд")
    application_count = fields.Integer(
        string="Өргөдлийн тоо", compute="_compute_application_count")

    def _compute_application_count(self):
        for rec in self:
            rec.application_count = self.env["mng.visa.application"].search_count(
                [("program_type_id", "=", rec.id)])
