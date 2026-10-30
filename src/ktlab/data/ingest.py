"""CSV ingestion and validation for the canonical interaction contract."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import CANONICAL_COLUMNS, KC_SEPARATOR, REQUIRED_COLUMNS, Interaction


class DataContractError(ValueError):
    """Raised when a CSV cannot be used without silently dropping data."""

    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        preview = "; ".join(
            f"row {e['source_row']} [{e['field']}]: {e['message']}" for e in errors[:5]
        )
        more = "" if len(errors) <= 5 else f" (+{len(errors) - 5} more)"
        super().__init__(f"{len(errors)} contract error(s): {preview}{more}")


@dataclass
class Audit:
    rows_read: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    missing_by_column: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def rows_rejected(self) -> int:
        return len({error["source_row"] for error in self.errors})

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "rows_read": self.rows_read,
            "rows_valid": self.rows_read - self.rows_rejected,
            "rows_rejected": self.rows_rejected,
            "missing_by_column": self.missing_by_column,
            "errors": self.errors,
        }


def _error(row: int, field_name: str, message: str) -> dict[str, Any]:
    return {"source_row": row, "field": field_name, "message": message}


def _parse_timestamp(value: str, row: int) -> tuple[datetime | None, dict[str, Any] | None]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, _error(row, "timestamp", f"not an ISO-8601 timestamp: {value!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc), None


def load_interactions(
    path: str | Path,
    *,
    allow_invalid: bool = False,
) -> tuple[list[Interaction], Audit]:
    """Load and validate a canonical CSV.

    Invalid rows are rejected, never silently fixed. By default any error raises
    ``DataContractError``; ``allow_invalid=True`` returns only valid rows plus an
    audit suitable for ``data_quality.json``.
    """
    path = Path(path)
    audit = Audit()
    audit.missing_by_column = {name: 0 for name in CANONICAL_COLUMNS}

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DataContractError([_error(1, "header", "CSV is empty")])
        missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
        if missing:
            raise DataContractError(
                [_error(1, "header", f"missing required column(s): {', '.join(missing)}")]
            )

        parsed_rows: list[Interaction] = []
        timestamps: dict[int, datetime] = {}
        for line_no, raw in enumerate(reader, start=2):
            audit.rows_read += 1
            for name in CANONICAL_COLUMNS:
                if not (raw.get(name) or "").strip():
                    audit.missing_by_column[name] += 1

            student_id = (raw.get("student_id") or "").strip()
            interaction_id = (raw.get("interaction_id") or "").strip()
            question_id = (raw.get("question_id") or "").strip()
            step_text = (raw.get("step") or "").strip()
            correct_text = (raw.get("correct") or "").strip()
            kc_text = (raw.get("kc_ids") or "").strip()
            timestamp_text = (raw.get("timestamp") or "").strip()
            question_text = (raw.get("question_text") or "").strip()

            row_errors: list[dict[str, Any]] = []
            for name, value in (
                ("student_id", student_id),
                ("interaction_id", interaction_id),
                ("question_id", question_id),
                ("step", step_text),
                ("kc_ids", kc_text),
                ("correct", correct_text),
            ):
                if not value:
                    row_errors.append(_error(line_no, name, "required value is blank"))

            try:
                step = int(step_text)
                if step < 1:
                    row_errors.append(_error(line_no, "step", "must be >= 1"))
            except ValueError:
                step = 0
                row_errors.append(_error(line_no, "step", f"not an integer: {step_text!r}"))

            if correct_text not in {"0", "1"}:
                row_errors.append(_error(line_no, "correct", f"must be 0 or 1: {correct_text!r}"))

            kc_ids = tuple(kc.strip() for kc in kc_text.split(KC_SEPARATOR) if kc.strip())
            if kc_text and not kc_ids:
                row_errors.append(_error(line_no, "kc_ids", "no non-empty KC id"))

            parsed_ts = None
            if timestamp_text:
                parsed_ts, ts_error = _parse_timestamp(timestamp_text, line_no)
                if ts_error:
                    row_errors.append(ts_error)

            if row_errors:
                audit.errors.extend(row_errors)
                continue

            interaction = Interaction(
                student_id=student_id,
                interaction_id=interaction_id,
                step=step,
                question_id=question_id,
                kc_ids=kc_ids,
                correct=int(correct_text),
                timestamp=timestamp_text or None,
                question_text=question_text or None,
                source_row=line_no,
            )
            parsed_rows.append(interaction)
            if parsed_ts is not None:
                timestamps[line_no] = parsed_ts

    if audit.rows_read == 0:
        audit.errors.append(_error(1, "rows", "CSV has a header but no data rows"))

    clean, dedup_errors, duplicate_rows = _check_duplicates(parsed_rows)
    audit.errors.extend(dedup_errors)
    clean = [row for row in clean if row.source_row not in duplicate_rows]
    clean, order_errors = _check_timestamp_order(clean, timestamps)
    audit.errors.extend(order_errors)
    dropped = {e["source_row"] for e in order_errors}
    if dropped:
        clean = [row for row in clean if row.source_row not in dropped]

    if audit.errors and not allow_invalid:
        raise DataContractError(audit.errors)
    return clean, audit


def _check_duplicates(
    rows: list[Interaction],
) -> tuple[list[Interaction], list[dict[str, Any]], set[int]]:
    seen_interaction: dict[tuple[str, str], int] = {}
    seen_step: dict[tuple[str, int], int] = {}
    errors: list[dict[str, Any]] = []
    dropped: set[int] = set()
    for row in rows:
        interaction_key = (row.student_id, row.interaction_id)
        step_key = (row.student_id, row.step)
        if interaction_key in seen_interaction:
            errors.append(
                _error(
                    row.source_row,
                    "interaction_id",
                    f"duplicate ({row.student_id}, {row.interaction_id}) first seen at row "
                    f"{seen_interaction[interaction_key]}",
                )
            )
            dropped.add(row.source_row)
            continue
        if step_key in seen_step:
            errors.append(
                _error(
                    row.source_row,
                    "step",
                    f"duplicate step {row.step} for {row.student_id} first seen at row "
                    f"{seen_step[step_key]}",
                )
            )
            dropped.add(row.source_row)
            continue
        seen_interaction[interaction_key] = row.source_row
        seen_step[step_key] = row.source_row
    return rows, errors, dropped


def _check_timestamp_order(
    rows: list[Interaction],
    timestamps: dict[int, datetime],
) -> tuple[list[Interaction], list[dict[str, Any]]]:
    by_student: dict[str, list[Interaction]] = defaultdict(list)
    for row in rows:
        by_student[row.student_id].append(row)

    errors: list[dict[str, Any]] = []
    for student_id, history in by_student.items():
        last_ts: datetime | None = None
        last_row = 0
        for row in sorted(history, key=lambda item: item.step):
            ts = timestamps.get(row.source_row)
            if ts is None:
                continue
            if last_ts is not None and ts < last_ts:
                errors.append(
                    _error(
                        row.source_row,
                        "timestamp",
                        f"decreases from row {last_row} within student {student_id!r} "
                        "when sorted by step",
                    )
                )
                continue
            last_ts = ts
            last_row = row.source_row
    return rows, errors
