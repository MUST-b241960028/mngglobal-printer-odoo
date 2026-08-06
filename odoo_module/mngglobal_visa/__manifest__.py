{
    "name": "MNG Виза — Зуучлалын Удирдлага",
    "version": "2.3.3",
    "category": "Services",
    "summary": "MNG Global зуучлалын үйл ажиллагааны удирдлагын систем",
    "description": """
        Филиппин, Япон, Солонгос зуучлалын бүрэн удирдлага.
        - AI Passport OCR Scanning & Auto-Fill (Паспорт автоматаар унших)
        - AI Smart Client Message Drafter (Оюутны сануулга мессеж бэлтгэгч)
        - SearchPanel sidebar: Хөтөлбөр тус бүрийн pipeline дотор элсэлтийн үеэр шүүх
        - Kanban pipeline (drag & drop)
    """,
    "author": "MNG Global",
    "website": "https://mngglobal.mn",
    "license": "LGPL-3",
    "depends": ["base", "mail", "contacts", "account", "calendar"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/program_data.xml",
        "data/template_data.xml",
        "data/recruitment_period_data.xml",
        "views/visa_recruitment_period_views.xml",
        "views/visa_application_views.xml",
        "views/visa_cohort_workspace_views.xml",
        "views/visa_assign_period_wizard_views.xml",
        "views/period_move_wizard_views.xml",
        "views/passport_ocr_wizard_views.xml",
        "views/period_add_lead_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "views/visa_document_views.xml",
        "views/visa_config_views.xml",
        "views/visa_dashboard_views.xml",
        "views/visa_audit_views.xml",
        "views/visa_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mngglobal_visa/static/src/css/dashboard.css",
            "mngglobal_visa/static/src/css/cohort_workspace.css",
            "mngglobal_visa/static/src/js/cohort_workspace.js",
            "mngglobal_visa/static/src/xml/cohort_workspace.xml",
        ]
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "sequence": 5,
}
