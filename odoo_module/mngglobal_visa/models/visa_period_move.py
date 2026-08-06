from odoo import fields, models


class MngVisaPeriodMove(models.Model):
    """Immutable audit trail for an application's cohort assignment."""

    _name = "mng.visa.period.move"
    _description = "Элсэлтийн үеийн шилжилт"
    _order = "moved_at desc, id desc"

    application_id = fields.Many2one(
        "mng.visa.application", string="Хүсэлт",
        required=True, ondelete="cascade", index=True)
    from_period_id = fields.Many2one(
        "mng.visa.recruitment.period", string="Өмнөх элсэлтийн үе",
        ondelete="set null")
    to_period_id = fields.Many2one(
        "mng.visa.recruitment.period", string="Шинэ элсэлтийн үе",
        ondelete="set null")
    move_type = fields.Selection([
        ("initial", "Анхны бүртгэл"),
        ("assign", "Элсэлтийн үед хуваарилсан"),
        ("move", "Элсэлтийн үе сольсон"),
        ("defer", "Дараагийн элсэлтэд шилжүүлсэн"),
        ("unassign", "Элсэлтийн үеэс гаргасан"),
    ], string="Үйлдэл", required=True, default="move")
    reason = fields.Text(string="Шалтгаан")
    moved_at = fields.Datetime(
        string="Огноо", required=True, default=fields.Datetime.now, index=True)
    moved_by = fields.Many2one(
        "res.users", string="Шилжүүлсэн", required=True,
        default=lambda self: self.env.user, readonly=True)
    new_application_id = fields.Many2one(
        "mng.visa.application", string="Шинэ гэрээ",
        ondelete="set null",
        help="Хойшлуулж шинээр үүсгэсэн гэрээ.")
