{
    "name": "MNG Виза — Зуучлалын Удирдлага",
    "version": "1.1.2",
    "category": "Services",
    "summary": "MNG Global зуучлалын үйл ажиллагааны удирдлагын систем",
    "description": """
        Филиппин, Япон, Солонгос зуучлалын бүрэн удирдлага.
        - Kanban pipeline (drag & drop)
        - Leads from chatbot → conversion to applications
        - Checklist per stage
        - Payment tracking (Odoo Invoicing)
        - CEO dashboard
    """,
    "author": "MNG Global",
    "website": "https://mngglobal.mn",
    "license": "LGPL-3",
    "depends": ["base", "mail", "contacts", "account"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/program_data.xml",
        "data/template_data.xml",
        "views/visa_dashboard_views.xml",
        "views/visa_lead_views.xml",
        "views/visa_application_views.xml",
        "views/visa_config_views.xml",
        "views/visa_menus.xml",
    ],
    "assets": {},
    "application": True,
    "installable": True,
    "auto_install": False,
    "sequence": 5,
}
