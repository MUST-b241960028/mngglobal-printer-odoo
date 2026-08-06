import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove the retired AI Copilot records from upgraded databases."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    xmlids = (
        "mng_visa_ai_copilot_menu",
        "mng_visa_ai_copilot_wizard_action",
        "mng_visa_ai_copilot_wizard_form",
        "access_visa_ai_copilot_wizard_all",
    )
    records = env["ir.model.data"].search([
        ("module", "=", "mngglobal_visa"),
        ("name", "in", xmlids),
    ])
    for record in records:
        target = env[record.model].browse(record.res_id).exists()
        if target:
            target.unlink()
    records.unlink()
    _logger.info("Post-migrate 2.3.3: removed retired AI Copilot records.")
