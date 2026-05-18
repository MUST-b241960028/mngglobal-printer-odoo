def migrate(cr, version):
    """
    1.2.0: Drop the unused mng.visa.lead model and the lead_id FK on applications.
    The chatbot lead flow was never built; leads were dead weight in the UI.
    """
    # Drop FK column on applications
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mng_visa_application' AND column_name = 'lead_id'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE mng_visa_application DROP COLUMN IF EXISTS lead_id CASCADE")

    # Drop the lead table itself
    cr.execute("DROP TABLE IF EXISTS mng_visa_lead CASCADE")

    # Remove orphan ir.model / ir.model.fields / ir.model.data rows for the lead model
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model = 'ir.model' AND name = 'model_mng_visa_lead'
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'mng.visa.lead'
    """)
    cr.execute("""
        DELETE FROM ir_model
        WHERE model = 'mng.visa.lead'
    """)

    # Remove menu / action / view records tied to the lead UI (defensive — Odoo usually
    # handles this when records are removed from data files, but xmlid cleanup is cheap).
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'mngglobal_visa'
          AND name IN (
              'mng_visa_lead_kanban',
              'mng_visa_lead_list',
              'mng_visa_lead_form',
              'mng_visa_lead_action',
              'mng_visa_leads_menu',
              'access_visa_lead_user',
              'access_visa_lead_admin',
              'access_visa_lead_mgr'
          )
    """)

    # Drop orphan view/action rows pointing at the now-deleted model (xmlid cleanup
    # above only removes the external ID registry, not the actual records).
    cr.execute("DELETE FROM ir_ui_view WHERE model = 'mng.visa.lead'")
    cr.execute("DELETE FROM ir_act_window WHERE res_model = 'mng.visa.lead'")
