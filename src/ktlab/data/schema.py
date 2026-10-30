"""Canonical interaction schema shared by all workstreams."""

from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED_COLUMNS = (
    "student_id",
    "interaction_id",
    "step",
    "question_id",
    "kc_ids",
    "correct",
)
OPTIONAL_COLUMNS = ("timestamp", "question_text")
CANONICAL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

KC_SEPARATOR = ";"
SPLIT_NAMES = ("train", "val", "test")
UNK_ID = "__unk__"


@dataclass(frozen=True)
class Interaction:
    """One row of the canonical interaction table.

    ``step`` is the within-student ordering key. ``source_row`` is the CSV
    record number (starting at 2) so rejected rows stay traceable.
    """

    student_id: str
    interaction_id: str
    step: int
    question_id: str
    kc_ids: tuple[str, ...] = field(default_factory=tuple)
    correct: int = 0
    timestamp: str | None = None
    question_text: str | None = None
    source_row: int = 0

    def to_row(self) -> dict[str, object]:
        return {
            "student_id": self.student_id,
            "interaction_id": self.interaction_id,
            "step": self.step,
            "question_id": self.question_id,
            "kc_ids": KC_SEPARATOR.join(self.kc_ids),
            "correct": self.correct,
            "timestamp": self.timestamp or "",
            "question_text": self.question_text or "",
        }
