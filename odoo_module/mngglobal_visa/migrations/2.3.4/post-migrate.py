import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove the retired global new-agreement inbox and its actions."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    records = env["ir.model.data"].search([
        ("module", "=", "mngglobal_visa"),
        ("name", "in", (
            "mng_visa_intake_menu",
            "mng_visa_cohort_workspace_intake",
            "mng_visa_app_action_intake",
        )),
    ])
    for record in records:
        target = env[record.model].browse(record.res_id).exists()
        if target:
            target.unlink()
    records.unlink()
    _logger.info("Post-migrate 2.3.4: removed the global new-agreement inbox.")
