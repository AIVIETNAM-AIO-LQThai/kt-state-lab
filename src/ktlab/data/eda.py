"""Descriptive EDA for the canonical interaction table."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from ._io import write_csv, write_json
from .schema import SPLIT_NAMES, Interaction


def _percentile(values: list[float | int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _frequency(rows: list[Interaction], field: str) -> Counter[str]:
    if field == "question":
        return Counter(row.question_id for row in rows)
    return Counter(kc for row in rows for kc in row.kc_ids)


def _long_tail(counts: Counter[str]) -> dict[str, Any]:
    frequencies = sorted(counts.values())
    return {
        "n_unique": len(counts),
        "n_singletons": sum(1 for value in frequencies if value == 1),
        "n_le_5": sum(1 for value in frequencies if value <= 5),
        "median_frequency": _percentile(frequencies, 0.5),
        "max_frequency": frequencies[-1] if frequencies else 0,
        "top_20": [
            {"id": key, "count": value} for key, value in counts.most_common(20)
        ],
    }


def summarize(
    rows: list[Interaction],
    assignments: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot summarize zero interactions")

    by_student: dict[str, list[Interaction]] = defaultdict(list)
    for row in rows:
        by_student[row.student_id].append(row)

    lengths = [len(history) for history in by_student.values()]
    max_step = max(row.step for row in rows)

    position_totals: Counter[int] = Counter()
    position_correct: Counter[int] = Counter()
    for row in rows:
        if row.step <= 15:
            position_totals[row.step] += 1
            position_correct[row.step] += row.correct

    question_counts = _frequency(rows, "question")
    kc_counts = _frequency(rows, "kc")

    first_seen: dict[tuple[str, str], int] = {}
    gaps: list[float] = []
    transitions: Counter[tuple[str, str]] = Counter()
    for student_id, history in by_student.items():
        ordered = sorted(history, key=lambda row: row.step)
        last_ts: datetime | None = None
        for row in ordered:
            for kc in row.kc_ids:
                first_seen.setdefault((student_id, kc), row.step)
            if row.timestamp:
                ts = _parse_timestamp(row.timestamp)
                if ts is not None:
                    if last_ts is not None:
                        gaps.append((ts - last_ts).total_seconds())
                    last_ts = ts
        for previous, current in zip(ordered, ordered[1:]):
            for source in previous.kc_ids:
                for target in current.kc_ids:
                    transitions[(source, target)] += 1

    first_seen_buckets: Counter[str] = Counter(
        str(step) if step <= 15 else ">15" for step in first_seen.values()
    )

    summary: dict[str, Any] = {
        "n_students": len(by_student),
        "n_interactions": len(rows),
        "n_questions": len(question_counts),
        "n_kcs": len(kc_counts),
        "correct_rate": sum(row.correct for row in rows) / len(rows),
        "sequence_length": {
            "min": min(lengths),
            "mean": fmean(lengths),
            "p50": _percentile(lengths, 0.5),
            "p90": _percentile(lengths, 0.9),
            "max": max(lengths),
        },
        "coverage": {
            "student_question_pairs": len({(row.student_id, row.question_id) for row in rows}),
            "possible_student_question_pairs": len(by_student) * len(question_counts),
            "student_kc_pairs": len(first_seen),
            "possible_student_kc_pairs": len(by_student) * len(kc_counts),
        },
        "question_long_tail": _long_tail(question_counts),
        "kc_long_tail": _long_tail(kc_counts),
        "correct_by_position": [
            {
                "position": position,
                "n": position_totals[position],
                "correct_rate": position_correct[position] / position_totals[position],
            }
            for position in sorted(position_totals)
        ],
        "kc_first_seen_step": dict(sorted(first_seen_buckets.items())),
        "time_gaps_seconds": {
            "n_gaps": len(gaps),
            "min": min(gaps) if gaps else None,
            "p50": _percentile(gaps, 0.5),
            "p90": _percentile(gaps, 0.9),
            "max": max(gaps) if gaps else None,
        },
    }

    if assignments is not None:
        train_rows = [row for row in rows if assignments[row.student_id] == "train"]
        train_questions = {row.question_id for row in train_rows}
        train_kcs = {kc for row in train_rows for kc in row.kc_ids}
        train_students = {row.student_id for row in train_rows}
        availability: dict[str, Any] = {}
        for split in SPLIT_NAMES:
            split_rows = [row for row in rows if assignments[row.student_id] == split]
            questions = {row.question_id for row in split_rows}
            kcs = {kc for row in split_rows for kc in row.kc_ids}
            availability[split] = {
                "n_students": len({row.student_id for row in split_rows}),
                "n_interactions": len(split_rows),
                "questions": {
                    "n": len(questions),
                    "seen_in_train": len(questions & train_questions),
                    "unseen_in_train": len(questions - train_questions),
                },
                "kcs": {
                    "n": len(kcs),
                    "seen_in_train": len(kcs & train_kcs),
                    "unseen_in_train": len(kcs - train_kcs),
                },
                "leaked_students_from_train": (
                    0
                    if split == "train"
                    else len({row.student_id for row in split_rows} & train_students)
                ),
            }
        summary["split_availability"] = availability

    return summary


def write_eda(
    rows: list[Interaction],
    out_dir: Path,
    assignments: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Write summary JSON and the underlying frequency/transition tables."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(rows, assignments)
    write_json(out_dir / "eda_summary.json", summary)

    by_student: dict[str, list[Interaction]] = defaultdict(list)
    for row in rows:
        by_student[row.student_id].append(row)

    sequence_counts = Counter(len(history) for history in by_student.values())
    write_csv(
        out_dir / "sequence_lengths.csv",
        ("length", "n_students"),
        ({"length": length, "n_students": count} for length, count in sorted(sequence_counts.items())),
    )

    write_csv(
        out_dir / "correct_by_position.csv",
        ("position", "n", "correct_rate"),
        summary["correct_by_position"],
    )

    for name, counts in (
        ("question_frequency.csv", _frequency(rows, "question")),
        ("kc_frequency.csv", _frequency(rows, "kc")),
    ):
        write_csv(
            out_dir / name,
            ("id", "count"),
            ({"id": key, "count": count} for key, count in sorted(counts.items())),
        )

    transitions: Counter[tuple[str, str]] = Counter()
    for history in by_student.values():
        ordered = sorted(history, key=lambda row: row.step)
        for previous, current in zip(ordered, ordered[1:]):
            for source in previous.kc_ids:
                for target in current.kc_ids:
                    transitions[(source, target)] += 1
    write_csv(
        out_dir / "kc_transitions.csv",
        ("from_kc", "to_kc", "count"),
        (
            {"from_kc": source, "to_kc": target, "count": count}
            for (source, target), count in sorted(
                transitions.items(), key=lambda item: (-item[1], item[0])
            )
        ),
    )
    return summary
