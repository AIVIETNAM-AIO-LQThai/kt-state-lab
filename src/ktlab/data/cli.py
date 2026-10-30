"""Command-line entrypoint for the M0 data pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from ._io import write_json
from .eda import write_eda
from .ingest import DataContractError, load_interactions
from .splits import SplitConfig, write_splits


def run_pipeline(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    seed: int = 42,
    val_fraction: float = 0.1,
    test_fraction: float = 0.1,
    support_sizes: tuple[int, ...] = (0, 1, 3, 5, 10),
    allow_invalid: bool = False,
) -> dict[str, Any]:
    """Validate a canonical CSV, write splits/ID maps/EDA, return the manifest."""
    rows, audit = load_interactions(input_path, allow_invalid=allow_invalid)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "data_quality.json", audit.to_dict())

    config = SplitConfig(
        seed=seed,
        val_fraction=val_fraction,
        test_fraction=test_fraction,
        support_sizes=support_sizes,
    )
    source_sha256 = hashlib.sha256(Path(input_path).read_bytes()).hexdigest()
    manifest, assignments = write_splits(
        rows, out_dir / "splits", config, source_sha256=source_sha256
    )
    write_eda(rows, out_dir / "eda", assignments)
    return manifest


def _parse_support_sizes(value: str) -> tuple[int, ...]:
    try:
        sizes = tuple(int(part) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("support sizes must be comma-separated integers") from exc
    if not sizes or any(size < 0 for size in sizes):
        raise argparse.ArgumentTypeError("support sizes must be non-empty and >= 0")
    return sizes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build M0 splits, ID maps, and EDA.")
    parser.add_argument("--input", required=True, help="canonical interaction CSV")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--test-fraction", type=float, default=0.1)
    parser.add_argument("--support-sizes", type=_parse_support_sizes, default=(0, 1, 3, 5, 10))
    parser.add_argument(
        "--allow-invalid",
        action="store_true",
        help="drop invalid rows and continue (always reported in data_quality.json)",
    )
    args = parser.parse_args(argv)

    try:
        manifest = run_pipeline(
            args.input,
            args.out,
            seed=args.seed,
            val_fraction=args.val_fraction,
            test_fraction=args.test_fraction,
            support_sizes=args.support_sizes,
            allow_invalid=args.allow_invalid,
        )
    except (DataContractError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc, DataContractError):
            print(json.dumps(exc.errors[:20], indent=2, ensure_ascii=False), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "out": str(Path(args.out)),
                "counts": manifest["counts"],
                "unmapped_ids": manifest["unmapped_ids"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
