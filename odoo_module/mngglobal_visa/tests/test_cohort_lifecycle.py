from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCohortLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["mng.visa.program.type"].create({
            "name": "Cohort Test Program",
            "code": "COHORT_TEST",
            "visa_type": "student",
        })
        cls.stage = cls.env["mng.visa.stage"].create({
            "name": "Inquiry",
            "program_type_id": cls.program.id,
            "sequence": 1,
        })
        cls.current_period = cls.env["mng.visa.recruitment.period"].create({
            "name": "Current Cohort",
            "program_type_id": cls.program.id,
            "state": "active",
        })
        cls.next_period = cls.env["mng.visa.recruitment.period"].create({
            "name": "Next Cohort",
            "program_type_id": cls.program.id,
            "state": "active",
        })

    def _new_application(self):
        return self.env["mng.visa.application"].create({
            "program_type_id": self.program.id,
            "recruitment_period_id": self.current_period.id,
            "client_name": "Test Student",
        })

    def test_move_preserves_case_and_records_history(self):
        application = self._new_application()

        move = application.action_move_to_period(
            self.next_period, "Test cohort transfer"
        )

        self.assertEqual(application.recruitment_period_id, self.next_period)
        self.assertEqual(move.from_period_id, self.current_period)
        self.assertEqual(move.to_period_id, self.next_period)
        self.assertEqual(move.move_type, "move")
        self.assertEqual(move.reason, "Test cohort transfer")

    def test_defer_creates_clean_case_and_keeps_original_intact(self):
        application = self._new_application()
        self.env["mng.visa.payment"].create({
            "application_id": application.id,
            "name": "Existing payment",
            "amount": 100,
        })

        deferred = application.action_defer_to_period(
            self.next_period, "Test defer"
        )

        self.assertNotEqual(deferred, application)
        self.assertEqual(application.recruitment_period_id, self.current_period)
        self.assertEqual(deferred.recruitment_period_id, self.next_period)
        self.assertEqual(deferred.client_name, application.client_name)
        self.assertEqual(deferred.previous_application_id, application)
        self.assertFalse(deferred.payment_ids)
        self.assertTrue(application.period_move_ids.filtered(
            lambda move: move.move_type == "defer"
            and move.new_application_id == deferred
        ))

    def test_workspace_data_keeps_program_and_cohort_boundaries(self):
        assigned = self._new_application()
        assigned.stage_id = self.stage
        unassigned = self.env["mng.visa.application"].create({
            "program_type_id": self.program.id,
            "client_name": "Unassigned Student",
            "kanban_state": "blocked",
        })

        workspace = self.env["mng.visa.application"].get_cohort_workspace_data(
            self.program.id
        )

        self.assertEqual(workspace["program"]["id"], self.program.id)
        self.assertEqual(workspace["stats"]["total"], 2)
        self.assertEqual(workspace["stats"]["unassigned"], 1)
        self.assertEqual(workspace["stats"]["blocked"], 1)
        self.assertIn("can_create_invoice", workspace["capabilities"])
        self.assertTrue(any(
            card["id"] == assigned.id
            for column in workspace["columns"]
            for card in column["cards"]
        ))

        cohort_workspace = self.env["mng.visa.application"].get_cohort_workspace_data(
            self.program.id, self.current_period.id, "cohort"
        )
        visible_ids = {
            card["id"]
            for column in cohort_workspace["columns"]
            for card in column["cards"]
        }
        self.assertEqual(visible_ids, {assigned.id})
        self.assertNotIn(unassigned.id, visible_ids)

    def test_current_workspace_uses_latest_open_recruitment_period(self):
        today = fields.Date.today()
        older_period = self.env["mng.visa.recruitment.period"].create({
            "name": "Older Open Period",
            "program_type_id": self.program.id,
            "date_start": fields.Date.add(today, days=-60),
            "date_end": fields.Date.add(today, days=10),
        })
        current_period = self.env["mng.visa.recruitment.period"].create({
            "name": "Current Open Period",
            "program_type_id": self.program.id,
            "date_start": fields.Date.add(today, days=-30),
            "date_end": fields.Date.add(today, days=60),
        })
        future_period = self.env["mng.visa.recruitment.period"].create({
            "name": "Future Period",
            "program_type_id": self.program.id,
            "date_start": fields.Date.add(today, days=30),
            "date_end": fields.Date.add(today, days=120),
        })
        older_application = self.env["mng.visa.application"].create({
            "program_type_id": self.program.id,
            "recruitment_period_id": older_period.id,
            "client_name": "Older Student",
        })
        current_application = self.env["mng.visa.application"].create({
            "program_type_id": self.program.id,
            "recruitment_period_id": current_period.id,
            "client_name": "Current Student",
        })
        future_application = self.env["mng.visa.application"].create({
            "program_type_id": self.program.id,
            "recruitment_period_id": future_period.id,
            "client_name": "Future Student",
        })

        workspace = self.env["mng.visa.application"].get_cohort_workspace_data(
            self.program.id, scope="current"
        )
        visible_ids = {
            card["id"]
            for column in workspace["columns"]
            for card in column["cards"]
        }

        self.assertEqual(workspace["current_cohort_id"], current_period.id)
        sidebar_period_ids = {cohort["id"] for cohort in workspace["cohorts"]}
        self.assertTrue({
            older_period.id,
            current_period.id,
            future_period.id,
        }.issubset(sidebar_period_ids))
        self.assertEqual(visible_ids, {current_application.id})
        self.assertNotIn(older_application.id, visible_ids)
        self.assertNotIn(future_application.id, visible_ids)
