from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

MANAGER_GROUP = "mngglobal_visa.group_visa_manager"

ACCENTS = [
    ("teal", "Хөх ногоон"),
    ("blue", "Цэнхэр"),
    ("violet", "Ягаан"),
    ("coral", "Улаан"),
    ("gold", "Шар"),
    ("green", "Ногоон"),
    ("slate", "Саарал"),
]

SNIPPET_RADIUS = 90


class MngTopicCategory(models.Model):
    _name = "mng.topic.category"
    _description = "Мэдээллийн ангилал"
    _order = "sequence, name"

    name = fields.Char(string="Нэр", required=True)
    accent = fields.Selection(ACCENTS, string="Өнгө", default="slate", required=True)
    sequence = fields.Integer(string="Дараалал", default=10)
    active = fields.Boolean(default=True)
    topic_ids = fields.One2many("mng.topic", "category_id", string="Сэдвүүд")
    topic_count = fields.Integer(string="Сэдвийн тоо", compute="_compute_topic_count")

    @api.depends("topic_ids")
    def _compute_topic_count(self):
        for rec in self:
            rec.topic_count = len(rec.topic_ids)


class MngTopic(models.Model):
    _name = "mng.topic"
    _description = "Мэдээллийн сэдэв"
    _order = "is_pinned desc, last_edited_at desc, id desc"

    name = fields.Char(string="Сэдвийн нэр", required=True)
    summary = fields.Char(
        string="Товч тайлбар",
        help="Дуудлага хүлээн авч буй ажилтан юуны тухай сэдэв болохыг нэг мөрөөс ойлгоно.",
    )
    category_id = fields.Many2one(
        "mng.topic.category", string="Ангилал", ondelete="restrict", index=True)
    program_type_id = fields.Many2one(
        "mng.visa.program.type", string="Хөтөлбөр",
        help="Тухайн хөтөлбөрт хамаарах бол сонгоно.")
    recruitment_period_id = fields.Many2one(
        "mng.visa.recruitment.period", string="Элсэлтийн үе",
        help="Тодорхой элсэлтийн үеийн мэдээлэл бол сонгоно.")
    page_ids = fields.One2many("mng.topic.page", "topic_id", string="Хуудсууд")
    page_count = fields.Integer(string="Хуудасны тоо", compute="_compute_page_count")
    owner_id = fields.Many2one(
        "res.users", string="Үүсгэсэн", default=lambda self: self.env.user, index=True)
    contributor_ids = fields.Many2many("res.users", string="Мэдээлэл оруулсан")
    is_pinned = fields.Boolean(string="Тогтоосон")
    active = fields.Boolean(default=True)
    last_editor_id = fields.Many2one("res.users", string="Сүүлд засварласан")
    last_edited_at = fields.Datetime(
        string="Сүүлд засварласан огноо", default=fields.Datetime.now)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("page_ids")
    def _compute_page_count(self):
        for rec in self:
            rec.page_count = len(rec.page_ids)

    @api.model_create_multi
    def create(self, vals_list):
        topics = super().create(vals_list)
        for topic in topics:
            topic.contributor_ids = [(4, self.env.user.id)]
            if not topic.page_ids:
                self.env["mng.topic.page"].create({
                    "topic_id": topic.id,
                    "name": "Ерөнхий мэдээлэл",
                    "sequence": 10,
                })
        return topics

    def _touch(self):
        self.write({
            "last_editor_id": self.env.user.id,
            "last_edited_at": fields.Datetime.now(),
            "contributor_ids": [(4, self.env.user.id)],
        })

    def action_archive_topic(self):
        self.ensure_one()
        self.write({"active": False})

    @api.model
    def get_hub_data(self, search_term=None):
        """Мэдээллийн сангийн бүх сэдэв, хуудасны жагсаалтыг буцаана.

        Хуудасны агуулгыг оруулахгүй (get_page тусад нь татна), харин хайлт
        хийсэн үед тухайн хайлт олдсон хуудас бүрийн богино эшлэлийг өгнө.
        """
        term = (search_term or "").strip()
        topics = self.search([])
        matches = {}

        if term:
            pattern = f"%{term}%"
            pages = self.env["mng.topic.page"].search([
                "|", ("name", "ilike", pattern), ("body", "ilike", pattern),
            ])
            for page in pages:
                matches.setdefault(page.topic_id.id, []).append({
                    "page_id": page.id,
                    "snippet": page._match_snippet(term),
                })
            topics = topics.filtered(
                lambda t: t.id in matches
                or term.lower() in (t.name or "").lower()
                or term.lower() in (t.summary or "").lower()
            )

        categories = self.env["mng.topic.category"].search([])
        used_ids = set(topics.mapped("category_id").ids)

        return {
            "categories": [{
                "id": cat.id,
                "name": cat.name,
                "accent": cat.accent,
                "topic_count": len(topics.filtered(lambda t, c=cat: t.category_id.id == c.id)),
            } for cat in categories if not term or cat.id in used_ids],
            "topics": [topic._hub_payload(matches.get(topic.id, [])) for topic in topics],
            "all_categories": [
                {"id": cat.id, "name": cat.name, "accent": cat.accent}
                for cat in categories
            ],
            # Хөтөлбөр/элсэлтийн үеийн нэрс нь зөвхөн шошго бөгөөд визний эрхгүй
            # ажилтан ч мэдээллийн санг ашиглах ёстой тул sudo-гоор уншина.
            "programs": [
                {"id": prog.id, "name": prog.name}
                for prog in self.env["mng.visa.program.type"].sudo().search([])
            ],
            "periods": [
                {"id": period.id, "name": period.name}
                for period in self.env["mng.visa.recruitment.period"].sudo().search([])
            ],
            "current_uid": self.env.user.id,
            "current_user_name": self.env.user.name,
            "is_manager": self.env.user.has_group(MANAGER_GROUP),
            "search_term": term,
        }

    def _hub_payload(self, match_list):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary or "",
            "category_id": self.category_id.id or False,
            "category_name": self.category_id.name or "",
            "accent": self.category_id.accent or "slate",
            "program_type_id": self.program_type_id.id or False,
            "program_name": self.program_type_id.sudo().name or "",
            "recruitment_period_id": self.recruitment_period_id.id or False,
            "period_name": self.recruitment_period_id.sudo().name or "",
            "is_pinned": self.is_pinned,
            "owner_id": self.owner_id.id,
            "owner_name": self.owner_id.name or "",
            "is_mine": self.owner_id.id == self.env.user.id,
            "last_editor_name": self.last_editor_id.name or self.owner_id.name or "",
            "edited_label": self._humanize(self.last_edited_at),
            "contributors": self.contributor_ids.mapped("name"),
            "page_count": len(self.page_ids),
            "pages": [{
                "id": page.id,
                "name": page.name,
                "sequence": page.sequence,
                "is_empty": not html2plaintext(page.body or "").strip(),
            } for page in self.page_ids.sorted(lambda p: (p.sequence, p.id))],
            "matches": match_list,
        }

    def _humanize(self, value):
        """Огноог монголоор ойлгомжтой богино тэмдэглэгээ болгоно."""
        if not value:
            return ""
        now = fields.Datetime.now()
        delta = now - value
        seconds = delta.total_seconds()
        if seconds < 60:
            return "Дөнгөж сая"
        if seconds < 3600:
            return "%d минутын өмнө" % int(seconds // 60)
        local = fields.Datetime.context_timestamp(self, value)
        local_now = fields.Datetime.context_timestamp(self, now)
        if local.date() == local_now.date():
            return "Өнөөдөр %s" % local.strftime("%H:%M")
        if (local_now.date() - local.date()).days == 1:
            return "Өчигдөр %s" % local.strftime("%H:%M")
        return local.strftime("%Y-%m-%d")


class MngTopicPage(models.Model):
    _name = "mng.topic.page"
    _description = "Сэдвийн хуудас"
    _order = "sequence, id"

    topic_id = fields.Many2one(
        "mng.topic", string="Сэдэв", required=True, ondelete="cascade", index=True)
    name = fields.Char(string="Хуудасны нэр", required=True, default="Шинэ хуудас")
    sequence = fields.Integer(string="Дараалал", default=10)
    body = fields.Html(string="Агуулга")
    active = fields.Boolean(default=True)
    last_editor_id = fields.Many2one("res.users", string="Сүүлд засварласан")
    last_edited_at = fields.Datetime(string="Сүүлд засварласан огноо")

    def _match_snippet(self, term):
        """Хайлтын үг агуулсан хэсгээс товч эшлэл гаргана."""
        self.ensure_one()
        text = " ".join(html2plaintext(self.body or "").split())
        position = text.lower().find(term.lower())
        if position < 0:
            return text[:SNIPPET_RADIUS * 2]
        start = max(position - SNIPPET_RADIUS, 0)
        end = min(position + len(term) + SNIPPET_RADIUS, len(text))
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

    @api.model
    def get_page(self, page_id):
        page = self.browse(int(page_id))
        page.check_access("read")
        return {
            "id": page.id,
            "topic_id": page.topic_id.id,
            "name": page.name,
            "body": page.body or "",
            "sequence": page.sequence,
            "last_editor_name": page.last_editor_id.name or "",
            "edited_label": page.topic_id._humanize(page.last_edited_at),
        }

    @api.model
    def reorder(self, page_ids):
        """Хуудсуудыг өгөгдсөн дарааллаар нь дугаарлана."""
        for index, page_id in enumerate(page_ids):
            self.browse(int(page_id)).write({"sequence": (index + 1) * 10})
        return True

    def action_archive_page(self):
        self.ensure_one()
        if len(self.topic_id.page_ids) <= 1:
            raise UserError(_("Сэдэвт хамгийн багадаа нэг хуудас байх ёстой."))
        self.write({"active": False})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_editor_id", self.env.user.id)
            vals.setdefault("last_edited_at", fields.Datetime.now())
        pages = super().create(vals_list)
        pages.mapped("topic_id")._touch()
        return pages

    def write(self, vals):
        result = super().write(vals)
        if "body" in vals or "name" in vals:
            super().write({
                "last_editor_id": self.env.user.id,
                "last_edited_at": fields.Datetime.now(),
            })
            self.mapped("topic_id")._touch()
        return result
