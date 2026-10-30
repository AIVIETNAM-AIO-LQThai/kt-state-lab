"""Small deterministic JSON/CSV writers with content hashes."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_csv(path: Path, columns: Iterable[str], rows: Iterable[Mapping[str, object]]) -> tuple[str, int]:
    """Write stable CSV and return (sha256, row count)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(columns),
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return hashlib.sha256(path.read_bytes()).hexdigest(), count


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
