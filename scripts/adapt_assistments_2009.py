"""Adapt the local ASSISTments 2009 export to the canonical interaction CSV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SOURCE_COLUMNS = ("user_id", "order_id", "problem_id", "correct", "skill_id")
OUTPUT_COLUMNS = (
    "student_id",
    "interaction_id",
    "step",
    "question_id",
    "kc_ids",
    "correct",
)
MISSING_VALUES = {"", "na", "nan", "none", "null"}


def _clean_column(values: pd.Series) -> pd.Series:
    return values.astype("string").fillna("").str.strip()


def _encode(values: pd.Series) -> pd.Series:
    encoded, _ = pd.factorize(values, sort=True)
    return pd.Series(encoded, index=values.index, dtype="int64")


def adapt_dataframe(source: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Convert source columns without changing the input frame."""
    missing_columns = [column for column in SOURCE_COLUMNS if column not in source.columns]
    if missing_columns:
        raise ValueError(f"source CSV is missing required columns: {', '.join(missing_columns)}")

    frame = source.loc[:, SOURCE_COLUMNS].copy()
    for column in SOURCE_COLUMNS:
        frame[column] = _clean_column(frame[column])

    missing_ids = {
        column: int(frame[column].str.casefold().isin(MISSING_VALUES).sum())
        for column in ("user_id", "order_id", "problem_id")
    }
    if any(missing_ids.values()):
        raise ValueError(f"source has missing required IDs: {missing_ids}")

    missing_kc = frame["skill_id"].str.casefold().isin(MISSING_VALUES)
    valid_correct = frame["correct"].isin({"0", "1"})
    dropped_missing_kc = int(missing_kc.sum())
    dropped_invalid_correct = int((~valid_correct).sum())
    frame = frame.loc[~missing_kc & valid_correct].copy()

    if frame.empty:
        raise ValueError("no rows remain after excluding missing KCs and invalid correct values")
    if frame["order_id"].duplicated().any():
        raise ValueError("source order_id values must be unique")

    frame["student_id"] = _encode(frame["user_id"])
    frame["question_id"] = _encode(frame["problem_id"])
    frame["kc_ids"] = _encode(frame["skill_id"]).astype("string")
    frame["interaction_id"] = frame["order_id"]
    frame["correct"] = frame["correct"].astype("int64")

    # Keep each student's original CSV order; the source has no timestamp.
    frame["_source_order"] = range(len(frame))
    frame = frame.sort_values(
        ["student_id", "_source_order"], kind="stable"
    )
    frame["step"] = frame.groupby("student_id", sort=False).cumcount() + 1
    result = frame.loc[:, OUTPUT_COLUMNS].reset_index(drop=True)

    audit = {
        "input_rows": len(source),
        "output_rows": len(result),
        "dropped_rows": int((missing_kc | ~valid_correct).sum()),
        "dropped_missing_kc": dropped_missing_kc,
        "dropped_invalid_correct": dropped_invalid_correct,
        "students": int(result["student_id"].nunique()),
        "questions": int(result["question_id"].nunique()),
        "knowledge_components": int(result["kc_ids"].nunique()),
    }
    if audit["students"] < 3:
        raise ValueError("at least 3 students must remain for the canonical pipeline")
    return result, audit


def adapt_file(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    input_path = Path(input_path)
    output_path = Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("output must not overwrite the immutable raw CSV")
    raw_dir = (Path(__file__).resolve().parents[1] / "data" / "raw").resolve()
    if output_path.resolve().is_relative_to(raw_dir):
        raise ValueError("output must be outside data/raw to keep raw files immutable")

    source = pd.read_csv(
        input_path,
        encoding="cp1252",
        dtype="string",
        keep_default_na=False,
        usecols=lambda column: column in SOURCE_COLUMNS,
    )
    result, audit = adapt_dataframe(source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert ASSISTments 2009 raw CSV to the kt-state-lab data contract."
    )
    parser.add_argument(
        "--input",
        default="data/raw/assistments_2009.csv",
        help="immutable ASSISTments raw CSV (default: data/raw/assistments_2009.csv)",
    )
    parser.add_argument(
        "--output",
        default="outputs/assistments_2009/canonical.csv",
        help="canonical output path (default: outputs/assistments_2009/canonical.csv)",
    )
    args = parser.parse_args(argv)

    try:
        audit = adapt_file(args.input, args.output)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"out": args.output, **audit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
