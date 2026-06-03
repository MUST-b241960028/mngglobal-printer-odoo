{
    "name": "MNG Лог — Өдөр тутмын тайлан/төлөвлөгөө",
    "version": "1.0.0",
    "category": "Human Resources",
    "summary": "Ажилчдын өдөр тутмын тайлан болон төлөвлөгөөний бүртгэл",
    "description": """
        Хүн бүр өөрийн өдөр тутмын тайлан, төлөвлөгөөг бүртгэнэ.
        Менежерүүд бүх ажилтны бүртгэлийг харна.
        - Засварлах хугацааны хязгаар (менежер тохируулна)
        - Архивлал (устгахгүй)
        - Бүтэн chatter аудит
        - Өөрийн бүртгэлийг өөр хүний нэрээр оруулах боломжгүй
    """,
    "author": "MNG Global",
    "website": "https://mngglobal.mn",
    "license": "LGPL-3",
    "depends": ["base", "mail", "mngglobal_visa"],
    "data": [
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/res_config_settings_views.xml",
        "views/daily_log_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
    "sequence": 6,
}
