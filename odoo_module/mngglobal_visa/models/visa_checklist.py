from odoo import models, fields


class MngVisaChecklistItem(models.Model):
    _name = "mng.visa.checklist.item"
    _description = "Шалгах хуудас"
    _order = "sequence, id"

    application_id = fields.Many2one(
        "mng.visa.application", string="Гэрээ",
        required=True, ondelete="cascade")
    name = fields.Char(string="Даалгавар", required=True)
    sequence = fields.Integer(default=10)
    is_done = fields.Boolean(string="Хийгдсэн")
    done_date = fields.Date(string="Хийсэн огноо")
    done_by = fields.Many2one("res.users", string="Хийсэн хүн")
    notes = fields.Text(string="Тэмдэглэл")


class MngVisaChecklistTemplate(models.Model):
    _name = "mng.visa.checklist.template"
    _description = "Шалгах хуудасны загвар"
    _order = "program_type_id, stage_id, sequence"

    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        required=True, ondelete="cascade")
    stage_id = fields.Many2one(
        "mng.visa.stage", string="Үе шат",
        domain="[('program_type_id', '=', program_type_id)]")
    name = fields.Char(string="Даалгавар", required=True)
    sequence = fields.Integer(default=10)
