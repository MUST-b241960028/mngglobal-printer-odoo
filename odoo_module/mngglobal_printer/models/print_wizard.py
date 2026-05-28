from odoo import models, fields, api, _
import base64

class MngPrintWizard(models.TransientModel):
    _name = "mng.print.wizard"
    _description = "Хэвлэх тохиргоо"

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

    def action_print(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        
        # Call the existing rendering logic from the mixin
        report = record._get_print_report()
        pdf_content, pdf_type = record._render_pdf_for_print(report)
        
        doc_name = (
            getattr(record, "name", None)
            or getattr(record, "number", None)
            or str(record.id)
        )
        filename = f"{doc_name}.pdf"
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()

        self.env["mng.print.queue"].create({
            "name": doc_name,
            "pdf_data": base64.b64encode(pdf_content).decode("utf-8"),
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
