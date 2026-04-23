{
    "name": "MNG Принтер",
    "version": "1.0.0",
    "category": "Tools",
    "summary": "Дэлхийн хаанаас ч оффисын принтерээр хэвлэх боломж",
    "description": """
        MNG Принтер — Оффисын хэвлэлийг хялбар болгоно

        • Дурын PDF баримтыг байршуулбал оффист хэдхэн секундын дотор хэвлэгдэнэ
        • Нэхэмжлэх, борлуулалт, худалдан авалтын захиалга дээр "Оффист хэвлэх" товч
        • MNG Printer Bridge клиент програмтай ажилладаг
        • Хэвлэлийн дараалал шууд харах боломжтой (Хүлээгдэж буй → Хэвлэгдсэн / Амжилтгүй)

        Төлбөргүй. IoT хайрцаг шаардлагагүй. Odoo Community Edition дээр ажиллана.
    """,
    "author": "MNG Global",
    "website": "https://mngglobal.mn",
    "license": "LGPL-3",
    "depends": ["base", "account", "sale", "purchase"],
    "data": [
        "security/ir.model.access.csv",
        "views/print_queue_views.xml",
        "views/print_wizard_views.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "images": ["static/description/icon.png"],
    "sequence": 10,
}
