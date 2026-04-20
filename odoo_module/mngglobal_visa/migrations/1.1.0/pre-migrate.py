def migrate(cr, version):
    """
    Handle schema changes from pre-1.0.0 state:
    - mng_visa_payment.currency (Selection char) → currency_id (Many2one integer)
    - Drop advance_paid column from mng_visa_application if it exists
    """
    # Add currency_id column if it doesn't exist yet (Odoo ORM will populate it later)
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mng_visa_payment' AND column_name = 'currency_id'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE mng_visa_payment ADD COLUMN currency_id INTEGER
        """)

    # Migrate old 'currency' Selection values to currency_id Many2one
    # Only run if the old 'currency' column still exists
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mng_visa_payment' AND column_name = 'currency'
    """)
    if cr.fetchone():
        # Map old selection values to res.currency ids
        cr.execute("""
            UPDATE mng_visa_payment p
            SET currency_id = c.id
            FROM res_currency c
            WHERE p.currency = 'MNT' AND c.name = 'MNT'
              AND p.currency_id IS NULL
        """)
        cr.execute("""
            UPDATE mng_visa_payment p
            SET currency_id = c.id
            FROM res_currency c
            WHERE p.currency = 'USD' AND c.name = 'USD'
              AND p.currency_id IS NULL
        """)
        # Drop the old column
        cr.execute("ALTER TABLE mng_visa_payment DROP COLUMN IF EXISTS currency")

    # Drop advance_paid from application if it still exists
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mng_visa_application' AND column_name = 'advance_paid'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE mng_visa_application DROP COLUMN IF EXISTS advance_paid")
