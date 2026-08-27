{
    "name": "MNG Мэдээллийн сан",
    "version": "1.0.0",
    "category": "Productivity",
    "summary": "Дуудлага хүлээн авагч ажилтнуудын сэдэв тус бүрийн хамтарсан мэдээллийн сан",
    "description": """
        Хөтөлбөр, элсэлт бүрийн мэдээллийг сэдэв болгон бүртгэж, бүх ажилтан
        нэг эх сурвалжаас уншиж, шууд засварлана.
        - Сэдэв бүр олон хуудастай (Ерөнхий мэдээлэл, Үнэ, Түгээмэл асуулт гэх мэт)
        - Хоёр ажилтан нэг хуудсыг зэрэг бичиж чадна (real-time)
        - Дуудлагын үеэр хурдан хайх: сэдэв, хуудас, агуулгаар нь хайна
    """,
    "author": "MNG Global",
    "website": "https://mngglobal.mn",
    "license": "LGPL-3",
    "depends": ["base", "web", "bus", "html_editor", "mngglobal_visa"],
    "data": [
        "security/ir.model.access.csv",
        "data/hub_category_data.xml",
        "views/hub_views.xml",
        "views/hub_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mngglobal_hub/static/src/css/topic_hub.css",
            "mngglobal_hub/static/src/js/topic_hub.js",
            "mngglobal_hub/static/src/xml/topic_hub.xml",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "sequence": 7,
}
