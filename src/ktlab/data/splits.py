"""Student-disjoint splits and CS-S support/query examples."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._io import write_csv, write_json
from .schema import CANONICAL_COLUMNS, SPLIT_NAMES, UNK_ID, Interaction

EXAMPLE_COLUMNS = CANONICAL_COLUMNS + ("split", "support_size", "role")


@dataclass(frozen=True)
class SplitConfig:
    seed: int = 42
    val_fraction: float = 0.1
    test_fraction: float = 0.1
    support_sizes: tuple[int, ...] = (0, 1, 3, 5, 10)

    def __post_init__(self) -> None:
        if not 0 < self.val_fraction < 1 or not 0 < self.test_fraction < 1:
            raise ValueError("val_fraction and test_fraction must be in (0, 1)")
        if self.val_fraction + self.test_fraction >= 1:
            raise ValueError("val_fraction + test_fraction must be < 1")
        if not self.support_sizes or any(k < 0 for k in self.support_sizes):
            raise ValueError("support_sizes must be non-empty and >= 0")
        if len(set(self.support_sizes)) != len(self.support_sizes):
            raise ValueError("support_sizes must not contain duplicates")


def assign_students(rows: list[Interaction], config: SplitConfig) -> dict[str, str]:
    """Assign whole students to train/val/test; never split a student's history."""
    students = sorted({row.student_id for row in rows})
    if len(students) < 3:
        raise ValueError("at least 3 students are needed for train/val/test")

    rng = random.Random(config.seed)
    rng.shuffle(students)
    n = len(students)
    n_test = min(max(1, round(n * config.test_fraction)), n - 2)
    n_val = min(max(1, round(n * config.val_fraction)), n - n_test - 1)

    test = set(students[:n_test])
    val = set(students[n_test : n_test + n_val])
    return {
        student: "test" if student in test else "val" if student in val else "train"
        for student in sorted(students)
    }


def build_id_maps(train_rows: list[Interaction]) -> dict[str, dict[str, int]]:
    """Map IDs from training data only; unseen IDs become ``__unk__`` (0)."""

    def mapping(values: set[str]) -> dict[str, int]:
        if UNK_ID in values:
            raise ValueError(f"reserved ID {UNK_ID!r} appears in the data")
        return {UNK_ID: 0, **{value: i for i, value in enumerate(sorted(values), start=1)}}

    return {
        "student": mapping({row.student_id for row in train_rows}),
        "question": mapping({row.question_id for row in train_rows}),
        "kc": mapping({kc for row in train_rows for kc in row.kc_ids}),
    }


def make_cs_s_examples(
    rows: list[Interaction],
    assignments: dict[str, str],
    support_sizes: tuple[int, ...],
) -> list[dict[str, Any]]:
    """Build chronological support prefixes and later query targets for val/test."""
    by_student: dict[str, list[Interaction]] = defaultdict(list)
    for row in rows:
        by_student[row.student_id].append(row)

    examples: list[dict[str, Any]] = []
    for student_id in sorted(by_student):
        split = assignments[student_id]
        if split == "train":
            continue
        history = sorted(by_student[student_id], key=lambda row: row.step)
        for k in sorted(set(support_sizes)):
            if k >= len(history):
                continue
            for index, row in enumerate(history):
                examples.append(
                    {
                        **row.to_row(),
                        "split": split,
                        "support_size": k,
                        "role": "support" if index < k else "query",
                    }
                )
    return sorted(
        examples,
        key=lambda item: (
            item["split"],
            item["student_id"],
            item["support_size"],
            item["step"],
        ),
    )


def _unmapped_counts(
    rows: list[Interaction], maps: dict[str, dict[str, int]]
) -> dict[str, int]:
    return {
        "students": len({row.student_id for row in rows} - maps["student"].keys()),
        "questions": len({row.question_id for row in rows} - maps["question"].keys()),
        "kcs": len({kc for row in rows for kc in row.kc_ids} - maps["kc"].keys()),
    }


def write_splits(
    rows: list[Interaction],
    out_dir: Path,
    config: SplitConfig = SplitConfig(),
    *,
    source_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Write split CSVs, CS-S examples, ID maps, and a hashed manifest."""
    assignments = assign_students(rows, config)
    out_dir.mkdir(parents=True, exist_ok=True)

    by_split: dict[str, list[Interaction]] = {name: [] for name in SPLIT_NAMES}
    for row in rows:
        by_split[assignments[row.student_id]].append(row)

    files: dict[str, Any] = {}
    for split in SPLIT_NAMES:
        split_rows = sorted(by_split[split], key=lambda row: (row.student_id, row.step))
        path = out_dir / f"{split}.csv"
        digest, count = write_csv(
            path,
            CANONICAL_COLUMNS + ("split",),
            ({**row.to_row(), "split": split} for row in split_rows),
        )
        files[path.name] = {"sha256": digest, "rows": count}

    examples = make_cs_s_examples(rows, assignments, config.support_sizes)
    digest, count = write_csv(out_dir / "cs_s_examples.csv", EXAMPLE_COLUMNS, examples)
    files["cs_s_examples.csv"] = {"sha256": digest, "rows": count}

    maps = build_id_maps(by_split["train"])
    id_maps_sha = write_json(out_dir / "id_maps.json", maps)

    examples_by_split: dict[str, dict[str, int]] = {
        split: dict(sorted(Counter(e["support_size"] for e in examples if e["split"] == split).items()))
        for split in ("val", "test")
    }
    manifest = {
        "schema_version": 1,
        "source_sha256": source_sha256,
        "config": {
            "seed": config.seed,
            "val_fraction": config.val_fraction,
            "test_fraction": config.test_fraction,
            "support_sizes": list(config.support_sizes),
        },
        "counts": {
            "students": {split: len({r.student_id for r in by_split[split]}) for split in SPLIT_NAMES},
            "interactions": {split: len(by_split[split]) for split in SPLIT_NAMES},
            "cs_s_examples": {
                split: {
                    "total": sum(examples_by_split[split].values()),
                    "by_support_size": examples_by_split[split],
                }
                for split in ("val", "test")
            },
        },
        "unmapped_ids": {split: _unmapped_counts(by_split[split], maps) for split in ("val", "test")},
        "files": files,
        "id_maps_sha256": id_maps_sha,
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest, assignments
