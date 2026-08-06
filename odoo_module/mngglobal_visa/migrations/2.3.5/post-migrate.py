import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


SEED_PERIOD_XMLIDS = (
    "rp_jp_stu_2027_jan",
    "rp_jp_stu_2027_apr",
    "rp_jp_stu_2027_jul",
    "rp_jp_stu_2027_oct",
    "rp_kr_2027_mar",
    "rp_kr_2027_jun",
    "rp_kr_2027_sep",
    "rp_kr_2027_dec",
)


def migrate(cr, version):
    """Remove only the duplicate 2027 periods previously seeded by the module."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    xml_records = env["ir.model.data"].search([
        ("module", "=", "mngglobal_visa"),
        ("model", "=", "mng.visa.recruitment.period"),
        ("name", "in", SEED_PERIOD_XMLIDS),
    ])
    removed = 0
    for xml_record in xml_records:
        period = env["mng.visa.recruitment.period"].browse(xml_record.res_id).exists()
        if period and period.application_ids:
            _logger.warning(
                "Keeping seeded period %s because it has %d contracts.",
                period.display_name,
                len(period.application_ids),
            )
            continue
        if period:
            period.unlink()
        xml_record.exists().unlink()
        removed += 1
    _logger.info("Post-migrate 2.3.5: removed %d duplicate seeded periods.", removed)
