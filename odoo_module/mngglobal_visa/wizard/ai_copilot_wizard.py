import json
import logging
import urllib.request
import urllib.error
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MngVisaAiCopilotWizard(models.TransientModel):
    _name = "mng.visa.ai.copilot.wizard"
    _description = "AI Туслах / ERP Copilot"

    user_query = fields.Text(string="Таны асуулт / Хүсэлт", required=True,
                             help="Жишээ нь: Солонгос 9-р сарын элсэлтэд нийт хэдэн оюутан байна вэ?")
    
    ai_response = fields.Text(string="AI Хариулт", readonly=True)

    def action_ask_ai(self):
        """
        ERP DB-ээс сүүлийн үеийн мэдээллийн контекст цуглуулж, Gemini AI-д асуулт тавина.
        """
        self.ensure_one()
        api_key = self.env["ir.config_parameter"].sudo().get_param("mngglobal_visa.gemini_api_key")
        model = self.env["ir.config_parameter"].sudo().get_param("mngglobal_visa.gemini_model", "gemini-2.5-flash")

        if not api_key:
            raise UserError(_("Gemini API Key тохируулагдаагүй байна. Тохиргоо -> AI Тохиргоо хэсэгт API Key оруулна уу."))

        # 1. Gather live ERP summary stats
        apps = self.env["mng.visa.application"].search([])
        periods = self.env["mng.visa.recruitment.period"].search([("state", "!=", "archived")])

        # Applications by program
        prog_stats = {}
        for app in apps:
            pname = app.program_type_id.name or "Тодорхойгүй"
            prog_stats[pname] = prog_stats.get(pname, 0) + 1

        # Applications by recruitment period
        period_stats = {}
        for p in periods:
            count = len(p.application_ids)
            period_stats[p.name] = {
                "program": p.program_type_id.name or "Бүх",
                "count": count,
                "paid_count": p.paid_count,
                "state": p.state
            }

        # Insurance deadline warnings
        overdue_ins = apps.filtered(lambda a: not a.insurance_done and a.insurance_due_date)
        overdue_ins_list = [{
            "name": a.client_name,
            "code": a.name,
            "program": a.program_type_id.name,
            "due_date": str(a.insurance_due_date)
        } for a in overdue_ins[:10]]

        erp_context = {
            "total_applications": len(apps),
            "applications_by_program": prog_stats,
            "recruitment_periods": period_stats,
            "insurance_warnings_count": len(overdue_ins),
            "insurance_warnings_sample": overdue_ins_list
        }

        system_instruction = f"""
You are an expert ERP AI Assistant for MNG Global (Visa & Overseas Education Agency in Mongolia).
Answer user questions accurately, professionally, and politely in MONGOLIAN language.

Here is the LIVE REAL-TIME DATA from MNG Global Odoo ERP:
```json
{json.dumps(erp_context, ensure_ascii=False, indent=2)}
```

Instructions:
- Use markdown formatting (bolding, bullet points, clean lists).
- If the user asks about statistics, counts, or period details, rely strictly on the JSON ERP data above.
- Always respond in natural, professional Mongolian.
"""

        payload = {
            "contents": [{
                "parts": [{"text": self.user_query}]
            }],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.2,
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
                raise UserError(_("AI Хариу буцаасангүй."))

            text_response = candidates[0]["content"]["parts"][0]["text"].strip()
            self.write({"ai_response": text_response})

            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            _logger.error("Gemini API Copilot Error: %s", err_body)
            raise UserError(_("Gemini API Алдаа: %s") % e.reason)
        except Exception as e:
            _logger.error("Copilot query error: %s", str(e))
            raise UserError(_("AI Хариу гарахад алдаа гарлаа: %s") % str(e))
