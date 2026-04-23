import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PrintBridgeMixin(models.AbstractModel):
    """
    Дурын загварт 'Оффист хэвлэх' функц нэмдэг mixin.
    Баримтын PDF-ийг үүсгэж хэвлэх дарааллын ажил үүсгэнэ.
    Odoo 17 / 18 / 19 нийцтэй.
    """
    _name = "mng.print.bridge.mixin"
    _description = "MNG Принтер Mixin"

    def _get_print_report(self):
        """Энэ баримтын ir.actions.report-ийг буцаана."""
        report_map = {
            "account.move": "account.account_invoices",
            "sale.order": "sale.action_report_saleorder",
            "purchase.order": "purchase.action_report_purchaseorder",
            "stock.picking": "stock.action_report_delivery",
        }
        ref = report_map.get(self._name)
        if ref:
            report = self.env.ref(ref, raise_if_not_found=False)
            if report:
                return report
        return None

    def _render_pdf_for_print(self, report):
        """Odoo хувилбаруудын нийцтэйгээр PDF үүсгэх."""
        try:
            pdf_content, content_type = self.env["ir.actions.report"]._render_qweb_pdf(
                report.report_name, res_ids=[self.id]
            )
            return pdf_content, content_type
        except (TypeError, AttributeError):
            pass

        try:
            pdf_content, content_type = report._render_qweb_pdf(
                report.id, res_ids=[self.id]
            )
            return pdf_content, content_type
        except (TypeError, AttributeError):
            pass

        try:
            pdf_content, content_type = report._render_qweb_pdf([self.id])
            return pdf_content, content_type
        except Exception:
            pass

        raise UserError(_(
            "PDF үүсгэж чадсангүй. Системийн админтай холбогдоно уу."
        ))

    def action_print_at_office(self):
        """PDF үүсгэж хэвлэх тохиргоо (wizard) нээнэ. UI товчны үйлдэл."""
        self.ensure_one()

        report = self._get_print_report()
        if not report:
            raise UserError(_(
                "%s баримтын хэвлэх тайлан тохируулаагүй байна. "
                "Системийн админтай холбогдоно уу."
            ) % self._name)

        return {
            "name": _("Хэвлэх тохиргоо"),
            "type": "ir.actions.act_window",
            "res_model": "mng.print.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "mng.print.bridge.mixin"]


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "mng.print.bridge.mixin"]


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "mng.print.bridge.mixin"]
