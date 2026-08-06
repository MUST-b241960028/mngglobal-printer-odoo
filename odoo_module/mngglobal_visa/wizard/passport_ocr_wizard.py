import base64
import json
import logging
import urllib.request
import urllib.error
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MngVisaPassportOcrWizard(models.TransientModel):
    _name = "mng.visa.passport.ocr.wizard"
    _description = "AI Паспорт Унших Визард"

    application_id = fields.Many2one(
        "mng.visa.application", string="Аппликейшн", required=True)
    
    file = fields.Binary(string="Паспортын зураг / Файл", required=True)
    file_name = fields.Char(string="Файлын нэр")

    extracted_name = fields.Char(string="Илрүүлсэн нэр (Client Name)", readonly=True)
    extracted_passport_number = fields.Char(string="Паспортын дугаар", readonly=True)
    extracted_dob = fields.Date(string="Төрсөн огноо", readonly=True)
    extracted_expiry = fields.Date(string="Дуусах огноо", readonly=True)

    state = fields.Selection([
        ("upload", "Файл хуулах"),
        ("preview", "Шалгах & Баталгаажуулах"),
    ], default="upload")

    def action_scan_passport(self):
        """
        Gemini Vision API ашиглан паспортын мэдээллийг уншина.
        """
        self.ensure_one()
        if not self.file:
            raise UserError(_("Паспортын файлаа сонгоно уу!"))

        api_key = self.env["ir.config_parameter"].sudo().get_param("mngglobal_visa.gemini_api_key")
        model = self.env["ir.config_parameter"].sudo().get_param("mngglobal_visa.gemini_model", "gemini-2.5-flash")

        if not api_key:
            raise UserError(_("Gemini API Key тохируулагдаагүй байна. Тохиргоо -> AI Тохиргоо хэсэгт API Key оруулна уу."))

        mime_type = "image/jpeg"
        if self.file_name:
            fn = self.file_name.lower()
            if fn.endswith(".png"):
                mime_type = "image/png"
            elif fn.endswith(".pdf"):
                mime_type = "application/pdf"
            elif fn.endswith(".webp"):
                mime_type = "image/webp"

        base64_data = self.file.decode("utf-8") if isinstance(self.file, bytes) else self.file

        prompt = """
You are an expert OCR parser for passports.
Extract the following fields from this passport document image in strict JSON format:
{
  "client_name": "Full name (Surname GivenName in Roman/Mongolian format if available)",
  "passport_number": "Passport number e.g. E3006775",
  "date_of_birth": "YYYY-MM-DD format e.g. 1997-12-19",
  "passport_expiry": "YYYY-MM-DD format e.g. 2032-04-24"
}
Only output valid JSON with no code fences or extra commentary.
If any field is missing or unreadable, set its value to null.
"""

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
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

            candidates = result.get("candidates", [])
            if not candidates:
                raise UserError(_("AI Хариу буцаасангүй. Зургийн чанараа шалгана уу."))

            text_content = candidates[0]["content"]["parts"][0]["text"].strip()
            # Clean JSON if any code fences exist
            if text_content.startswith("```json"):
                text_content = text_content[7:]
            if text_content.endswith("```"):
                text_content = text_content[:-3]
            text_content = text_content.strip()

            parsed = json.loads(text_content)

            self.write({
                "extracted_name": parsed.get("client_name"),
                "extracted_passport_number": parsed.get("passport_number"),
                "extracted_dob": parsed.get("date_of_birth"),
                "extracted_expiry": parsed.get("passport_expiry"),
                "state": "preview",
            })

            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            _logger.error("Gemini API Error: %s", err_body)
            raise UserError(_("Gemini API Алдаа: %s") % e.reason)
        except Exception as e:
            _logger.error("Passport OCR processing error: %s", str(e))
            raise UserError(_("Паспорт уншихад алдаа гарлаа: %s") % str(e))

    def action_confirm_apply(self):
        """
        Илрүүлсэн мэдээллийг аппликейшн дээр бичиж хаана.
        """
        self.ensure_one()
        vals = {}
        if self.extracted_name:
            vals["client_name"] = self.extracted_name
        if self.extracted_passport_number:
            vals["passport_number"] = self.extracted_passport_number
        if self.extracted_dob:
            vals["date_of_birth"] = self.extracted_dob
        if self.extracted_expiry:
            vals["passport_expiry"] = self.extracted_expiry

        if vals:
            self.application_id.write(vals)

            # Also create passport document record automatically
            self.env["mng.visa.document"].create({
                "application_id": self.application_id.id,
                "document_type": "passport",
                "name": _("Паспорт — %s") % (self.extracted_name or self.application_id.client_name or ""),
                "file": self.file,
                "file_name": self.file_name or "passport.jpg",
                "notes": _("AI Passport OCR-оор автоматаар уншиж бүртгэсэн."),
            })

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Амжилттай!"),
                    "message": _("Паспортын мэдээлэл болон баримт амжилттай бүртгэгдлээ."),
                    "type": "success",
                    "sticky": False,
                }
            }
