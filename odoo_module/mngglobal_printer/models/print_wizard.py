import logging
import base64
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MngPrintWizard(models.TransientModel):
    _name = "mng.print.wizard"
    _description = "Хэвлэх тохиргоо ба урьдчилан харах"

    printer_id = fields.Many2one(
        "mng.printer.device", 
        string="Принтер сонгох", 
        domain="[('is_online', '=', True)]",
        help="Хоосон орхивол тухайн принтер дээрх үндсэн принтерээр хэвлэнэ."
    )
    copies = fields.Integer(string="Хуулбар тоо", default=1)

    pages = fields.Char(
        string="Хуудас",
        help="Хэвлэх хуудсууд, ж: 1-3,5,8. Хоосон бол бүх хуудас.")
    page_subset = fields.Selection([
        ("all", "Бүх хуудас"),
        ("odd", "Сондгой хуудас"),
        ("even", "Тэгш хуудас"),
    ], string="Хуудасны багц", default="all")
    duplex = fields.Selection([
        ("default", "Принтерийн үндсэн"),
        ("simplex", "Нэг талд"),
        ("duplexlong", "Хоёр талд (урт ирмэг)"),
        ("duplexshort", "Хоёр талд (богино ирмэг)"),
    ], string="Хэвлэх тал", default="default")
    orientation = fields.Selection([
        ("default", "Үндсэн"),
        ("portrait", "Босоо"),
        ("landscape", "Хэвтээ"),
    ], string="Чиглэл", default="default")
    color_mode = fields.Selection([
        ("default", "Үндсэн"),
        ("color", "Өнгөт"),
        ("monochrome", "Хар цагаан"),
    ], string="Өнгө", default="default")
    scaling = fields.Selection([
        ("default", "Үндсэн"),
        ("fit", "Хуудсанд багтаах"),
        ("shrink", "Багасгаж багтаах"),
        ("noscale", "Жинхэнэ хэмжээ"),
    ], string="Хэмжээ", default="default")

    res_model = fields.Char(string="Эх загвар")
    res_id = fields.Integer(string="Эх бичлэгийн ID")

    pdf_preview = fields.Binary(string="PDF Урьдчилан харах", attachment=False)
    pdf_preview_filename = fields.Char(string="Файлын нэр", default="preview.pdf")
    pdf_preview_html = fields.Html(
        string="PDF HTML Preview",
        compute="_compute_pdf_preview_html",
        sanitize=False
    )

    @api.depends("pdf_preview")
    def _compute_pdf_preview_html(self):
        for rec in self:
            if rec.pdf_preview:
                if rec.id:
                    iframe_src = f"/mng_printer/stream_pdf?model={rec._name}&id={rec.id}&field=pdf_preview"
                else:
                    b64_str = rec.pdf_preview.decode("utf-8") if isinstance(rec.pdf_preview, bytes) else rec.pdf_preview
                    iframe_src = f"data:application/pdf;base64,{b64_str}#toolbar=0"

                rec.pdf_preview_html = f'''
                    <iframe src="{iframe_src}"
                            style="width:100%; height:780px; border:1px solid #ddd; border-radius:6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    </iframe>
                '''
            else:
                rec.pdf_preview_html = '''
                    <div style="text-align:center; padding: 120px 20px; color: #777; background: #fdfdfd; border: 2px dashed #ccc; border-radius: 6px;">
                        <div style="font-size: 48px; margin-bottom: 10px;">📄</div>
                        <h4 style="color: #444; font-weight: 600;">Баримт Бэлдэж Байна...</h4>
                    </div>
                '''

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res_model = res.get("res_model") or self.env.context.get("active_model")
        res_id = res.get("res_id") or self.env.context.get("active_id")

        if res_model and res_id:
            res["res_model"] = res_model
            res["res_id"] = res_id
            try:
                record = self.env[res_model].browse(res_id)
                if hasattr(record, "_get_print_report") and hasattr(record, "_render_pdf_for_print"):
                    report = record._get_print_report()
                    pdf_content, _ = record._render_pdf_for_print(report)
                    if pdf_content:
                        doc_name = (
                            getattr(record, "name", None)
                            or getattr(record, "number", None)
                            or str(record.id)
                        )
                        doc_name = "".join(c for c in doc_name if c.isalnum() or c in "._- ").strip()
                        res["pdf_preview"] = base64.b64encode(pdf_content).decode("utf-8")
                        res["pdf_preview_filename"] = f"{doc_name}.pdf"
            except Exception as e:
                _logger.warning(f"Could not generate PDF preview for {res_model},{res_id}: {e}")

        return res

    def action_print(self):
        self.ensure_one()
        pdf_b64 = self.pdf_preview
        filename = self.pdf_preview_filename or "document.pdf"

        if not pdf_b64 and self.res_model and self.res_id:
            record = self.env[self.res_model].browse(self.res_id)
            report = record._get_print_report()
            pdf_content, _ = record._render_pdf_for_print(report)
            pdf_b64 = base64.b64encode(pdf_content).decode("utf-8")
            doc_name = (
                getattr(record, "name", None)
                or getattr(record, "number", None)
                or str(record.id)
            )
            filename = f"{doc_name}.pdf"

        doc_name = os.path.splitext(filename)[0]

        self.env["mng.print.queue"].create({
            "name": doc_name,
            "pdf_data": pdf_b64,
            "pdf_filename": filename,
            "source_model": self.res_model,
            "source_id": self.res_id,
            "printer_id": self.printer_id.id,
            "copies": self.copies,
            "pages": self.pages,
            "page_subset": self.page_subset,
            "duplex": self.duplex,
            "orientation": self.orientation,
            "color_mode": self.color_mode,
            "scaling": self.scaling,
            "state": "pending",
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Оффисын принтерт илгээлээ"),
                "message": _("'%s' хэвлэх дарааллд орлоо.") % doc_name,
                "type": "success",
                "sticky": False,
            },
        }
