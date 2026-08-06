import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Give existing cohort assignments an auditable starting point."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Application = env["mng.visa.application"]
    PeriodMove = env["mng.visa.period.move"]
    applications = Application.search([
        ("recruitment_period_id", "!=", False),
    ])
    existing_application_ids = set(PeriodMove.search([
        ("application_id", "in", applications.ids),
    ]).mapped("application_id").ids)

    values = []
    for application in applications:
        if application.id in existing_application_ids:
            continue
        values.append({
            "application_id": application.id,
            "to_period_id": application.recruitment_period_id.id,
            "move_type": "initial",
            "reason": "Existing cohort assignment recorded during the cohort workspace upgrade.",
            "moved_at": application.write_date or application.create_date,
            "moved_by": application.write_uid.id or SUPERUSER_ID,
        })

    if values:
        PeriodMove.create(values)
    _logger.info(
        "Post-migrate 2.2.0: recorded %d existing cohort assignments.",
        len(values),
    )
