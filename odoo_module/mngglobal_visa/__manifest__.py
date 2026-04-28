{
    "name": "MNG Виза — Зуучлалын Удирдлага",
    "version": "1.4.1",
    "category": "Services",
    "summary": "MNG Global зуучлалын үйл ажиллагааны удирдлагын систем",
    "description": """
        Филиппин, Япон, Солонгос зуучлалын бүрэн удирдлага.
        - Kanban pipeline (drag & drop)
        - Хөтөлбөр тус бүрийн үе шатны тохиргоо
        - Шалгах хуудас (per-stage checklist)
        - Төлбөр, нэхэмжлэл хяналт
        - Удирдлагын хэсэг
    """,
    "author": "MNG Global",
    "website": "https://mngglobal.mn",
    "license": "LGPL-3",
    "depends": ["base", "mail", "contacts", "account"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/program_data.xml",
        "data/template_data.xml",
        "views/visa_application_views.xml",
        "views/visa_document_views.xml",
        "views/visa_config_views.xml",
        "views/visa_dashboard_views.xml",
        "views/visa_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mngglobal_visa/static/src/css/dashboard.css"
        ]
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "sequence": 5,
}
