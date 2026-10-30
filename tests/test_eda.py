import csv
import json
import tempfile
import unittest
from pathlib import Path

from ktlab.data.eda import summarize, write_eda
from ktlab.data.ingest import load_interactions
from ktlab.data.splits import SplitConfig, assign_students
from tests.support import FIXTURE


class EdaTests(unittest.TestCase):
    def setUp(self):
        self.rows, _ = load_interactions(FIXTURE)

    def test_summary_counts_and_rates(self):
        summary = summarize(self.rows)
        self.assertEqual(summary["n_students"], 6)
        self.assertEqual(summary["n_interactions"], 30)
        self.assertEqual(summary["n_questions"], 6)
        self.assertEqual(summary["n_kcs"], 3)
        self.assertAlmostEqual(
            summary["correct_rate"], sum(row.correct for row in self.rows) / 30
        )
        self.assertEqual(summary["sequence_length"]["min"], 4)
        self.assertEqual(summary["sequence_length"]["max"], 6)
        self.assertEqual(summary["time_gaps_seconds"]["n_gaps"], 24)
        self.assertEqual(summary["coverage"]["student_question_pairs"], 29)

    def test_position_rows_are_bounded_to_first_fifteen_steps(self):
        summary = summarize(self.rows)
        positions = [item["position"] for item in summary["correct_by_position"]]
        self.assertEqual(positions, list(range(1, 7)))
        self.assertTrue(all(item["n"] > 0 for item in summary["correct_by_position"]))

    def test_split_availability_has_no_student_overlap(self):
        assignments = assign_students(
            self.rows, SplitConfig(seed=42, val_fraction=0.34, test_fraction=0.34)
        )
        summary = summarize(self.rows, assignments)
        for split in ("train", "val", "test"):
            self.assertEqual(summary["split_availability"][split]["leaked_students_from_train"], 0)
        self.assertGreater(
            summary["split_availability"]["test"]["questions"]["n"],
            0,
        )

    def test_write_eda_outputs_tables(self):
        assignments = assign_students(
            self.rows, SplitConfig(seed=42, val_fraction=0.34, test_fraction=0.34)
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary = write_eda(self.rows, Path(tmp), assignments)
            expected = {
                "eda_summary.json",
                "sequence_lengths.csv",
                "correct_by_position.csv",
                "question_frequency.csv",
                "kc_frequency.csv",
                "kc_transitions.csv",
            }
            self.assertEqual({p.name for p in Path(tmp).iterdir()}, expected)
            loaded = json.loads((Path(tmp) / "eda_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded, summary)

            with (Path(tmp) / "kc_transitions.csv").open(encoding="utf-8", newline="") as handle:
                transitions = {(row["from_kc"], row["to_kc"]) for row in csv.DictReader(handle)}
            self.assertIn(("kc03", "kc02"), transitions)

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == "__main__":
    unittest.main()
