import csv
import hashlib
import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from ktlab.data.ingest import load_interactions
from ktlab.data.splits import (
    SplitConfig,
    assign_students,
    build_id_maps,
    make_cs_s_examples,
    write_splits,
)
from tests.support import FIXTURE


def _load():
    rows, _ = load_interactions(FIXTURE)
    return rows


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.rows = _load()
        self.config = SplitConfig(seed=42, val_fraction=0.34, test_fraction=0.34)

    def test_assignment_is_deterministic_and_disjoint(self):
        first = assign_students(self.rows, self.config)
        second = assign_students(self.rows, self.config)
        self.assertEqual(first, second)

        by_split = defaultdict(set)
        for student, split in first.items():
            by_split[split].add(student)
        self.assertEqual(set(by_split), {"train", "val", "test"})
        self.assertFalse(by_split["train"] & by_split["val"])
        self.assertFalse(by_split["train"] & by_split["test"])
        self.assertFalse(by_split["val"] & by_split["test"])
        self.assertEqual(set(first), {r.student_id for r in self.rows})

    def test_id_maps_come_from_train_only(self):
        assignments = assign_students(self.rows, self.config)
        train_rows = [row for row in self.rows if assignments[row.student_id] == "train"]
        maps = build_id_maps(train_rows)
        self.assertEqual(maps["student"]["__unk__"], 0)
        self.assertEqual(
            set(maps["student"]) - {"__unk__"}, {row.student_id for row in train_rows}
        )
        for name, values in (
            ("question", {row.question_id for row in train_rows}),
            ("kc", {kc for row in train_rows for kc in row.kc_ids}),
        ):
            self.assertEqual(set(maps[name]) - {"__unk__"}, values)
            indices = [maps[name][value] for value in values]
            self.assertEqual(sorted(indices), list(range(1, len(values) + 1)))

    def test_cs_s_support_is_chronological_prefix(self):
        assignments = assign_students(self.rows, self.config)
        examples = make_cs_s_examples(self.rows, assignments, self.config.support_sizes)
        history_length = defaultdict(int)
        for row in self.rows:
            history_length[row.student_id] += 1

        grouped = defaultdict(list)
        for example in examples:
            grouped[(example["split"], example["student_id"], example["support_size"])].append(example)

        self.assertTrue(grouped)
        for (split, student, k), group in grouped.items():
            self.assertNotEqual(split, "train")
            support = [e for e in group if e["role"] == "support"]
            query = [e for e in group if e["role"] == "query"]
            self.assertEqual(len(support), k)
            self.assertEqual(len(support) + len(query), history_length[student])
            if support:
                self.assertLess(max(e["step"] for e in support), min(e["step"] for e in query))

    def test_train_students_have_no_cs_s_examples(self):
        assignments = assign_students(self.rows, self.config)
        examples = make_cs_s_examples(self.rows, assignments, self.config.support_sizes)
        train_students = {student for student, split in assignments.items() if split == "train"}
        self.assertFalse({example["student_id"] for example in examples} & train_students)

    def test_write_splits_is_deterministic_and_hashes_match(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            manifest1, assignments1 = write_splits(self.rows, Path(tmp1), self.config)
            manifest2, assignments2 = write_splits(self.rows, Path(tmp2), self.config)
            self.assertEqual(assignments1, assignments2)
            self.assertEqual(manifest1, manifest2)
            self.assertEqual(
                (Path(tmp1) / "manifest.json").read_text(encoding="utf-8"),
                (Path(tmp2) / "manifest.json").read_text(encoding="utf-8"),
            )

            for name, info in manifest1["files"].items():
                data = (Path(tmp1) / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), info["sha256"], name)
            id_maps = (Path(tmp1) / "id_maps.json").read_bytes()
            self.assertEqual(hashlib.sha256(id_maps).hexdigest(), manifest1["id_maps_sha256"])

    def test_student_sets_are_disjoint_in_written_csvs(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, _ = write_splits(self.rows, Path(tmp), self.config)
            students = {}
            for split in ("train", "val", "test"):
                with (Path(tmp) / f"{split}.csv").open(encoding="utf-8", newline="") as handle:
                    students[split] = {row["student_id"] for row in csv.DictReader(handle)}
            self.assertFalse(students["train"] & students["val"])
            self.assertFalse(students["train"] & students["test"])
            self.assertFalse(students["val"] & students["test"])
            self.assertEqual(
                sum(len(value) for value in students.values()),
                manifest["counts"]["students"]["train"]
                + manifest["counts"]["students"]["val"]
                + manifest["counts"]["students"]["test"],
            )

    def test_invalid_config_is_rejected(self):
        with self.assertRaises(ValueError):
            SplitConfig(val_fraction=0.6, test_fraction=0.5)
        with self.assertRaises(ValueError):
            SplitConfig(support_sizes=(1, 1))
        with self.assertRaises(ValueError):
            SplitConfig(support_sizes=(-1,))


if __name__ == "__main__":
    unittest.main()
