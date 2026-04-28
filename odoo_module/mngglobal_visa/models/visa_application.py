from odoo import models, fields, api


class MngVisaApplication(models.Model):
    _name = "mng.visa.application"
    _description = "Зуучлалын өргөдөл"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, create_date desc"
    _rec_name = "display_name"

    # Sequence
    name = fields.Char(
        string="Дугаар", readonly=True, copy=False, default="New")

    display_name = fields.Char(
        compute="_compute_display_name", store=True)

    @api.depends("name", "partner_id.name")
    def _compute_display_name(self):
        for rec in self:
            client = rec.partner_id.name or "—"
            rec.display_name = f"{rec.name} — {client}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "mng.visa.application") or "New"
        records = super().create(vals_list)
        for rec in records:
            if rec.program_type_id and rec.stage_id:
                rec._populate_checklist_from_template(rec.stage_id)
        return records

    # Program & Stage
    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        required=True, tracking=True)
    program_code = fields.Char(
        related="program_type_id.code", string="Хөтөлбөрийн код", store=True)
    stage_id = fields.Many2one(
        "mng.visa.stage", string="Үе шат",
        tracking=True, group_expand="_read_group_stage_ids",
        domain="[('program_type_id', '=', program_type_id)]",
        copy=False)
    priority = fields.Selection([
        ("0", "Энгийн"),
        ("1", "Чухал"),
        ("2", "Өндөр"),
        ("3", "Яаралтай"),
    ], string="Ач холбогдол", default="0", tracking=True)
    kanban_state = fields.Selection([
        ("normal", "Хэвийн"),
        ("done", "Бэлэн"),
        ("blocked", "Саатсан"),
    ], string="Kanban төлөв", default="normal")
    active = fields.Boolean(default=True)

    # Client (res.partner)
    partner_id = fields.Many2one(
        "res.partner", string="Үйлчлүүлэгч",
        required=True, tracking=True,
        domain="[('user_ids', '=', False)]")
    client_phone = fields.Char(
        related="partner_id.phone", string="Утас", readonly=False)
    client_email = fields.Char(
        related="partner_id.email", string="Имэйл", readonly=False)
    passport_number = fields.Char(string="Паспортын дугаар", tracking=True)
    passport_expiry = fields.Date(string="Паспорт дуусах")
    date_of_birth = fields.Date(string="Төрсөн он")

    # Kids program fields
    parent_name = fields.Char(string="Эцэг/эхийн нэр")
    parent_phone = fields.Char(string="Эцэг/эхийн утас")
    teacher_id = fields.Many2one(
        "res.users", string="Хариуцсан багш",
        help="Филиппин хүүхдийн хөтөлбөрийн хариуцсан багш")

    # Program details
    school_name = fields.Char(string="Сургуулийн нэр")
    city = fields.Char(string="Хот")
    program_duration = fields.Char(string="Хугацаа")
    departure_date = fields.Date(string="Нисэх огноо", tracking=True)

    # Staff
    assigned_to = fields.Many2one(
        "res.users", string="Хариуцагч",
        default=lambda self: self.env.uid, tracking=True)

    # Finance
    total_fee = fields.Monetary(string="Нийт хураамж", currency_field="currency_id")
    remaining_fee = fields.Monetary(
        string="Үлдэгдэл", compute="_compute_remaining",
        currency_field="currency_id", store=True)
    currency_id = fields.Many2one(
        "res.currency", string="Валют",
        default=lambda self: self.env.company.currency_id)
    payment_status = fields.Selection([
        ("unpaid", "Төлөөгүй"),
        ("partial", "Хэсэгчлэн"),
        ("paid", "Бүрэн төлсөн"),
    ], string="Төлбөрийн төлөв", default="unpaid",
        compute="_compute_payment_status", store=True, tracking=True)
    payment_ids = fields.One2many(
        "mng.visa.payment", "application_id", string="Төлбөрүүд")
    invoice_ids = fields.Many2many(
        "account.move", string="Нэхэмжлэлүүд",
        copy=False)
    invoice_count = fields.Integer(
        compute="_compute_invoice_count")

    # Documents
    document_ids = fields.One2many(
        "mng.visa.document", "application_id", string="Бичиг баримтууд")
    document_count = fields.Integer(
        compute="_compute_document_count", string="Бичиг баримт")

    # Checklist
    checklist_ids = fields.One2many(
        "mng.visa.checklist.item", "application_id", string="Шалгах хуудас")
    checklist_progress = fields.Float(
        string="Явц %", compute="_compute_checklist_progress", store=True)

    # Yellow card
    date_yellow_card = fields.Date(string="Шар хуудас гарсан огноо", tracking=True)

    # Insurance
    insurance_done = fields.Boolean(string="Даатгал хийсэн", tracking=True)
    insurance_date = fields.Date(string="Даатгал хийсэн огноо")
    insurance_due_date = fields.Date(
        string="Даатгал хийх эцсийн огноо",
        compute="_compute_insurance_due", store=True)

    # Dates (auto-set on stage change)
    date_inquiry = fields.Date(string="Лавлагаа авсан")
    date_contract = fields.Date(string="Гэрээ хийсэн")
    date_submitted = fields.Date(string="Мэдүүлсэн")
    date_result = fields.Date(string="Хариу ирсэн")
    date_departed = fields.Date(string="Нисэж явсан")
    date_done = fields.Date(string="Дууссан")

    # Notes
    notes = fields.Html(string="Тэмдэглэл")
    rejection_reason = fields.Text(string="Татгалзсан шалтгаан")

    # Color for kanban
    color = fields.Integer(string="Өнгө")

    # Computed

    @api.depends("departure_date")
    def _compute_insurance_due(self):
        from datetime import timedelta
        for rec in self:
            if rec.departure_date:
                rec.insurance_due_date = rec.departure_date - timedelta(days=7)
            else:
                rec.insurance_due_date = False

    @api.depends("total_fee", "payment_ids.amount", "payment_ids.state")
    def _compute_remaining(self):
        for rec in self:
            paid = sum(p.amount for p in rec.payment_ids if p.state == "paid")
            rec.remaining_fee = max(rec.total_fee - paid, 0)

    @api.depends("remaining_fee", "total_fee")
    def _compute_payment_status(self):
        for rec in self:
            if rec.total_fee <= 0:
                rec.payment_status = "unpaid"
            elif rec.remaining_fee <= 0:
                rec.payment_status = "paid"
            elif rec.remaining_fee < rec.total_fee:
                rec.payment_status = "partial"
            else:
                rec.payment_status = "unpaid"

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    @api.depends("checklist_ids", "checklist_ids.is_done")
    def _compute_checklist_progress(self):
        for rec in self:
            total = len(rec.checklist_ids)
            done = len(rec.checklist_ids.filtered("is_done"))
            rec.checklist_progress = (done / total * 100) if total else 0

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Show all stages for the current program type in kanban."""
        program_type_id = self.env.context.get("default_program_type_id")
        if program_type_id:
            return stages.search(
                [("program_type_id", "=", program_type_id)],
                order="sequence")
        return stages.search([], order="sequence")

    # Stage change tracking

    def write(self, vals):
        if "stage_id" in vals:
            stage = self.env["mng.visa.stage"].browse(vals["stage_id"])
            today = fields.Date.today()
            if stage.sequence <= 1:
                vals.setdefault("date_inquiry", today)
            if stage.is_done:
                vals.setdefault("date_done", today)
            if stage.is_yellow_card:
                vals.setdefault("date_yellow_card", today)
        result = super().write(vals)
        if "stage_id" in vals:
            stage = self.env["mng.visa.stage"].browse(vals["stage_id"])
            for rec in self:
                rec._populate_checklist_from_template(stage)
        return result

    def _populate_checklist_from_template(self, stage):
        """Add checklist items from template for the given stage (skips duplicates)."""
        self.ensure_one()
        if not self.program_type_id:
            return
        templates = self.env["mng.visa.checklist.template"].search([
            ("program_type_id", "=", self.program_type_id.id),
            ("stage_id", "=", stage.id),
        ], order="sequence")
        if not templates:
            return
        existing_names = set(self.checklist_ids.mapped("name"))
        ChecklistItem = self.env["mng.visa.checklist.item"]
        for tmpl in templates:
            if tmpl.name not in existing_names:
                ChecklistItem.create({
                    "application_id": self.id,
                    "name": tmpl.name,
                    "sequence": tmpl.sequence,
                })

    @api.onchange("program_type_id")
    def _onchange_program_type(self):
        """Set first stage when program type changes."""
        if self.program_type_id:
            first = self.env["mng.visa.stage"].search(
                [("program_type_id", "=", self.program_type_id.id)],
                order="sequence", limit=1)
            self.stage_id = first

    # Actions

    def action_create_invoice(self):
        """Create an invoice for this application."""
        self.ensure_one()
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_line_ids": [(0, 0, {
                "name": f"Зуучлалын хураамж — {self.name}",
                "quantity": 1,
                "price_unit": self.remaining_fee or self.total_fee,
            })],
        })
        self.invoice_ids = [(4, invoice.id)]
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_invoices(self):
        """Open related invoices."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "name": "Нэхэмжлэлүүд",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
        }

    def action_open_documents(self):
        """Open attached documents for this application."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.document",
            "name": "Бичиг баримтууд",
            "view_mode": "list,form",
            "domain": [("application_id", "=", self.id)],
            "context": {"default_application_id": self.id},
        }

    def action_generate_fee_schedule(self):
        """Generate payment records from fee templates for this program."""
        self.ensure_one()
        from datetime import timedelta
        templates = self.env["mng.visa.fee.template"].search([
            ("program_type_id", "=", self.program_type_id.id),
        ], order="sequence")
        if not templates:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": "Энэ хөтөлбөрт тохирох төлбөрийн загвар байхгүй байна.",
                    "type": "warning",
                },
            }
        created = 0
        for tmpl in templates:
            if tmpl.fee_type == "percentage":
                amount = self.total_fee * tmpl.percentage / 100
            else:
                amount = tmpl.fixed_amount
            due_date = False
            self.env["mng.visa.payment"].create({
                "application_id": self.id,
                "name": tmpl.name,
                "amount": amount,
                "currency_id": tmpl.currency_id.id,
                "payment_method": tmpl.payment_method or False,
                "date_due": due_date,
            })
            created += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": f"{created} төлбөрийн бичлэг үүслээ.",
                "type": "success",
            },
        }
