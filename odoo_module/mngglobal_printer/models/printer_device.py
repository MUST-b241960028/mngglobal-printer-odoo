import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MngPrinterDevice(models.Model):
    """
    Холбогдсон принтер — клиент програмаас ирсэн принтерийн мэдээлэл.
    Клиент програм холбогдоход өөрийн бүх принтерийг энд бүртгэнэ.
    """
    _name = "mng.printer.device"
    _description = "Принтер төхөөрөмж"
    _order = "is_default desc, name"
    _rec_name = "display_name"

    name = fields.Char(string="Принтерийн нэр", required=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    client_name = fields.Char(string="Компьютерийн нэр",
                               help="Клиент програм суулгасан компьютерийн нэр")
    is_default = fields.Boolean(string="Үндсэн принтер", default=False)
    is_online = fields.Boolean(string="Онлайн", default=False, readonly=True)
    last_seen = fields.Datetime(string="Сүүлд холбогдсон", readonly=True)
    port = fields.Char(string="Порт")

    _constraints = [
        models.Constraint(
            "unique(name, client_name)",
            "Энэ компьютерт ижил нэртэй принтер бүртгэгдсэн байна!",
        ),
    ]

    @api.depends("name", "client_name", "is_default")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or "?"]
            if rec.client_name:
                parts.append(f"({rec.client_name})")
            if rec.is_default:
                parts.append("★")
            rec.display_name = " ".join(parts)

    @api.model
    def register_printers(self, client_name, printers):
        """
        Клиент програмаас дуудагдана. Принтерийн жагсаалтыг шинэчилнэ.

        :param client_name: str — компьютерийн нэр
        :param printers: list of dict — [{"name": "...", "default": bool, "port": "..."}, ...]
        :returns: list of dict — бүртгэгдсэн принтерүүд [{"id": int, "name": str}, ...]
        """
        now = fields.Datetime.now()
        result = []

        # Mark all printers for this client as offline first
        existing = self.search([("client_name", "=", client_name)])
        existing.write({"is_online": False})

        printer_names = []
        for p in printers:
            pname = p.get("name", "").strip()
            if not pname:
                continue
            printer_names.append(pname)

            # Find or create
            device = self.search([
                ("name", "=", pname),
                ("client_name", "=", client_name),
            ], limit=1)

            vals = {
                "is_online": True,
                "is_default": p.get("default", False),
                "last_seen": now,
                "port": p.get("port", ""),
            }

            if device:
                device.write(vals)
            else:
                vals.update({
                    "name": pname,
                    "client_name": client_name,
                })
                device = self.create(vals)

            result.append({"id": device.id, "name": device.name})

        _logger.info("Принтер бүртгэл шинэчлэгдлээ: %s — %d принтер (%s)",
                     client_name, len(result), ", ".join(printer_names))
        return result
