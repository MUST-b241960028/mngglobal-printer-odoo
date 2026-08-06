from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape


class MngVisaApplication(models.Model):
    _name = "mng.visa.application"
    _description = "Зуучлалын гэрээ"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, create_date desc"
    _rec_name = "display_name"

    # Sequence
    name = fields.Char(
        string="Дугаар", readonly=True, copy=False, default="New")

    display_name = fields.Char(
        compute="_compute_display_name", store=True)

    @api.depends("name", "client_name")
    def _compute_display_name(self):
        for rec in self:
            client = rec.client_name or "—"
            rec.display_name = f"{rec.name} — {client}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "mng.visa.application") or "New"
        records = super().create(vals_list)
        for rec in records:
            if rec.program_type_id:
                rec._populate_all_checklists()
        return records

    # Program & Stage
    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        required=True, tracking=True)
    program_code = fields.Char(
        related="program_type_id.code", string="Хөтөлбөрийн код", store=True)
    recruitment_period_id = fields.Many2one(
        "mng.visa.recruitment.period", string="Элсэлтийн үе / Хавтас",
        domain="['&', ('state', '!=', 'archived'), '|', ('program_type_id', '=', False), ('program_type_id', '=', program_type_id)]",
        tracking=True, help="Сурагч/хэрэглэгчийн бүртгэгдсэн элсэлтийн хугацааны хавтас")
    period_move_ids = fields.One2many(
        "mng.visa.period.move", "application_id", string="Элсэлтийн үеийн түүх")
    period_move_count = fields.Integer(
        compute="_compute_period_move_count", string="Шилжилт")
    previous_application_id = fields.Many2one(
        "mng.visa.application", string="Өмнөх аппликейшн",
        ondelete="set null", copy=False, readonly=True)
    deferred_application_ids = fields.One2many(
        "mng.visa.application", "previous_application_id",
        string="Дараагийн аппликейшнүүд")
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

    # Client info (plain text — no contact database)
    client_name = fields.Char(
        string="Үйлчлүүлэгч", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Холбоостой харилцагч")
    client_phone = fields.Char(string="Утас", tracking=True)
    client_email = fields.Char(string="Имэйл")
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

    # Meetings
    meeting_ids = fields.Many2many(
        "calendar.event", string="Уулзалтууд", copy=False)
    meeting_count = fields.Integer(
        compute="_compute_meeting_count", string="Уулзалт")

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

    def _compute_meeting_count(self):
        for rec in self:
            rec.meeting_count = len(rec.meeting_ids)

    @api.depends("period_move_ids")
    def _compute_period_move_count(self):
        for rec in self:
            rec.period_move_count = len(rec.period_move_ids)

    def action_schedule_meeting(self):
        """Open calendar event form pre-filled with client info."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "calendar.event",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_name": f"Уулзалт — {self.client_name or ''} ({self.name})",
                "default_user_id": self.env.uid,
            },
        }

    def action_open_meetings(self):
        """Open list of meetings linked to this application."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "calendar.event",
            "name": "Уулзалтууд",
            "view_mode": "list,form,calendar",
            "domain": [("id", "in", self.meeting_ids.ids)],
            "context": {
                "default_name": f"Уулзалт — {self.client_name or ''} ({self.name})",
            },
        }

    @api.depends("stage_id", "stage_id.sequence", "program_type_id", "checklist_ids", "checklist_ids.is_done")
    def _compute_checklist_progress(self):
        Stage = self.env["mng.visa.stage"]
        stage_cache = {}
        for rec in self:
            if not rec.program_type_id or not rec.stage_id:
                rec.checklist_progress = 0.0
                continue

            pid = rec.program_type_id.id
            if pid not in stage_cache:
                stage_cache[pid] = Stage.search(
                    [("program_type_id", "=", pid)], order="sequence"
                ).ids

            all_ids = stage_cache[pid]
            total_stages = len(all_ids)
            if not total_stages:
                rec.checklist_progress = 0.0
                continue

            try:
                stage_index = all_ids.index(rec.stage_id.id)
            except ValueError:
                stage_index = 0

            total_checks = len(rec.checklist_ids)
            done_checks = len(rec.checklist_ids.filtered("is_done"))
            checklist_fraction = (done_checks / total_checks) if total_checks else 1.0

            rec.checklist_progress = (stage_index + checklist_fraction) / total_stages * 100

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

    @api.constrains("program_type_id", "recruitment_period_id")
    def _check_recruitment_period_program(self):
        for rec in self:
            period_program = rec.recruitment_period_id.program_type_id
            if period_program and period_program != rec.program_type_id:
                raise ValidationError(_(
                    "Сонгосон элсэлтийн үе нь тухайн хөтөлбөрт хамаарахгүй байна."
                ))

    def write(self, vals):
        old_periods = {}
        period_changed = "recruitment_period_id" in vals
        if period_changed:
            old_periods = {
                rec.id: rec.recruitment_period_id for rec in self
            }

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

        if period_changed and not self.env.context.get("mng_skip_period_history"):
            move_type = "move" if vals.get("recruitment_period_id") else "unassign"
            reason = self.env.context.get("mng_period_move_reason")
            for rec in self:
                from_period = old_periods[rec.id]
                if from_period != rec.recruitment_period_id:
                    rec._record_period_change(
                        from_period, rec.recruitment_period_id, move_type, reason
                    )
        return result

    def _validate_target_period(self, target_period):
        self.ensure_one()
        if not target_period or not target_period.exists():
            raise UserError(_("Шинэ элсэлтийн үе сонгоно уу."))
        if target_period.state == "archived":
            raise UserError(_("Архивлагдсан элсэлтийн үе рүү шилжүүлэх боломжгүй."))
        if (
            target_period.program_type_id
            and target_period.program_type_id != self.program_type_id
        ):
            raise UserError(_(
                "'%s' элсэлтийн үе нь '%s' хөтөлбөрт хамаарахгүй байна."
            ) % (target_period.name, self.program_type_id.name))

    def _record_period_change(
        self, from_period, to_period, move_type, reason=False,
        new_application=False,
    ):
        self.ensure_one()
        move = self.env["mng.visa.period.move"].create({
            "application_id": self.id,
            "from_period_id": from_period.id if from_period else False,
            "to_period_id": to_period.id if to_period else False,
            "move_type": move_type,
            "reason": reason or False,
            "new_application_id": new_application.id if new_application else False,
        })

        labels = dict(move._fields["move_type"].selection)
        from_name = html_escape(from_period.name) if from_period else _("Хуваарилаагүй")
        to_name = html_escape(to_period.name) if to_period else _("Хуваарилаагүй")
        body = "<p><b>%s</b>: %s &rarr; %s" % (
            html_escape(labels[move_type]), from_name, to_name,
        )
        if reason:
            body += "<br/><span>%s</span>" % html_escape(reason)
        if new_application:
            body += "<br/><span>%s: %s</span>" % (
                _("Шинэ аппликейшн"), html_escape(new_application.display_name),
            )
        self.message_post(body=body + "</p>")
        return move

    def action_move_to_period(self, target_period, reason=False, move_type="move"):
        """Move the current case while preserving a visible audit history."""
        self.ensure_one()
        target_period = self.env["mng.visa.recruitment.period"].browse(
            target_period.id if hasattr(target_period, "id") else target_period
        )
        self._validate_target_period(target_period)
        from_period = self.recruitment_period_id
        if from_period == target_period:
            return False

        self.with_context(mng_skip_period_history=True).write({
            "recruitment_period_id": target_period.id,
        })
        return self._record_period_change(
            from_period, target_period, move_type, reason
        )

    def action_defer_to_period(self, target_period, reason):
        """Create a fresh case for a later cohort without copying case artifacts."""
        self.ensure_one()
        target_period = self.env["mng.visa.recruitment.period"].browse(
            target_period.id if hasattr(target_period, "id") else target_period
        )
        self._validate_target_period(target_period)

        Stage = self.env["mng.visa.stage"]
        first_stage = Stage.search(
            [("program_type_id", "=", self.program_type_id.id)],
            order="sequence, id", limit=1,
        )
        values = {
            "program_type_id": self.program_type_id.id,
            "recruitment_period_id": target_period.id,
            "stage_id": first_stage.id,
            "previous_application_id": self.id,
            "priority": self.priority,
            "partner_id": self.partner_id.id,
            "client_name": self.client_name,
            "client_phone": self.client_phone,
            "client_email": self.client_email,
            "passport_number": self.passport_number,
            "passport_expiry": self.passport_expiry,
            "date_of_birth": self.date_of_birth,
            "parent_name": self.parent_name,
            "parent_phone": self.parent_phone,
            "teacher_id": self.teacher_id.id,
            "school_name": self.school_name,
            "city": self.city,
            "program_duration": self.program_duration,
            "assigned_to": self.assigned_to.id,
            "currency_id": self.currency_id.id,
        }
        new_application = self.env["mng.visa.application"].create(values)
        self._record_period_change(
            self.recruitment_period_id, target_period, "defer", reason,
            new_application=new_application,
        )
        new_application.message_post(
            body="<p><b>%s</b>: %s</p>" % (
                _("Өмнөх аппликейшнээс үүсгэсэн"),
                html_escape(self.display_name),
            )
        )
        return new_application

    def action_open_move_period_wizard(self):
        self.ensure_one()
        return {
            "name": _("Элсэлтийн үе солих"),
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.period.move.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_application_id": self.id,
                "default_mode": "move",
            },
        }

    def action_open_defer_period_wizard(self):
        self.ensure_one()
        return {
            "name": _("Дараагийн элсэлтэд шилжүүлэх"),
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.period.move.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_application_id": self.id,
                "default_mode": "defer",
            },
        }

    def action_open_period_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Элсэлтийн үеийн түүх"),
            "res_model": "mng.visa.period.move",
            "view_mode": "list,form",
            "domain": [("application_id", "=", self.id)],
            "context": {"default_application_id": self.id},
        }

    def _populate_all_checklists(self):
        """Load ALL checklist items for this program at once (skips duplicates)."""
        self.ensure_one()
        if not self.program_type_id:
            return
        templates = self.env["mng.visa.checklist.template"].search([
            ("program_type_id", "=", self.program_type_id.id),
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
        """Set first stage and populate all checklists when program type changes."""
        if self.program_type_id:
            first = self.env["mng.visa.stage"].search(
                [("program_type_id", "=", self.program_type_id.id)],
                order="sequence", limit=1)
            self.stage_id = first

    # Actions

    def _get_or_create_partner(self):
        """Auto-create a minimal res.partner from client_name for invoicing.
        Odoo invoices require a partner_id — this creates one transparently."""
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        # Try to find existing partner by name
        partner = self.env["res.partner"].search(
            [("name", "=", self.client_name)], limit=1)
        if not partner:
            partner = self.env["res.partner"].create({
                "name": self.client_name,
                "phone": self.client_phone or False,
                "email": self.client_email or False,
                "company_type": "person",
            })
        self.partner_id = partner
        return partner

    def action_create_invoice(self):
        """Create an invoice for this application."""
        self.ensure_one()
        partner = self._get_or_create_partner()
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_line_ids": [(0, 0, {
                "name": f"Зуучлалын хураамж — {self.client_name} — {self.name}",
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

    def action_open_passport_ocr(self):
        """
        Паспорт OCR унших визардыг нээнэ.
        """
        self.ensure_one()
        return {
            "name": _("✨ AI Паспорт Унших"),
            "type": "ir.actions.act_window",
            "res_model": "mng.visa.passport.ocr.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_application_id": self.id,
            }
        }

    def action_generate_ai_message(self):
        """
        Оюутанд сануулга / дараагийн алхмын тухай Монгол мессеж бэлдэнэ.
        """
        self.ensure_one()
        import json
        import urllib.request
        import urllib.error

        api_key = self.env["ir.config_parameter"].sudo().get_param("mngglobal_visa.gemini_api_key")
        model = self.env["ir.config_parameter"].sudo().get_param("mngglobal_visa.gemini_model", "gemini-2.5-flash")

        if not api_key:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Анхааруулга",
                    "message": "Gemini API Key тохируулагдаагүй байна. Тохиргоо -> AI Тохиргоо хэсэгт API Key оруулна уу.",
                    "type": "warning",
                }
            }

        missing_checklists = self.checklist_ids.filtered(lambda c: not c.is_done).mapped("name")
        lead_data = {
            "client_name": self.client_name or "Үйлчлүүлэгч",
            "program": self.program_type_id.name or "Хөтөлбөр",
            "stage": self.stage_id.name or "Эхлэл",
            "payment_status": self.payment_status,
            "remaining_fee": self.remaining_fee,
            "missing_checklist_items": missing_checklists,
            "departure_date": str(self.departure_date) if self.departure_date else None,
        }

        prompt = f"""
Draft a polite, professional Mongolian SMS/Chat follow-up message from MNG Global agency to the student:
Student Details:
{json.dumps(lead_data, ensure_ascii=False, indent=2)}

Keep it concise, friendly, and clear. Outline the next steps or missing items.
Output ONLY the message text in Mongolian. No greeting tags like 'Subject:'.
"""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3}
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            msg_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Post to chatter
            self.message_post(
                body=f"<b>✨ AI Мессеж бэлдэгч:</b><br/><pre style='white-space: pre-wrap;'>{msg_text}</pre>",
                message_type="comment"
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "AI Мессеж бэлэн боллоо!",
                    "message": "AI-аас бэлдсэн мессежийг Chatter (Доод хэсэг)-т нэмлээ.",
                    "type": "success",
                    "sticky": False,
                }
            }
        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Алдаа",
                    "message": f"AI Мессеж үүсгэхэд алдаа гарлаа: {str(e)}",
                    "type": "danger",
                }
            }
