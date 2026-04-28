import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill ALL checklist items for existing applications."""
    _logger.info("Post-migrate 1.4.1: Populating checklists for existing applications...")

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    applications = env["mng.visa.application"].search([
        ("program_type_id", "!=", False),
    ])
    _logger.info("Found %d applications to backfill checklists for.", len(applications))

    for app in applications:
        app._populate_all_checklists()
        _logger.info("  → %s (%s): %d checklist items",
                      app.name, app.program_type_id.code,
                      len(app.checklist_ids))

    _logger.info("Post-migrate 1.4.1: Checklist backfill complete.")
