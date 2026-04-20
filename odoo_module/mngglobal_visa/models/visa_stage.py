from odoo import models, fields


class MngVisaStage(models.Model):
    _name = "mng.visa.stage"
    _description = "Зуучлалын үе шат"
    _order = "program_type_id, sequence, id"

    name = fields.Char(string="Нэр", required=True, translate=True)
    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр", required=True,
        ondelete="cascade")
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(
        string="Kanban-д хураах",
        help="Энэ үе шатыг kanban-д хураасан байдлаар харуулна")
    is_done = fields.Boolean(string="Дууссан үе шат")
    is_failed = fields.Boolean(string="Амжилтгүй үе шат")
    is_yellow_card = fields.Boolean(
        string="Шар хуудасны үе шат",
        help="Энэ үе шатад орох үед шар хуудасны огноо автоматаар тэмдэглэгдэнэ")
