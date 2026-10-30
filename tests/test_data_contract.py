import unittest

from ktlab.data.ingest import DataContractError, load_interactions
from tests.support import FIXTURE, HEADER, row, write_csv


class DataContractTests(unittest.TestCase):
    def test_fixture_loads_clean(self):
        rows, audit = load_interactions(FIXTURE)
        self.assertTrue(audit.ok)
        self.assertEqual(audit.rows_read, 30)
        self.assertEqual(len(rows), 30)
        multi_kc = [r for r in rows if r.question_id == "q06"]
        self.assertTrue(multi_kc)
        self.assertTrue(all(len(r.kc_ids) == 2 for r in multi_kc))

    def test_missing_required_column_reports_header(self):
        path = write_csv("student_id,interaction_id,step,question_id,kc_ids\ns1,i1,1,q1,kc1\n")
        try:
            with self.assertRaises(DataContractError) as caught:
                load_interactions(path)
            self.assertEqual(caught.exception.errors[0]["field"], "header")
        finally:
            path.unlink()

    def test_invalid_label_is_rejected_not_fixed(self):
        path = write_csv(HEADER + "\n" + row(correct=2) + "\n")
        try:
            with self.assertRaises(DataContractError):
                load_interactions(path)
            rows, audit = load_interactions(path, allow_invalid=True)
            self.assertEqual(rows, [])
            self.assertEqual(audit.rows_rejected, 1)
        finally:
            path.unlink()

    def test_duplicate_interaction_id_is_rejected(self):
        path = write_csv(HEADER + "\n" + row(interaction="i1", step=1) + "\n" + row(interaction="i1", step=2) + "\n")
        try:
            with self.assertRaises(DataContractError) as caught:
                load_interactions(path)
            self.assertIn("duplicate", caught.exception.errors[0]["message"])
        finally:
            path.unlink()

    def test_duplicate_student_step_is_rejected(self):
        path = write_csv(HEADER + "\n" + row(interaction="i1", step=1) + "\n" + row(interaction="i2", step=1) + "\n")
        try:
            with self.assertRaises(DataContractError):
                load_interactions(path)
        finally:
            path.unlink()

    def test_blank_kc_is_rejected(self):
        path = write_csv(HEADER + "\n" + row(kcs="") + "\n")
        try:
            with self.assertRaises(DataContractError):
                load_interactions(path)
        finally:
            path.unlink()

    def test_timestamp_regression_within_student_is_rejected(self):
        path = write_csv(
            HEADER
            + "\n"
            + row(interaction="i1", step=1, timestamp="2024-01-01T10:00:00Z")
            + "\n"
            + row(interaction="i2", step=2, timestamp="2024-01-01T09:00:00Z")
            + "\n"
        )
        try:
            with self.assertRaises(DataContractError) as caught:
                load_interactions(path)
            self.assertEqual(caught.exception.errors[0]["field"], "timestamp")
            rows, audit = load_interactions(path, allow_invalid=True)
            self.assertEqual(len(rows), 1)
            self.assertEqual(audit.rows_rejected, 1)
        finally:
            path.unlink()

    def test_header_only_is_rejected(self):
        path = write_csv(HEADER + "\n")
        try:
            with self.assertRaises(DataContractError) as caught:
                load_interactions(path)
            self.assertEqual(caught.exception.errors[0]["field"], "rows")
        finally:
            path.unlink()

    def test_rows_out_of_file_order_are_accepted(self):
        path = write_csv(
            HEADER
            + "\n"
            + row(interaction="i2", step=2, timestamp="2024-01-01T09:05:00Z")
            + "\n"
            + row(interaction="i1", step=1, timestamp="2024-01-01T09:00:00Z")
            + "\n"
        )
        try:
            rows, audit = load_interactions(path)
            self.assertTrue(audit.ok)
            self.assertEqual({r.step for r in rows}, {1, 2})
        finally:
            path.unlink()

    def test_missing_optional_timestamp_is_allowed(self):
        path = write_csv(HEADER + "\n" + row(timestamp="") + "\n")
        try:
            rows, audit = load_interactions(path)
            self.assertEqual(len(rows), 1)
            self.assertTrue(audit.ok)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
