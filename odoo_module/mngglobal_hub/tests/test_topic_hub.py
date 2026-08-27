from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestTopicHub(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["mng.topic.category"].create({
            "name": "Тест ангилал",
            "accent": "teal",
        })
        cls.peer = new_test_user(cls.env, login="hub_peer", groups="base.group_user")

    def _new_topic(self, name="Филиппин өвлийн зуслан"):
        return self.env["mng.topic"].create({
            "name": name,
            "category_id": self.category.id,
        })

    def test_new_topic_is_writable_immediately(self):
        """Шинэ сэдэв нээхэд ажилтан шууд бичиж эхлэх хуудастай байх ёстой."""
        topic = self._new_topic()
        self.assertEqual(len(topic.page_ids), 1)
        self.assertTrue(topic.page_ids.name)

    def test_edit_records_who_answered_last(self):
        """Дуудлага авах хүн мэдээллийг хэн, хэзээ шинэчилснийг харах ёстой."""
        topic = self._new_topic()
        page = topic.page_ids
        page.with_user(self.peer).write({"body": "<p>Хичээл 12 сарын 5-нд эхэлнэ.</p>"})

        self.assertEqual(page.last_editor_id, self.peer)
        self.assertEqual(topic.last_editor_id, self.peer)
        self.assertIn(self.peer, topic.contributor_ids)

    def test_search_finds_topic_by_page_content(self):
        """Дуудлагын үеэр агуулгын дотроос хайж, ямар хуудсанд байгааг олох ёстой."""
        topic = self._new_topic()
        topic.page_ids.write({
            "body": "<p>Онгоцны тийз 1,850,000 төгрөг, эцэг эх хамт нисэхгүй.</p>",
        })

        data = self.env["mng.topic"].get_hub_data("тийз")
        found = [item for item in data["topics"] if item["id"] == topic.id]

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["matches"][0]["page_id"], topic.page_ids.id)
        self.assertIn("1,850,000", found[0]["matches"][0]["snippet"])

    def test_search_ignores_unrelated_topics(self):
        """Хайлт нь холбогдолгүй сэдвийг гаргаж ирвэл ажилтан буруу хариулт өгнө."""
        self._new_topic()
        other = self._new_topic("Япон хэлний сургууль")
        other.page_ids.write({"body": "<p>Элсэлт 1 сард.</p>"})

        data = self.env["mng.topic"].get_hub_data("Элсэлт 1 сард")

        self.assertEqual([item["id"] for item in data["topics"]], [other.id])

    def test_last_page_cannot_be_archived(self):
        """Сэдэв хоосон үлдвэл дуудлага авах хүн юу ч уншихгүй болно."""
        topic = self._new_topic()
        first = topic.page_ids

        with self.assertRaises(UserError):
            first.action_archive_page()

        second = self.env["mng.topic.page"].create({
            "topic_id": topic.id,
            "name": "Түгээмэл асуулт",
        })
        second.action_archive_page()

        self.assertEqual(topic.page_ids.ids, first.ids)
