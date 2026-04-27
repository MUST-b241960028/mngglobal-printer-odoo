"""
Pre-migration: Reset noupdate flags on ir.rule records so that
the module upgrade can actually rewrite/create record rules.

Without this, Odoo silently skips updating any ir.rule that was
originally installed under <data noupdate="1">.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'mngglobal_visa'

# XML IDs of every ir.rule we own (old + new)
RULE_XMLIDS = [
    'rule_visa_application_manager',
    'rule_visa_application_ph_adult',
    'rule_visa_application_ph_kids',
    'rule_visa_application_jp_student',
    'rule_visa_application_jp_worker',
    'rule_visa_application_kr',
    'rule_visa_application_prevent_leak',
    'rule_visa_payment_manager',
    'rule_visa_payment_ph_adult',
    'rule_visa_payment_ph_kids',
    'rule_visa_payment_jp_student',
    'rule_visa_payment_jp_worker',
    'rule_visa_payment_kr',
    'rule_visa_payment_prevent_leak',
    'rule_visa_checklist_manager',
    'rule_visa_checklist_ph_adult',
    'rule_visa_checklist_ph_kids',
    'rule_visa_checklist_jp_student',
    'rule_visa_checklist_jp_worker',
    'rule_visa_checklist_kr',
    'rule_visa_checklist_prevent_leak',
]


def migrate(cr, version):
    """Flip noupdate → False for all our ir.rule records."""
    if not version:
        # Fresh install, nothing to migrate
        return

    _logger.info(
        "pre-migrate 1.3.0: resetting noupdate flags for %s ir.rule records",
        len(RULE_XMLIDS),
    )

    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = FALSE
         WHERE module = %s
           AND name = ANY(%s)
        """,
        (MODULE, list(RULE_XMLIDS)),
    )
    updated = cr.rowcount
    _logger.info(
        "pre-migrate 1.3.0: flipped noupdate on %d ir_model_data rows", updated
    )
