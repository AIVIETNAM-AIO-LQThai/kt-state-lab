import unittest

import pandas as pd

from scripts.adapt_assistments_2009 import OUTPUT_COLUMNS, adapt_dataframe


class AssistmentsAdapterTests(unittest.TestCase):
    def test_maps_ids_and_preserves_per_student_source_order(self):
        source = pd.DataFrame(
            {
                "user_id": ["u2", "u1", "u2", "u1"],
                "order_id": ["4", "2", "9", "8"],
                "problem_id": ["q2", "q1", "q1", "q2"],
                "correct": ["1", "0", "1", "0"],
                "skill_id": ["k2", "k1", "k1", "k2"],
            }
        )
        source.loc[4] = ["u3", "10", "q3", "1", "k3"]
        original = source.copy(deep=True)

        result, audit = adapt_dataframe(source)

        self.assertEqual(list(result.columns), list(OUTPUT_COLUMNS))
        self.assertEqual(source.to_dict(), original.to_dict())
        self.assertEqual(result["student_id"].nunique(), 3)
        self.assertEqual(result["question_id"].nunique(), 3)
        self.assertEqual(result["kc_ids"].nunique(), 3)
        self.assertEqual(set(result["student_id"]), {0, 1, 2})
        self.assertEqual(set(result["question_id"]), {0, 1, 2})
        self.assertEqual(set(result["kc_ids"]), {"0", "1", "2"})
        self.assertEqual(
            result.groupby("student_id", sort=False)["step"].apply(list).tolist(),
            [[1, 2], [1, 2], [1]],
        )
        self.assertEqual(audit["input_rows"], 5)
        self.assertEqual(audit["output_rows"], 5)

    def test_excludes_missing_kc_and_invalid_correct_rows_with_counts(self):
        source = pd.DataFrame(
            {
                "user_id": ["u1", "u2", "u3", "u4", "u5"],
                "order_id": ["1", "2", "3", "4", "5"],
                "problem_id": ["q1", "q2", "q3", "q4", "q5"],
                "correct": ["1", "0", "2", "1", "1"],
                "skill_id": ["k1", "NA", "k2", "k3", "k4"],
            }
        )

        result, audit = adapt_dataframe(source)

        self.assertEqual(len(result), 3)
        self.assertEqual(audit["dropped_missing_kc"], 1)
        self.assertEqual(audit["dropped_invalid_correct"], 1)

    def test_rejects_missing_required_source_columns(self):
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            adapt_dataframe(pd.DataFrame({"user_id": []}))


if __name__ == "__main__":
    unittest.main()
